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

━━━ INSTRUCTIONS FOR EACH PROMPT ━━━

1. FLOOR PLAN
Start with: "Generate a floor plan of [describe the overall layout from above: \
number of bays, their left-to-right arrangement, walls if multi-wall, \
overall footprint shape]."
Then add: "Black and white. Lines only. Top-down 2D view. No perspective."
Then handle dimensions: if the summary includes explicit measurements, add \
"Label these dimensions: [list each one by bay or element]." \
If no measurements were given, add "No dimensions. No numbers. No text labels."

2. FRONT ELEVATION
Start with: "Generate a front elevation drawing of [describe the full design \
from left to right, bay by bay: for each bay state exactly what it shows — \
drawer section, panel door, glass door, open shelf, decorative column — \
its approximate proportional height and width, plus all visible details: \
cornice or top trim style, any grooves or carved profiles on sides, hardware \
type and position, shelf lines inside open sections, base or plinth style]."
Then add: "Black and white. 2D front view. Minimal text — only label things \
like 'open shelf' or 'glass' where a word genuinely helps."

3. REALISTIC RENDER
Start with: "Generate a photorealistic 3D image of [describe the full piece: \
material of each surface, color and finish, hardware style, top trim \
treatment, base treatment, overall proportions, number and arrangement \
of bays]."
Then add context: "[where it sits — e.g. mounted on a wall / freestanding \
on a floor / built-in kitchen installation]."
Then add: "Natural lighting. Clean neutral background."

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
