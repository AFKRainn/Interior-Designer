"""
Chairman Agent — synthesizes council deliberation into a DSD.

The Chairman takes the final interpretations from all three council
members and produces a single, authoritative Design Specification Document.
"""
import json
import logging
from typing import Optional

from app.models.council_state import CouncilState
from app.models.dsd import (
    DesignSpecificationDocument,
    DesignType,
    ViewSpec,
    ViewType,
    Dimensions,
    StyleSpec,
    MaterialSpec,
    ColorSpec,
    StructuralElement,
    ContextSpec,
)
from app.services.openrouter import OpenRouterClient

logger = logging.getLogger(__name__)


class Chairman:
    """
    Synthesizes the council's deliberation into a final DSD.

    Uses one of the council models (configured as CHAIRMAN_MODEL)
    to merge all three final interpretations.
    """

    def __init__(self, client: OpenRouterClient | None = None):
        from config import CHAIRMAN_MODEL, COUNCIL_MODELS

        self.client = client or OpenRouterClient()
        self.chairman_key = CHAIRMAN_MODEL
        self.chairman_model = COUNCIL_MODELS[CHAIRMAN_MODEL]["id"]

    async def synthesize(
        self, state: CouncilState, project_id: str
    ) -> DesignSpecificationDocument:
        """
        Synthesize the council's Round 3 (convergence) responses
        into a single Design Specification Document.
        """
        from app.prompts.council_prompts import CHAIRMAN_SYNTHESIS_PROMPT

        # Collect Round 3 (final) responses
        if len(state.rounds) < 3:
            raise ValueError("Council must complete 3 rounds before synthesis")

        round3 = state.rounds[2]
        finals = {}
        for resp in round3.responses:
            if not resp.error:
                finals[resp.member_id] = resp.response_text

        # Build the synthesis prompt
        prompt = CHAIRMAN_SYNTHESIS_PROMPT.format(
            claude_final=finals.get("claude", "No response"),
            gpt_final=finals.get("gpt", "No response"),
            gemini_final=finals.get("gemini", "No response"),
        )

        # Query the chairman
        response = await self.client.chat_completion(
            model=self.chairman_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=16384,
        )

        # Parse the response — two parts: JSON DSD + view generation prompts
        raw_text = self.client.extract_text(response) or ""
        logger.info(f"Chairman raw response (first 1200 chars): {raw_text[:1200]}")

        parsed = self._extract_dict_json(raw_text)

        if parsed is None:
            raise ValueError(
                "Chairman failed to produce a valid JSON object. "
                f"Raw response: {raw_text[:500]}"
            )

        # Parse the separate GENERATION_PROMPTS section (outside the JSON)
        view_prompts = self._extract_view_prompts(raw_text)
        if view_prompts:
            logger.info(
                f"Extracted {len(view_prompts)} view generation prompt(s): "
                f"{list(view_prompts.keys())}"
            )
        else:
            logger.warning("No view generation prompts found in chairman response.")

        state.chairman_id = self.chairman_key
        dsd = self._build_dsd(parsed, project_id)

        # Attach council-authored generation prompts to their ViewSpecs
        if view_prompts:
            for view_spec in dsd.views_to_generate:
                prompt_content = view_prompts.get(view_spec.label, "")
                if prompt_content:
                    view_spec.generation_prompt = prompt_content
                    logger.info(
                        f"Attached generation prompt to '{view_spec.label}' "
                        f"({len(prompt_content)} chars)"
                    )
                else:
                    logger.warning(
                        f"No generation prompt found for view '{view_spec.label}'. "
                        f"Will use fallback template."
                    )

        return dsd

    @staticmethod
    def _extract_view_prompts(text: str) -> dict[str, str]:
        """
        Parse the GENERATION_PROMPTS_START ... GENERATION_PROMPTS_END section
        from the chairman's raw response.

        Format expected:
            GENERATION_PROMPTS_START
            VIEW_PROMPT: Floor Plan
            [content lines]
            VIEW_PROMPT_END

            VIEW_PROMPT: Front Elevation — Wall A
            [content lines]
            VIEW_PROMPT_END
            GENERATION_PROMPTS_END

        Returns:
            Dict mapping view label -> generation prompt text.
            Empty dict if the section is not found.
        """
        import re

        prompts: dict[str, str] = {}

        # Find the delimited section
        section_match = re.search(
            r"GENERATION_PROMPTS_START\s*(.*?)\s*GENERATION_PROMPTS_END",
            text,
            re.DOTALL,
        )
        if not section_match:
            # Try without END marker (model may have been cut off)
            section_match = re.search(
                r"GENERATION_PROMPTS_START\s*(.*)",
                text,
                re.DOTALL,
            )
            if not section_match:
                return prompts

        section_text = section_match.group(1)

        # Split into individual VIEW_PROMPT blocks
        blocks = re.split(r"VIEW_PROMPT:\s*", section_text)
        for block in blocks:
            if not block.strip():
                continue

            # First line is the label; content goes until VIEW_PROMPT_END or next block
            lines = block.split("\n", 1)
            label = lines[0].strip().strip('"').strip("'")
            if not label:
                continue

            content_raw = lines[1] if len(lines) > 1 else ""

            # Strip the VIEW_PROMPT_END marker and trailing whitespace
            content = re.sub(r"\s*VIEW_PROMPT_END\s*$", "", content_raw, flags=re.DOTALL)
            content = content.strip()

            if label and content:
                prompts[label] = content

        return prompts

    @staticmethod
    def _extract_dict_json(text: str) -> dict | None:
        """
        Extract the first JSON **object** (dict) from text, ignoring arrays.
        Tries multiple strategies:
          1. JSON object inside a markdown code block
          2. The largest top-level { ... } in the raw text
          3. Direct parse of the whole text (only if result is a dict)
        """
        if not text:
            return None

        # Strategy 1: JSON object inside ```json ... ``` code block
        import re
        # Match code blocks with or without closing fence (handles truncation)
        code_blocks = re.findall(
            r"```(?:json)?\s*\n(.*?)(?:\n```|$)", text, re.DOTALL
        )
        for block in code_blocks:
            block = block.strip()
            if block.startswith("{"):
                try:
                    candidate = json.loads(block)
                    if isinstance(candidate, dict):
                        return candidate
                except json.JSONDecodeError:
                    pass

        # Strategy 2: Find the largest { ... } in the raw text
        best = None
        best_len = 0
        i = 0
        while i < len(text):
            if text[i] == "{":
                depth = 0
                for j in range(i, len(text)):
                    if text[j] == "{":
                        depth += 1
                    elif text[j] == "}":
                        depth -= 1
                    if depth == 0:
                        snippet = text[i : j + 1]
                        if len(snippet) > best_len:
                            try:
                                candidate = json.loads(snippet)
                                if isinstance(candidate, dict):
                                    best = candidate
                                    best_len = len(snippet)
                            except json.JSONDecodeError:
                                pass
                        i = j + 1
                        break
                else:
                    break  # unmatched brace, stop
            else:
                i += 1

        if best is not None:
            return best

        # Strategy 3: Direct parse (only accept dicts)
        try:
            candidate = json.loads(text)
            if isinstance(candidate, dict):
                return candidate
        except json.JSONDecodeError:
            pass

        return None

    def _build_dsd(self, data: dict, project_id: str) -> DesignSpecificationDocument:
        """
        Build a DSD from the chairman's parsed JSON output.
        Handles missing fields gracefully with defaults.
        """
        # Map the design type
        type_str = data.get("type", "furniture").lower()
        try:
            design_type = DesignType(type_str)
        except ValueError:
            design_type = DesignType.FURNITURE

        # Map views — expects list of dicts with type/label/description/generation_prompt
        views_raw = data.get("views_to_generate", data.get("views_recommended", []))
        views: list[ViewSpec] = []
        for v in views_raw:
            if isinstance(v, dict):
                vtype = v.get("type", "")
                try:
                    ViewType(vtype)  # validate type
                except ValueError:
                    logger.warning(f"Unknown view type from chairman: {vtype}")
                    continue

                views.append(ViewSpec(
                    type=vtype,
                    label=v.get("label", vtype.replace("_", " ").title()),
                    description=v.get("description", ""),
                    # generation_prompt is assigned after _build_dsd returns,
                    # from the parsed GENERATION_PROMPTS section
                    generation_prompt="",
                ))
            elif isinstance(v, str):
                # Legacy format: plain string like "floor_plan"
                try:
                    ViewType(v)
                except ValueError:
                    logger.warning(f"Unknown view type from chairman: {v}")
                    continue
                views.append(ViewSpec(
                    type=v,
                    label=v.replace("_", " ").title(),
                    description="",
                    generation_prompt="",
                ))
            # Note: generation_prompt is populated after _build_dsd returns

        # Build dimensions
        dims_data = data.get("dimensions", {})
        dimensions = Dimensions(
            width=dims_data.get("width"),
            height=dims_data.get("height"),
            depth=dims_data.get("depth"),
            notes=dims_data.get("notes"),
        )

        # Build style
        style_data = data.get("style", {})
        style = StyleSpec(
            aesthetic=style_data.get("aesthetic", ""),
            era=style_data.get("era", ""),
            influences=style_data.get("influences", []),
        )

        # Build materials
        materials = []
        for m in data.get("materials", []):
            if isinstance(m, dict):
                materials.append(MaterialSpec(
                    name=m.get("name", "unknown"),
                    usage=m.get("usage", ""),
                    finish=m.get("finish", ""),
                ))

        # Build colors
        colors_data = data.get("colors", {})
        colors = ColorSpec(
            primary=colors_data.get("primary"),
            secondary=colors_data.get("secondary"),
            accent=colors_data.get("accent"),
            notes=colors_data.get("notes"),
        )

        # Build structural elements
        elements = []
        for e in data.get("structural_elements", []):
            if isinstance(e, dict):
                elem_dims = None
                if "dimensions" in e and isinstance(e["dimensions"], dict):
                    elem_dims = Dimensions(**e["dimensions"])
                elements.append(StructuralElement(
                    name=e.get("name", "unnamed"),
                    description=e.get("description", ""),
                    dimensions=elem_dims,
                    material=e.get("material"),
                    position=e.get("position", ""),
                    count=e.get("count", 1),
                ))

        # Build context
        ctx_data = data.get("context", {})
        context = ContextSpec(
            placement=ctx_data.get("placement", ""),
            surroundings=ctx_data.get("surroundings", ""),
            scale_reference=ctx_data.get("scale_reference", ""),
        )

        return DesignSpecificationDocument(
            project_id=project_id,
            version=1,
            type=design_type,
            name=data.get("name", "Untitled Design"),
            description=data.get("description", ""),
            dimensions=dimensions,
            style=style,
            materials=materials,
            colors=colors,
            structural_elements=elements,
            spatial_layout=data.get("spatial_layout", ""),
            context=context,
            views_to_generate=views,
            generation_notes=data.get("generation_notes", ""),
        )
