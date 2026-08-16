"""
Spec author — locked brief → valid Furniture Spec; chat instruction → patched spec.

The model writes JSON. Code validates it. One repair pass on ValidationError.
"""
from __future__ import annotations

import json
import logging

from pydantic import ValidationError

from app.agents.llm_json import complete_json
from app.models.furniture_spec import FurnitureSpec
from app.prompts.spec_prompts import (
    SPEC_FROM_BRIEF_PROMPT,
    SPEC_PATCH_PROMPT,
    SPEC_REPAIR_PROMPT,
    SPEC_SCHEMA_RULES,
)
from app.services.openrouter import OpenRouterClient

logger = logging.getLogger(__name__)

_LAYOUT_TYPE_ALIASES = {
    "l": "L",
    "l-shaped": "L",
    "l_shaped": "L",
    "lshaped": "L",
    "u": "U",
    "u-shaped": "U",
    "u_shaped": "U",
    "ushaped": "U",
    "straight": "straight",
    "galley": "galley",
    "parallel": "galley",
    "custom": "custom",
}


class SpecAuthorError(ValueError):
    """Spec JSON could not be made valid."""


class SpecAuthor:
    def __init__(self, client: OpenRouterClient | None = None):
        from config import BRIEF_MODEL

        self.client = client or OpenRouterClient()
        self.model = BRIEF_MODEL["id"]
        self.reasoning_effort = BRIEF_MODEL.get("reasoning_effort", "high")

    async def from_brief(
        self,
        brief: str,
        conversation: list[dict] | None = None,
    ) -> FurnitureSpec:
        prompt = SPEC_FROM_BRIEF_PROMPT.format(
            schema_rules=SPEC_SCHEMA_RULES,
            brief=brief,
        )
        if conversation:
            prompt += "\n\nCONVERSATION (for context, brief wins if they conflict):\n"
            prompt += _conversation_excerpt(conversation)
        messages = [{"role": "user", "content": prompt}]
        return await self._write_valid_spec(messages, brief_fallback=brief)

    async def patch(self, spec: FurnitureSpec, instruction: str) -> FurnitureSpec:
        payload = spec.model_dump(mode="json")
        prompt = SPEC_PATCH_PROMPT.format(
            schema_rules=SPEC_SCHEMA_RULES,
            spec_json=json.dumps(payload, indent=2),
            instruction=instruction,
        )
        messages = [{"role": "user", "content": prompt}]
        updated = await self._write_valid_spec(
            messages, brief_fallback=spec.brief, keep_id=spec.project_id
        )
        if updated.project_id != spec.project_id:
            updated.project_id = spec.project_id
        if updated.version <= spec.version:
            updated.version = spec.version + 1
        return updated

    async def _write_valid_spec(
        self,
        messages: list[dict],
        brief_fallback: str = "",
        keep_id: str | None = None,
    ) -> FurnitureSpec:
        result = await complete_json(
            self.client, self.model, messages, self.reasoning_effort
        )
        spec, err = try_parse_spec(
            result["parsed"], brief_fallback=brief_fallback, keep_id=keep_id
        )
        if spec is not None:
            return spec

        repair = SPEC_REPAIR_PROMPT.format(
            error=err or "not valid Furniture Spec JSON",
            spec_json=json.dumps(result["parsed"] or {}, indent=2)[:8000],
            schema_rules=SPEC_SCHEMA_RULES,
        )
        repair_messages = messages + [
            {"role": "assistant", "content": json.dumps(result["parsed"])},
            {"role": "user", "content": repair},
        ]
        repaired = await complete_json(
            self.client, self.model, repair_messages, self.reasoning_effort
        )
        spec, err2 = try_parse_spec(
            repaired["parsed"], brief_fallback=brief_fallback, keep_id=keep_id
        )
        if spec is not None:
            return spec
        raise SpecAuthorError(err2 or err or "spec JSON invalid after repair")


def normalize_spec_dict(data: dict) -> dict:
    """Coerce common LLM aliases before Pydantic validation."""
    out = dict(data)
    layout = out.get("layout")
    if isinstance(layout, dict):
        raw_type = str(layout.get("type", "custom")).strip().lower()
        layout = dict(layout)
        layout["type"] = _LAYOUT_TYPE_ALIASES.get(raw_type, layout.get("type", "custom"))
        out["layout"] = layout
    return out


def try_parse_spec(
    data: dict,
    brief_fallback: str = "",
    keep_id: str | None = None,
) -> tuple[FurnitureSpec | None, str | None]:
    if not data:
        return None, "model returned no JSON object"
    payload = normalize_spec_dict(data)
    if keep_id:
        payload["project_id"] = keep_id
    if brief_fallback and not payload.get("brief"):
        payload["brief"] = brief_fallback
    try:
        return FurnitureSpec.model_validate(payload), None
    except ValidationError as exc:
        return None, str(exc)


def _conversation_excerpt(messages: list[dict], limit: int = 12) -> str:
    lines: list[str] = []
    for msg in messages[-limit:]:
        role = msg.get("role", "")
        if role == "system":
            continue
        content = msg.get("content", "")
        if isinstance(content, list):
            texts = [
                p.get("text", "")
                for p in content
                if isinstance(p, dict) and p.get("type") == "text"
            ]
            content = " ".join(texts)
        if not isinstance(content, str):
            continue
        lines.append(f"{role}: {content[:800]}")
    return "\n".join(lines)
