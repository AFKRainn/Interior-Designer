"""
Chairman Agent

Receives the full consultant–client conversation (including the approved
Final Design Summary) and generates three clean, direct image generation
prompts: floor plan, front elevation, and 3D realistic render.
"""
import logging

from app.services.openrouter import OpenRouterClient

logger = logging.getLogger(__name__)

CHAIRMAN_SYSTEM_PROMPT = """\
You generate prompts for an AI image generation model. Be precise, specific, \
and short. Do not add rules, restrictions, or disclaimers — just describe \
exactly what to draw or render.
"""

CHAIRMAN_PROMPT = """\
Based on the conversation and Final Design Summary below, generate three image \
generation prompts.

{conversation}

━━━ PROPORTIONS RULE — APPLIES TO ALL THREE PROMPTS ━━━
Before writing any prompt, calculate the real-world aspect ratio of the design \
from the available dimensions. If width and height are both known: compute the \
ratio (e.g. 90 cm wide × 270 cm tall = width:height = 1:3). \
If width and depth are known for the floor plan: compute that ratio too. \
Every prompt you write must open with a proportions statement that names both \
the numeric ratio AND a plain description: \
"width:height ratio 1:3 — tall and narrow" or \
"width:depth ratio 1:0.72 — nearly square footprint" etc. \
If only one dimension is known, estimate from the design type. \
This must be the very first sentence of each prompt so the model composes \
the correct canvas shape before placing any elements. \
Never omit this. A drawing that is the wrong shape is wrong, no matter how \
correct the content is.

━━━ INSTRUCTIONS FOR EACH PROMPT ━━━

1. FLOOR PLAN
A floor plan is a camera pointing STRAIGHT DOWN at the unit from above. \
You are describing the CUT SECTION geometry only — not what is inside the unit.

What is VISIBLE from directly above:
- The outer rectangular perimeter (width × depth as a closed rectangle)
- Internal structural vertical dividers — these appear as lines running \
  FRONT-TO-BACK (parallel to the depth axis), one line per dividing wall
- The front face — show door openings as GAPS in the front edge line; \
  doors that are closed appear as thin rectangles flush with the front edge
- For L-shape or multi-wall: show both walls meeting at the corner

What is NOT VISIBLE from above (do NOT mention in the floor plan prompt):
- Shelves (they are horizontal — invisible from above)
- Drawer fronts (vertical face — invisible from above)
- Appliances behind doors
- Cornice, base plinth, hardware
- Any internal content or storage arrangement

Build the prompt as:
"[Proportions statement: width × depth, ratio, shape description.] \
Generate a top-down floor plan of [outer shape and total dimensions if given]. \
Inside, [number] vertical dividing lines at [positions if known] create \
[number] sections from left to right, each [width if known] wide. \
The front edge shows [describe door openings as gaps or closed door lines]. \
[For L-shape: describe the second wall.] \
Draw this exactly to scale — the rectangle must reflect the real width-to-depth \
ratio and must not be stretched or squared off. \
Black and white. Lines only. Top-down 2D view. No perspective. \
[If dimensions given: Label these dimensions: width, depth, each section width.] \
[If no dimensions: No numbers. No text labels.]"

2. FRONT ELEVATION
Build the prompt as:
"[Proportions statement: width × height, ratio, shape description — e.g. \
'90 cm wide × 270 cm tall, ratio 1:3, the drawing must be 3 times taller than \
it is wide — tall and narrow. Do not widen or compress the drawing.'] \
Generate a front elevation drawing of [describe the full design from left to \
right, bay by bay: for each bay state exactly what it shows — drawer section, \
panel door, glass door, open shelf, decorative column — its proportional height \
and width relative to the whole, plus all visible details: cornice or top trim \
style, any grooves or carved profiles on sides, hardware type and position, \
shelf lines inside open sections, base or plinth style]. \
Black and white. 2D front view. Maintain the stated proportions exactly — \
the image canvas must match the width:height ratio. \
Minimal text — only label things like 'open shelf' or 'glass' where a word \
genuinely helps."
Then add dimensions: if the conversation contains any measurements (overall \
width, height, bay widths, element heights, plinth height, etc. — including \
any that were derived or calculated during the conversation), add: \
"Add architectural dimension annotations: draw extension lines and arrows for \
ALL of these measurements — [list every dimension explicitly: e.g. '90 cm total \
width (horizontal arrow across top), 270 cm total height (vertical arrow on \
right side), 22.6 cm left bay width (horizontal arrow below the bay), 62 cm \
right bay width (horizontal arrow below the bay), 10 cm plinth height (vertical \
arrow on left side)']. Place dimension lines outside the drawing boundary so \
they do not overlap the design."
If no dimensions were given or calculated at all, add: "No dimension annotations."

3. REALISTIC RENDER
Build the prompt in this order:

a) Proportions first — "[width × height, ratio, plain description — e.g. \
'90 cm wide × 270 cm tall, ratio 1:3 — the unit is exactly 3 times taller than \
it is wide, tall and narrow. Render it at this ratio. Do not widen it.']"

b) Structure and materials — describe the full piece: material of each surface, \
color and finish, hardware style, top trim treatment, base treatment, bay \
arrangement left to right.

c) Built-in elements — for any appliance, equipment, or object that sits inside \
a bay, explicitly state it fills the bay tightly: e.g. "washing machine fitted \
flush into its bay, filling the full bay width and height of that section with \
no visible gap on the sides." Do this for every appliance or insert.

d) Context — where it sits (mounted on wall / freestanding / built-in). \
"Natural lighting. Clean neutral background. Render the exact proportions stated \
— do not widen, compress, or recompose."

━━━ OUTPUT ━━━
Return JSON only — no other text:
{{
  "floor_plan": "...",
  "front_elevation": "...",
  "realistic_render": "..."
}}
"""


class Chairman:
    """
    Generates three clean image generation prompts from the approved design.
    """

    def __init__(self, client: OpenRouterClient | None = None):
        from config import CHAIRMAN_MODEL_CFG
        self.client = client or OpenRouterClient()
        self.model = CHAIRMAN_MODEL_CFG["id"]
        self.reasoning_effort = CHAIRMAN_MODEL_CFG.get("reasoning_effort", "none")

    async def generate_prompts(self, messages: list[dict]) -> dict:
        """
        Generate floor plan, front elevation, and realistic render prompts.

        Args:
            messages: Full consultant–client conversation history (includes
                      the assistant's final confirmed response with the summary).

        Returns:
            {"floor_plan": str, "front_elevation": str, "realistic_render": str}
        """
        conversation_text = self._format_conversation(messages)

        prompt = CHAIRMAN_PROMPT.format(conversation=conversation_text)

        api_messages = [
            {"role": "system", "content": CHAIRMAN_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]

        response = await self.client.chat_completion(
            model=self.model,
            messages=api_messages,
            temperature=1.0,
            reasoning_effort=self.reasoning_effort,
        )

        parsed = self.client.extract_json(response) or {}
        if not isinstance(parsed, dict):
            parsed = {}

        floor_plan = parsed.get("floor_plan", "")
        front_elevation = parsed.get("front_elevation", "")
        realistic_render = parsed.get("realistic_render", "")

        # Log for developer review
        sep = "=" * 70
        for label, p in [
            ("FLOOR PLAN", floor_plan),
            ("FRONT ELEVATION", front_elevation),
            ("REALISTIC RENDER", realistic_render),
        ]:
            print(f"\n{sep}\n[CHAIRMAN PROMPT] {label}\n{sep}\n{p}\n{sep}\n")

        if not floor_plan or not front_elevation or not realistic_render:
            logger.warning(
                f"Chairman produced incomplete prompts. "
                f"Raw response: {self.client.extract_text(response)[:500]}"
            )

        return {
            "floor_plan": floor_plan,
            "front_elevation": front_elevation,
            "realistic_render": realistic_render,
        }

    async def improve_prompt(
        self,
        view_type: str,
        original_prompt: str,
        feedback: str,
        final_summary: str = "",
    ) -> str:
        """
        Improve a single generation prompt based on user feedback about the
        generated image. The design is unchanged; only the prompt wording is fixed.

        Args:
            view_type:       "floor_plan" | "front_elevation" | "realistic_render"
            original_prompt: The prompt that produced the bad image.
            feedback:        What the user says is wrong with the image.
            final_summary:   The approved design summary (for context).

        Returns:
            An improved prompt string.
        """
        label = {
            "floor_plan": "Floor Plan",
            "front_elevation": "Front Elevation",
            "realistic_render": "Realistic Render",
        }.get(view_type, view_type)

        improve_prompt = f"""\
A {label} image was generated from the prompt below, but the user says it \
looks wrong. The design itself is correct — only the generation prompt needs \
to be improved so the image model produces a better result.

APPROVED DESIGN SUMMARY:
{final_summary or "(see conversation context)"}

ORIGINAL PROMPT THAT PRODUCED THE WRONG IMAGE:
{original_prompt}

USER FEEDBACK ABOUT WHAT IS WRONG WITH THE IMAGE:
{feedback}

Rewrite the prompt to fix the specific rendering issue the user describes. \
Keep everything else the same. Focus on making the image model render the \
correct result — do not change the design. \
Return only the improved prompt text, nothing else. No JSON, no explanation.
"""

        api_messages = [
            {"role": "system", "content": CHAIRMAN_SYSTEM_PROMPT},
            {"role": "user", "content": improve_prompt},
        ]

        response = await self.client.chat_completion(
            model=self.model,
            messages=api_messages,
            temperature=1.0,
            reasoning_effort=self.reasoning_effort,
        )

        improved = self.client.extract_text(response) or ""
        improved = improved.strip()

        sep = "=" * 70
        print(f"\n{sep}\n[CHAIRMAN PROMPT IMPROVED] {label}\n{sep}\n{improved}\n{sep}\n")

        return improved if improved else original_prompt

    @staticmethod
    def _format_conversation(messages: list[dict]) -> str:
        """Format the full conversation as readable text for the chairman."""
        lines = []
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")

            if role == "system":
                continue

            if isinstance(content, list):
                text_parts = [
                    p.get("text", "") for p in content
                    if isinstance(p, dict) and p.get("type") == "text"
                ]
                content = " ".join(text_parts)

            label = "Client" if role == "user" else "Consultant"
            lines.append(f"{label}: {content}")

        return "\n\n".join(lines)
