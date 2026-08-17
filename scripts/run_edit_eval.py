"""
Run the edit-agent evaluation set against the real model.

    python -m scripts.run_edit_eval           # every case
    python -m scripts.run_edit_eval two-doors # one case by id prefix

Needs OPENROUTER_API_KEY. Costs real money: 20 calls to a max-effort model.
The numbers it prints are the ones plan.txt Phase 5 asks for.
"""
from __future__ import annotations

import asyncio
import sys

from app.agents.structure import Structure
from tests.eval.harness import Report, load, score_case


async def main(filter_prefix: str = "") -> int:
    evalset = load()
    cases = [c for c in evalset.cases if c.id.startswith(filter_prefix)]
    if not cases:
        print(f"no case matches {filter_prefix!r}")
        return 1

    structure = Structure()
    report = Report()
    print(f"{len(cases)} case(s) against {evalset.spec_name}/{evalset.wall_id}\n")

    for case in cases:
        spec = evalset.spec()
        try:
            decision = await structure.edit(spec, evalset.wall_id, case.utterance)
        except Exception as err:  # a crashed call is a failed case, not a crash
            report.add(case.id, "error")
            print(f"  ERR  {case.id}: {err}")
            continue

        outcome = score_case(case, decision.must_clarify, decision.ops)
        report.add(case.id, outcome)
        mark = "ok  " if outcome == "correct" else "FAIL"
        detail = (
            f"asked: {decision.ambiguities[0]['question']}"
            if decision.must_clarify and decision.ambiguities
            else ", ".join(op.kind for op in decision.ops) or "nothing"
        )
        print(f"  {mark} {case.id:<26} {outcome:<15} {detail}")
        if outcome != "correct":
            print(f"       understanding: {decision.understanding}")

    print("\n" + report.summary(evalset))
    return 0 if report.rate("correct") == 1.0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "")))
