"""
Intake gate and edit routing (plan 10).

These are the mechanisms that replaced the council. They are tested with a
scripted model because what matters is not what a model says on one day — it
is that the system cannot be talked past.
"""
from __future__ import annotations

import json

import pytest

import config
from app.agents.intake import Intake, compile_brief, merge_resolved
from app.agents.schemas import parse_ops
from app.agents.structure import Structure, StructureError
from app.models.ops import OpError, Split
from app.models.paths import resolve
from app.models.spec import SplitAxis
from app.typology.profiles import missing_fields, profile_for
from tests.fake_openrouter import FakeClient
from tests.v2_factory import straight_wall

KITCHEN_KEYS = profile_for("kitchen").keys()


def intake_reply(status="chat", resolved=None, open_=None, typology="kitchen"):
    return {
        "typology": typology,
        "notice": [{"q": "what is it", "a": "a kitchen run"}],
        "resolved": resolved or [],
        "open": open_ or [],
        "confidence": 0.8,
        "response": "text for the client",
        "status": status,
    }


def all_resolved(keys, source="client"):
    return [{"field": key, "value": "stated", "source": source} for key in keys]


# -- the completeness gate ------------------------------------------------


@pytest.mark.asyncio
async def test_the_gate_refuses_a_ready_brief_with_holes_in_it():
    """A model cannot declare itself finished while a maker still has questions."""
    partial = all_resolved(KITCHEN_KEYS[:3])
    client = FakeClient([
        intake_reply(status="ready", resolved=partial),  # claims ready
        intake_reply(status="ready", resolved=partial),  # still claims ready
    ])
    turn = await Intake(client).start([], "a 3 m kitchen run")

    assert turn.status == "chat", "the gate let an incomplete brief through"
    assert turn.missing
    assert set(turn.missing) == set(KITCHEN_KEYS) - {r.field for r in turn.resolved}


@pytest.mark.asyncio
async def test_the_gate_sends_the_missing_fields_back_to_the_model():
    partial = all_resolved(KITCHEN_KEYS[:2])
    client = FakeClient([
        intake_reply(status="ready", resolved=partial),
        intake_reply(status="ready", resolved=all_resolved(KITCHEN_KEYS)),
    ])
    turn = await Intake(client).start([], "a kitchen")

    assert turn.status == "ready"
    assert turn.missing == []
    # the second call was told exactly what was outstanding
    second = client.calls[1]["messages"][-1]["content"]
    assert "Not ready yet" in second
    assert "worktop" in second


@pytest.mark.asyncio
async def test_a_default_counts_as_resolved_but_is_recorded_as_an_assumption():
    resolved = all_resolved(KITCHEN_KEYS[:-1]) + [
        {"field": KITCHEN_KEYS[-1], "value": "12 cm recessed", "source": "default"}
    ]
    client = FakeClient([intake_reply(status="ready", resolved=resolved)])
    messages: list[dict] = []
    turn = await Intake(client).start(messages, "a kitchen")

    assert turn.ready
    merged = merge_resolved(messages, turn)
    defaults = [item for item in merged if item.is_default]
    assert len(defaults) == 1

    brief = compile_brief(merged, turn.typology)
    assert "[system default]" in brief
    assert "Typology: kitchen" in brief


@pytest.mark.asyncio
async def test_intake_asks_for_structured_output_not_politely():
    client = FakeClient([intake_reply()])
    await Intake(client).start([], "hello")
    fmt = client.calls[0]["response_format"]
    assert fmt["type"] == "json_schema"
    assert fmt["json_schema"]["strict"] is True
    required = fmt["json_schema"]["schema"]["required"]
    # ambiguity cannot be quietly skipped: the fields are mandatory
    assert "open" in required and "resolved" in required


@pytest.mark.asyncio
async def test_intake_never_asks_more_than_three_questions_at_once():
    many = [{"field": f, "why": "?", "options": []} for f in KITCHEN_KEYS[:6]]
    client = FakeClient([intake_reply(open_=many)])
    turn = await Intake(client).start([], "a kitchen")
    assert len(turn.open) == 3


def test_profiles_ask_for_what_a_maker_needs():
    assert "worktop" in KITCHEN_KEYS
    assert "appliances" in KITCHEN_KEYS
    assert "door_action" in profile_for("wardrobe").keys()
    assert missing_fields("kitchen", KITCHEN_KEYS) == []


# -- edit routing ---------------------------------------------------------


def edit_reply(**kwargs):
    base = {
        "understanding": "split the top of bay 1 into two doors",
        "targets": ["wall-a/bay-1/row-1"],
        "ops": [{"kind": "split", "path": "wall-a/bay-1/row-1", "axis": "cols", "count": 2}],
        "ambiguities": [],
        "confidence": 0.95,
        "action": "propose",
    }
    base.update(kwargs)
    return base


@pytest.mark.asyncio
async def test_two_doors_next_to_each_other_becomes_one_op():
    """The sentence that started the rewrite, end to end."""
    client = FakeClient([edit_reply()])
    spec = straight_wall()
    decision = await Structure(client).edit(
        spec, "wall-a", "I want two doors next to each other on the top part"
    )

    assert not decision.must_clarify
    assert len(decision.ops) == 1
    assert isinstance(decision.ops[0], Split)
    assert decision.ops[0].axis is SplitAxis.COLS


@pytest.mark.asyncio
async def test_low_confidence_forces_a_question_even_when_the_model_wants_to_act():
    client = FakeClient([edit_reply(confidence=0.4)])
    decision = await Structure(client).edit(straight_wall(), "wall-a", "make it nicer")
    assert decision.must_clarify


@pytest.mark.asyncio
async def test_any_stated_ambiguity_forces_a_question():
    client = FakeClient([
        edit_reply(
            confidence=0.99,
            action="propose",
            ambiguities=[{"question": "which bay?", "options": ["bay-1", "bay-2"]}],
        )
    ])
    decision = await Structure(client).edit(straight_wall(), "wall-a", "widen the tall one")
    assert decision.must_clarify, "a declared ambiguity must beat a confident action"


@pytest.mark.asyncio
async def test_a_proposal_that_will_not_apply_is_retried_then_becomes_a_question():
    impossible = edit_reply(
        understanding="make bay 1 900 cm wide",
        ops=[{"kind": "set_size", "path": "wall-a/bay-1", "size_cm": 900}],
    )
    client = FakeClient([impossible, impossible])
    decision = await Structure(client).edit(straight_wall(), "wall-a", "bay 1 is 900")

    assert decision.must_clarify
    assert "does not fit" in decision.ambiguities[0]["question"]


@pytest.mark.asyncio
async def test_the_spec_is_never_touched_by_an_edit_call():
    client = FakeClient([edit_reply()])
    spec = straight_wall()
    before = spec.model_dump(mode="json")
    await Structure(client).edit(spec, "wall-a", "two doors on top")
    assert spec.model_dump(mode="json") == before


@pytest.mark.asyncio
async def test_the_model_only_sees_paths_that_exist():
    client = FakeClient([edit_reply()])
    await Structure(client).edit(straight_wall(), "wall-a", "change something")
    prompt = client.last_prompt
    assert "wall-a/bay-1/row-1" in prompt
    assert "wall-a/bay-9" not in prompt


@pytest.mark.asyncio
async def test_the_edit_call_runs_at_max_effort():
    client = FakeClient([edit_reply()])
    await Structure(client).edit(straight_wall(), "wall-a", "x")
    assert client.calls[0]["reasoning_effort"] == "max"
    assert client.calls[0]["response_format"]["json_schema"]["strict"] is True


# -- wide op parsing ------------------------------------------------------


def test_nulls_in_a_wide_op_mean_absence():
    ops = parse_ops([
        {"kind": "split", "path": "wall-a/bay-1", "axis": "cols", "count": 2,
         "size_cm": None, "wall_id": None, "ratios": None, "hinge": None}
    ])
    assert len(ops) == 1 and ops[0].kind == "split"


def test_set_front_accepts_the_field_name_models_actually_use():
    ops = parse_ops([{"kind": "set_front", "path": "wall-a/bay-2", "front_type": "glass"}])
    assert ops[0].type.value == "glass"


def test_a_nonsense_op_is_rejected_with_its_position():
    with pytest.raises(OpError, match="op 1"):
        parse_ops([{"kind": "not_an_op"}])


# -- spec authoring -------------------------------------------------------


@pytest.mark.asyncio
async def test_a_broken_spec_is_repaired_from_the_validator_message():
    broken = {
        "name": "x", "units": "cm",
        "layout": {"type": "straight", "walls": [{"id": "wall-a", "length": 300, "sequence": 0}]},
        "walls": [{"id": "wall-a", "height": 220, "depth": 60, "bays": [
            {"id": "bay-1", "size_cm": 100, "front": {"type": "door"}},
        ]}],
    }
    fixed = json.loads(json.dumps(broken))
    fixed["walls"][0]["bays"][0] = {"id": "bay-1", "flex": 1, "front": {"type": "door"}}

    client = FakeClient([broken, fixed])
    spec = await Structure(client).build_spec("a 3 m run with one door")

    assert spec.walls[0].bays[0].flex == 1
    # the repair prompt carried the validator's own words
    assert "Either make one child flex" in client.calls[1]["messages"][-1]["content"]


@pytest.mark.asyncio
async def test_two_failed_attempts_surface_rather_than_looping():
    broken = {"layout": {"walls": []}, "walls": []}
    client = FakeClient([broken, broken])
    with pytest.raises(StructureError):
        await Structure(client).build_spec("nonsense")
