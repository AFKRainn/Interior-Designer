"""
Structure agent — brief to spec, and utterance to edit ops (plan 10.2, 10.3).

The hard reasoning job, so it runs on the strongest model at max effort. It
still never computes geometry: it chooses structure and operations, and code
decides whether they fit.

The edit path is the fix for build 1's worst failure mode. There, every edit
asked the model to "return the FULL updated spec JSON", so a misunderstanding
rewrote the document with nothing to review. Here an edit is a set of named
ops with a restatement attached, and either it is confident enough to propose
(and the user sees it drawn before it lands) or it must ask.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Optional

import config
from app.agents.llm_json import complete_json
from app.agents.schemas import EDIT_FORMAT, parse_ops
from app.models.ops import Op, OpError, apply_ops
from app.models.paths import describe
from app.models.spec import Spec, SpecError, build_spec
from app.prompts.structure_prompts import (
    EDIT_RETRY,
    EDIT_SYSTEM,
    EDIT_USER,
    OPENING_TREE_RULES,
    SPEC_FROM_BRIEF,
    SPEC_REPAIR,
)
from app.services.openrouter import OpenRouterClient


class StructureError(RuntimeError):
    pass


@dataclass
class EditDecision:
    """What the agent wants to do, and whether it is allowed to do it."""

    understanding: str
    action: str
    confidence: float
    ops: list[Op] = field(default_factory=list)
    ambiguities: list[dict[str, Any]] = field(default_factory=list)
    targets: list[str] = field(default_factory=list)
    error: str = ""

    @property
    def must_clarify(self) -> bool:
        """Three independent reasons to ask instead of act (plan 10.3)."""
        return (
            self.action == "clarify"
            or bool(self.ambiguities)
            or self.confidence < config.CLARIFY_THRESHOLD
            or not self.ops
        )

    def public(self) -> dict[str, Any]:
        return {
            "understanding": self.understanding,
            "action": "clarify" if self.must_clarify else "propose",
            "confidence": self.confidence,
            "ambiguities": self.ambiguities,
            "targets": self.targets,
            "ops": [op.model_dump(mode="json") for op in self.ops],
            "error": self.error,
        }


class Structure:
    def __init__(
        self,
        client: Optional[OpenRouterClient] = None,
        model: Optional[dict] = None,
    ):
        self.client = client or OpenRouterClient()
        self.model = model or config.STRUCTURE_MODEL

    @property
    def _effort(self) -> str:
        return self.model.get("reasoning_effort", "max")

    # -- brief -> spec ----------------------------------------------------

    async def build_spec(self, brief: str, repairs: int = 1) -> Spec:
        """Author a spec, then repair once against the validator's own words.

        The recursive opening tree is not expressible in strict json_schema
        across providers, so this uses json_object mode and leans on the
        invariants instead. The validator's message is written to be readable
        by exactly this loop (progress D10).
        """
        prompt = SPEC_FROM_BRIEF.format(rules=OPENING_TREE_RULES, brief=brief)
        messages = [{"role": "user", "content": prompt}]

        last_error = ""
        attempt_json = "{}"
        for _ in range(repairs + 1):
            result = await complete_json(
                self.client,
                self.model["id"],
                messages,
                reasoning_effort=self._effort,
                response_format={"type": "json_object"},
            )
            parsed = result["parsed"]
            if parsed:
                attempt_json = json.dumps(parsed, indent=2)
                try:
                    return build_spec(parsed)
                except SpecError as err:
                    last_error = str(err)
            else:
                last_error = "the model returned no JSON object"

            messages = [
                {
                    "role": "user",
                    "content": SPEC_REPAIR.format(
                        error=last_error,
                        spec_json=attempt_json,
                        rules=OPENING_TREE_RULES,
                    ),
                }
            ]

        raise StructureError(f"could not build a valid spec: {last_error}")

    # -- utterance -> ops -------------------------------------------------

    async def edit(
        self,
        spec: Spec,
        wall_id: str,
        utterance: str,
        selection: str | None = None,
        retries: int = 1,
    ) -> EditDecision:
        inventory = _inventory(spec, wall_id)
        messages = [
            {"role": "system", "content": EDIT_SYSTEM},
            {
                "role": "user",
                "content": EDIT_USER.format(
                    wall_id=wall_id,
                    selection=selection or "nothing selected",
                    inventory=inventory,
                    materials=_flat(spec.materials.model_dump()),
                    hardware=_flat(spec.hardware.model_dump()),
                    utterance=utterance.strip(),
                ),
            },
        ]

        decision = await self._decide(messages)
        if decision.must_clarify:
            return decision

        # A proposal that will not apply is not a proposal. Try once more
        # with the rejection, then fall back to asking.
        for _ in range(retries):
            try:
                apply_ops(spec, decision.ops)
                return decision
            except OpError as err:
                messages.append({"role": "user", "content": EDIT_RETRY.format(error=err)})
                decision = await self._decide(messages)
                decision.error = str(err)
                if decision.must_clarify:
                    return decision

        try:
            apply_ops(spec, decision.ops)
        except OpError as err:
            return EditDecision(
                understanding=decision.understanding,
                action="clarify",
                confidence=0.0,
                ambiguities=[
                    {
                        "question": f"That change does not fit: {err}. How should it be resolved?",
                        "options": [],
                    }
                ],
                error=str(err),
            )
        return decision

    async def _decide(self, messages: list[dict]) -> EditDecision:
        result = await complete_json(
            self.client,
            self.model["id"],
            messages,
            reasoning_effort=self._effort,
            response_format=EDIT_FORMAT,
        )
        parsed = result["parsed"]
        if not parsed:
            raise StructureError("edit model returned no JSON")
        messages.append({"role": "assistant", "content": result["text"]})

        ambiguities = [a for a in (parsed.get("ambiguities") or []) if isinstance(a, dict)]
        try:
            ops = parse_ops(parsed.get("ops") or [])
        except OpError as err:
            return EditDecision(
                understanding=str(parsed.get("understanding", "")),
                action="clarify",
                confidence=0.0,
                ambiguities=ambiguities,
                targets=[str(t) for t in (parsed.get("targets") or [])],
                error=str(err),
            )

        return EditDecision(
            understanding=str(parsed.get("understanding", "")).strip(),
            action="clarify" if parsed.get("action") == "clarify" else "propose",
            confidence=float(parsed.get("confidence") or 0.0),
            ops=ops,
            ambiguities=ambiguities,
            targets=[str(t) for t in (parsed.get("targets") or [])],
        )


def _inventory(spec: Spec, wall_id: str) -> str:
    """Only real paths, so the model cannot target something that is not there."""
    rows = describe(spec, wall_id)
    lines = []
    for row in rows:
        what = row["front"] or f"{row['split']} split"
        label = f" \"{row['label']}\"" if row["label"] else ""
        lines.append(f"  {row['path']}{label} — {what}, {row['w_cm']} x {row['h_cm']} cm")
    return "\n".join(lines) or "  (no bays yet)"


def _flat(data: dict) -> str:
    bits = [f"{k}={v}" for k, v in data.items() if v]
    return ", ".join(bits) or "unset"
