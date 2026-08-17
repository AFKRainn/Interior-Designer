"""
Intake agent — takes the brief (plan 10.1).

There is no reviewer behind this any more, so the diligence has to be
structural rather than dispositional. Two mechanisms do that work:

  1. The output CONTRACT. `resolved` and `open` are required fields, so the
     model cannot quietly decide it has nothing to ask.
  2. The COMPLETENESS GATE. Code, not judgement, decides whether the brief is
     ready: a required field must be answered or explicitly defaulted. A
     model that claims "ready" while fields are missing is sent back with the
     list. It cannot talk its way past.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

import config
from app.agents.llm_json import complete_json, user_content_with_images
from app.agents.schemas import INTAKE_FORMAT
from app.prompts.intake_prompts import INTAKE_GATE_NOTE, INTAKE_SYSTEM, INTAKE_TURN
from app.services.openrouter import OpenRouterClient
from app.typology.profiles import checklist, missing_fields

MAX_QUESTIONS = 3


class IntakeError(RuntimeError):
    pass


@dataclass
class Resolved:
    field: str
    value: str
    source: str = "client"

    @property
    def is_default(self) -> bool:
        return self.source == "default"


@dataclass
class IntakeTurn:
    response: str
    status: str
    typology: str
    resolved: list[Resolved] = field(default_factory=list)
    open: list[dict[str, Any]] = field(default_factory=list)
    confidence: float = 0.0
    missing: list[str] = field(default_factory=list)

    @property
    def ready(self) -> bool:
        return self.status == "ready"

    def public(self) -> dict[str, Any]:
        return {
            "response": self.response,
            "status": self.status,
            "typology": self.typology,
            "resolved": [r.__dict__ for r in self.resolved],
            "open": self.open,
            "confidence": self.confidence,
            "missing": self.missing,
        }


class Intake:
    def __init__(
        self,
        client: Optional[OpenRouterClient] = None,
        model: Optional[dict] = None,
    ):
        self.client = client or OpenRouterClient()
        self.model = model or config.INTAKE_MODEL

    async def start(
        self,
        messages: list[dict],
        text: str,
        images: list[dict] | None = None,
    ) -> IntakeTurn:
        messages.append({"role": "system", "content": INTAKE_SYSTEM})
        return await self.reply(messages, text, images)

    async def reply(
        self,
        messages: list[dict],
        text: str,
        images: list[dict] | None = None,
    ) -> IntakeTurn:
        state = _state(messages)
        messages.append(
            {
                "role": "user",
                "content": user_content_with_images(
                    f"{text}\n\n{INTAKE_TURN.format(**state)}", images
                ),
            }
        )
        return await self._run(messages)

    async def _run(self, messages: list[dict], gate_retries: int = 1) -> IntakeTurn:
        result = await complete_json(
            self.client,
            self.model["id"],
            messages,
            reasoning_effort=self.model.get("reasoning_effort", "high"),
            response_format=INTAKE_FORMAT,
        )
        parsed = result["parsed"]
        if not parsed:
            raise IntakeError("intake model returned no JSON")
        messages.append({"role": "assistant", "content": result["text"]})

        turn = _to_turn(parsed)
        turn.missing = [f.key for f in missing_fields(turn.typology, [r.field for r in turn.resolved])]

        # THE GATE. Claiming ready with holes in the brief is not allowed.
        if turn.ready and turn.missing:
            if gate_retries <= 0:
                turn.status = "chat"
                return turn
            messages.append(
                {
                    "role": "user",
                    "content": INTAKE_GATE_NOTE.format(missing=", ".join(turn.missing)),
                }
            )
            return await self._run(messages, gate_retries - 1)

        return turn


def _state(messages: list[dict]) -> dict[str, str]:
    resolved = _resolved_so_far(messages)
    typology = _typology_so_far(messages)
    missing = [f.key for f in missing_fields(typology, list(resolved))]
    return {
        "checklist": checklist(typology),
        "resolved": ", ".join(sorted(resolved)) or "nothing yet",
        "missing": ", ".join(missing) or "nothing",
    }


def _assistant_payloads(messages: list[dict]) -> list[dict]:
    import json

    out = []
    for message in messages:
        if message.get("role") != "assistant":
            continue
        try:
            data = json.loads(message.get("content") or "")
        except (ValueError, TypeError):
            continue
        if isinstance(data, dict):
            out.append(data)
    return out


def _resolved_so_far(messages: list[dict]) -> set[str]:
    keys: set[str] = set()
    for payload in _assistant_payloads(messages):
        for item in payload.get("resolved") or []:
            if isinstance(item, dict) and item.get("field"):
                keys.add(str(item["field"]))
    return keys


def _typology_so_far(messages: list[dict]) -> str:
    typology = "other"
    for payload in _assistant_payloads(messages):
        if payload.get("typology"):
            typology = str(payload["typology"])
    return typology


def _to_turn(parsed: dict) -> IntakeTurn:
    resolved = [
        Resolved(
            field=str(item.get("field", "")).strip(),
            value=str(item.get("value", "")).strip(),
            source=str(item.get("source", "client")).strip() or "client",
        )
        for item in parsed.get("resolved") or []
        if isinstance(item, dict) and item.get("field")
    ]
    questions = [item for item in (parsed.get("open") or []) if isinstance(item, dict)]
    return IntakeTurn(
        response=str(parsed.get("response", "")).strip(),
        status="ready" if parsed.get("status") == "ready" else "chat",
        typology=str(parsed.get("typology") or "other"),
        resolved=resolved,
        open=questions[:MAX_QUESTIONS],
        confidence=float(parsed.get("confidence") or 0.0),
    )


def merge_resolved(history: list[dict], turn: IntakeTurn) -> list[Resolved]:
    """Everything settled across the whole conversation, latest value wins."""
    merged: dict[str, Resolved] = {}
    for payload in _assistant_payloads(history):
        for item in payload.get("resolved") or []:
            if isinstance(item, dict) and item.get("field"):
                merged[str(item["field"])] = Resolved(
                    field=str(item["field"]),
                    value=str(item.get("value", "")),
                    source=str(item.get("source", "client")),
                )
    for item in turn.resolved:
        merged[item.field] = item
    return [merged[key] for key in sorted(merged)]


def compile_brief(resolved: list[Resolved], typology: str) -> str:
    """The brief is compiled from settled facts, not written by the model.

    Prose summaries lose numbers. This cannot.
    """
    lines = [f"Typology: {typology}", ""]
    for item in resolved:
        suffix = "  [system default]" if item.is_default else ""
        lines.append(f"{item.field}: {item.value}{suffix}")
    return "\n".join(lines)
