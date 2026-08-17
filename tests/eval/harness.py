"""
Scoring for the edit-agent evaluation set (plan Phase 5).

Three numbers matter, and the third is the one everybody forgets:

  correct-op rate       did it emit the right operation when the request was clear
  clarify-when-needed   did it ask when the request was genuinely ambiguous
  false-clarify rate    did it ask when it should just have acted

Optimising the middle number alone produces an agent that asks about
everything, which is how the build-1 consultant loop became unbearable. The
research this design rests on reports higher coverage with FEWER questions
(plan.txt section 15), so both directions are measured.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.models.ops import Op
from app.models.spec import Spec, build_spec

CASES_FILE = Path(__file__).parent / "edit_cases.json"
SPECS_DIR = Path(__file__).resolve().parents[1] / "golden" / "specs"


@dataclass
class Case:
    id: str
    utterance: str
    expect: str  # "ops" | "clarify"
    ops: list[dict[str, Any]] = field(default_factory=list)
    note: str = ""

    @property
    def should_act(self) -> bool:
        return self.expect == "ops"


@dataclass
class EvalSet:
    spec_name: str
    wall_id: str
    cases: list[Case]

    def spec(self) -> Spec:
        data = json.loads((SPECS_DIR / f"{self.spec_name}.json").read_text(encoding="utf-8"))
        return build_spec(data)


def load() -> EvalSet:
    raw = json.loads(CASES_FILE.read_text(encoding="utf-8"))
    return EvalSet(
        spec_name=raw["spec"],
        wall_id=raw["wall_id"],
        cases=[
            Case(
                id=item["id"],
                utterance=item["utterance"],
                expect=item["expect"],
                ops=item.get("ops", []),
                note=item.get("note", ""),
            )
            for item in raw["cases"]
        ],
    )


def op_matches(expected: dict[str, Any], actual: Op) -> bool:
    """Expected ops are partial: only the fields written have to agree.

    The point is whether the agent chose the right MOVE, not whether it
    guessed an id we happened to write down.
    """
    got = actual.model_dump(mode="json")
    for key, value in expected.items():
        if key not in got:
            return False
        if isinstance(value, (int, float)) and isinstance(got[key], (int, float)):
            if abs(float(value) - float(got[key])) > 0.01:
                return False
        elif got[key] != value:
            return False
    return True


def score_case(case: Case, clarified: bool, ops: list[Op]) -> str:
    """One of: correct, wrong_op, missed_clarify, false_clarify."""
    if case.should_act:
        if clarified:
            return "false_clarify"
        if not case.ops:
            return "correct" if ops else "wrong_op"
        matched = all(
            any(op_matches(expected, actual) for actual in ops) for expected in case.ops
        )
        return "correct" if matched else "wrong_op"
    return "correct" if clarified else "missed_clarify"


@dataclass
class Report:
    outcomes: dict[str, str] = field(default_factory=dict)

    def add(self, case_id: str, outcome: str) -> None:
        self.outcomes[case_id] = outcome

    def rate(self, *outcomes: str) -> float:
        if not self.outcomes:
            return 0.0
        hits = sum(1 for value in self.outcomes.values() if value in outcomes)
        return hits / len(self.outcomes)

    def summary(self, evalset: EvalSet) -> str:
        clear = [c for c in evalset.cases if c.should_act]
        vague = [c for c in evalset.cases if not c.should_act]
        correct_ops = sum(1 for c in clear if self.outcomes.get(c.id) == "correct")
        asked = sum(1 for c in vague if self.outcomes.get(c.id) == "correct")
        false_asks = sum(1 for c in clear if self.outcomes.get(c.id) == "false_clarify")

        lines = [
            f"correct-op rate       {correct_ops}/{len(clear)}",
            f"clarify-when-needed   {asked}/{len(vague)}",
            f"false-clarify rate    {false_asks}/{len(clear)}",
            "",
        ]
        for case in evalset.cases:
            outcome = self.outcomes.get(case.id, "not run")
            mark = "ok  " if outcome == "correct" else "FAIL"
            lines.append(f"  {mark} {case.id:<26} {outcome}")
        return "\n".join(lines)
