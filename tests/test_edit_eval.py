"""
The evaluation set has to be trustworthy before its score means anything.

These tests check the SET and the HARNESS, not a model: every "should act"
case must name an operation that genuinely applies to the spec, and the
scorer must classify the four outcomes correctly. Running it against a live
model is `python -m scripts.run_edit_eval`.
"""
from __future__ import annotations

import pytest

from app.agents.schemas import parse_ops
from app.agents.structure import Structure
from app.models.ops import apply_ops
from tests.eval.harness import Report, load, op_matches, score_case
from tests.fake_openrouter import FakeClient

EVAL = load()


def test_the_set_covers_both_halves_of_the_problem():
    clear = [c for c in EVAL.cases if c.should_act]
    vague = [c for c in EVAL.cases if not c.should_act]
    assert len(clear) >= 12, "not enough clear cases to measure correct-op rate"
    assert len(vague) >= 5, "not enough ambiguous cases to measure clarification"
    assert len(EVAL.cases) >= 20


def test_the_regression_that_started_the_rewrite_is_in_the_set():
    case = next(c for c in EVAL.cases if c.id == "two-doors-top")
    assert "two doors next to each other" in case.utterance
    assert case.ops[0]["kind"] == "split"
    assert case.ops[0]["axis"] == "cols"


def test_case_ids_are_unique():
    ids = [c.id for c in EVAL.cases]
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize(
    "case", [c for c in EVAL.cases if c.should_act and c.ops], ids=lambda c: c.id
)
def test_every_expected_op_actually_applies(case):
    """A target the spec cannot satisfy would make the eval unpassable."""
    spec = EVAL.spec()
    ops = parse_ops([dict(op) for op in case.ops])
    apply_ops(spec, ops)  # raises if the op is not valid against the spec


def test_ambiguous_cases_name_no_operations():
    for case in EVAL.cases:
        if not case.should_act:
            assert not case.ops, f"{case.id} expects a question but lists ops"


def test_partial_expectations_match_on_the_fields_that_matter():
    ops = parse_ops([{"kind": "split", "path": "wall-a/bay-1/row-1", "axis": "cols", "count": 2}])
    assert op_matches({"kind": "split", "axis": "cols"}, ops[0])
    assert not op_matches({"kind": "split", "axis": "rows"}, ops[0])
    assert not op_matches({"kind": "merge"}, ops[0])


def test_the_scorer_separates_all_four_outcomes():
    clear = next(c for c in EVAL.cases if c.id == "bay-width")
    vague = next(c for c in EVAL.cases if c.id == "ambiguous-the-big-one")
    right = parse_ops([{"kind": "set_size", "path": "wall-a/bay-2", "size_cm": 120}])
    wrong = parse_ops([{"kind": "set_size", "path": "wall-a/bay-1", "size_cm": 120}])

    assert score_case(clear, clarified=False, ops=right) == "correct"
    assert score_case(clear, clarified=False, ops=wrong) == "wrong_op"
    assert score_case(clear, clarified=True, ops=[]) == "false_clarify"
    assert score_case(vague, clarified=True, ops=[]) == "correct"
    assert score_case(vague, clarified=False, ops=right) == "missed_clarify"


def test_the_report_computes_rates():
    report = Report()
    for case in EVAL.cases:
        report.add(case.id, "correct")
    assert report.rate("correct") == 1.0
    text = report.summary(EVAL)
    assert "correct-op rate" in text
    assert "false-clarify rate" in text


@pytest.mark.asyncio
async def test_a_perfect_model_scores_perfectly_through_the_real_agent():
    """End-to-end harness check: route every case through Structure itself."""
    report = Report()
    for case in EVAL.cases:
        spec = EVAL.spec()
        if case.should_act:
            reply = {
                "understanding": f"applying: {case.utterance}",
                "targets": [],
                "ops": [dict(op) for op in case.ops],
                "ambiguities": [],
                "confidence": 0.95,
                "action": "propose",
            }
        else:
            reply = {
                "understanding": "",
                "targets": [],
                "ops": [],
                "ambiguities": [{"question": "which one?", "options": ["a", "b"]}],
                "confidence": 0.3,
                "action": "clarify",
            }
        decision = await Structure(FakeClient([reply])).edit(spec, EVAL.wall_id, case.utterance)
        report.add(case.id, score_case(case, decision.must_clarify, decision.ops))

    assert report.rate("correct") == 1.0, report.summary(EVAL)
