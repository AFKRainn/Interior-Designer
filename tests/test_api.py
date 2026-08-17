"""
The HTTP surface (plan 12).

The rule under test throughout: every mutation goes through an op, and no
endpoint accepts a spec. That is what stops a model — or a bug — rewriting
the document behind the user's back the way build 1 did.
"""
from __future__ import annotations

import base64

import pytest
from fastapi.testclient import TestClient

from app.api.main import app, get_image_client, get_intake, get_structure
from app.editor import session as session_store
from app.planner.views import plan_views
from tests.fake_openrouter import FakeClient
from tests.test_agents import all_resolved, edit_reply, intake_reply, KITCHEN_KEYS
from tests.v2_factory import l_kitchen

PNG = base64.b64encode(b"\x89PNG\r\n\x1a\nfake").decode("ascii")


@pytest.fixture(autouse=True)
def clean_sessions():
    session_store.SESSIONS.clear()
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def client():
    return TestClient(app)


def demo(client: TestClient) -> dict:
    response = client.post("/api/session/demo")
    assert response.status_code == 200
    return response.json()


def test_health_reports_the_models_in_use(client):
    body = client.get("/api/health").json()
    assert body["ok"] is True
    assert "terra" in body["structure_model"]


def test_a_new_session_starts_in_the_brief(client):
    body = client.post("/api/session").json()
    assert body["phase"] == "brief"
    assert body["spec"] is None
    assert body["can_undo"] is False


def test_the_demo_gives_a_working_spec_without_an_api_key(client):
    body = demo(client)
    assert body["phase"] == "edit"
    assert [w["id"] for w in body["spec"]["layout"]["walls"]] == ["wall-a", "wall-b"]


# -- editing --------------------------------------------------------------


def test_ops_apply_and_bump_the_version(client):
    body = demo(client)
    before = body["spec"]["version"]
    updated = client.post(
        f"/api/session/{body['id']}/ops",
        json={"ops": [{"kind": "set_label", "path": "wall-a/bay-1", "label": "Sink"}]},
    ).json()
    assert updated["spec"]["version"] == before + 1
    assert updated["spec"]["walls"][0]["bays"][0]["label"] == "Sink"
    assert updated["can_undo"] is True


def test_an_impossible_op_is_refused_and_changes_nothing(client):
    body = demo(client)
    response = client.post(
        f"/api/session/{body['id']}/ops",
        json={"ops": [{"kind": "set_size", "path": "wall-a/bay-1", "size_cm": 9000}]},
    )
    assert response.status_code == 422
    assert "available" in response.json()["detail"]
    assert client.get(f"/api/session/{body['id']}").json()["spec"]["version"] == body["spec"]["version"]


def test_preview_solves_the_change_without_committing_it(client):
    body = demo(client)
    preview = client.post(
        f"/api/session/{body['id']}/ops/preview",
        json={"ops": [{"kind": "split", "path": "wall-a/bay-1", "axis": "cols", "count": 2}]},
    ).json()

    assert "wall-a/bay-1/col-1" in preview["diff"]
    assert preview["diff"]["wall-a/bay-1/col-1"] == "added"
    # nothing landed
    assert client.get(f"/api/session/{body['id']}").json()["spec"]["version"] == body["spec"]["version"]


def test_undo_restores_the_previous_version(client):
    body = demo(client)
    client.post(
        f"/api/session/{body['id']}/ops",
        json={"ops": [{"kind": "set_label", "path": "wall-a/bay-1", "label": "Sink"}]},
    )
    restored = client.post(f"/api/session/{body['id']}/undo").json()
    assert restored["spec"]["walls"][0]["bays"][0]["label"] == ""
    assert restored["can_undo"] is False


def test_undo_with_no_history_says_so(client):
    body = demo(client)
    assert client.post(f"/api/session/{body['id']}/undo").status_code == 409


def test_there_is_no_endpoint_that_accepts_a_spec(client):
    """Build 1's edit path was 'return the whole document'. It is gone."""
    routes = {route.path for route in app.routes}
    assert not any(path.endswith("/spec") for path in routes)
    assert "/api/session/{session_id}/spec/patch" not in routes


# -- chat editing ---------------------------------------------------------


def test_a_confident_edit_comes_back_as_a_preview_not_a_change(client):
    from app.agents.structure import Structure

    # bay-1 of the demo L-kitchen is a single door, so splitting it into a
    # pair is the two-doors request against this spec
    app.dependency_overrides[get_structure] = lambda: Structure(
        FakeClient([
            edit_reply(
                understanding="split bay-1 into two doors side by side",
                targets=["wall-a/bay-1"],
                ops=[{"kind": "split", "path": "wall-a/bay-1", "axis": "cols", "count": 2}],
            )
        ])
    )
    body = demo(client)
    response = client.post(
        f"/api/session/{body['id']}/edit",
        json={"utterance": "two doors next to each other on the top part", "wall_id": "wall-a"},
    ).json()

    assert response["decision"]["action"] == "propose"
    assert response["decision"]["preview"]["diff"]
    # the real spec is untouched until the user confirms
    assert response["session"]["spec"]["version"] == body["spec"]["version"]


def test_an_unclear_edit_asks_instead_of_acting(client):
    from app.agents.structure import Structure

    app.dependency_overrides[get_structure] = lambda: Structure(
        FakeClient([
            edit_reply(
                confidence=0.3,
                action="clarify",
                ops=[],
                ambiguities=[{"question": "Which bay do you mean?", "options": ["bay-1", "bay-2"]}],
            )
        ])
    )
    body = demo(client)
    response = client.post(
        f"/api/session/{body['id']}/edit",
        json={"utterance": "make the big one wider"},
    ).json()

    assert response["decision"]["action"] == "clarify"
    assert "preview" not in response["decision"]
    assert response["session"]["chat"][-1]["text"] == "Which bay do you mean?"


# -- intake ---------------------------------------------------------------


def test_the_brief_endpoint_holds_the_gate(client):
    from app.agents.intake import Intake

    partial = all_resolved(KITCHEN_KEYS[:2])
    app.dependency_overrides[get_intake] = lambda: Intake(
        FakeClient([
            intake_reply(status="ready", resolved=partial),
            intake_reply(status="ready", resolved=partial),
        ])
    )
    body = client.post("/api/session").json()
    result = client.post(
        f"/api/session/{body['id']}/brief", json={"text": "a 3 m kitchen"}
    ).json()

    assert result["phase"] == "brief"  # not brief_ready
    assert result["intake"]["missing"]


def test_a_complete_brief_moves_on(client):
    from app.agents.intake import Intake

    app.dependency_overrides[get_intake] = lambda: Intake(
        FakeClient([intake_reply(status="ready", resolved=all_resolved(KITCHEN_KEYS))])
    )
    body = client.post("/api/session").json()
    result = client.post(f"/api/session/{body['id']}/brief", json={"text": "a kitchen"}).json()

    assert result["phase"] == "brief_ready"
    assert "Typology: kitchen" in result["brief"]


def test_building_a_spec_before_the_brief_is_refused(client):
    body = client.post("/api/session").json()
    assert client.post(f"/api/session/{body['id']}/spec/build").status_code == 409


# -- lock and render ------------------------------------------------------


def sheet_names(spec_json: dict) -> list[str]:
    from app.models.spec import build_spec

    return sorted({n for job in plan_views(build_spec(spec_json)).cameras for n in job.references})


def test_lock_requires_every_sheet_the_planner_asked_for(client):
    body = demo(client)
    response = client.post(
        f"/api/session/{body['id']}/lock",
        json={"sheets": [{"name": "elev-wall-a.png", "data": PNG}]},
    )
    assert response.status_code == 422
    assert "Missing" in response.json()["detail"]


def test_lock_accepts_the_full_set(client):
    body = demo(client)
    sheets = [{"name": name, "data": PNG} for name in sheet_names(body["spec"])]
    locked = client.post(f"/api/session/{body['id']}/lock", json={"sheets": sheets}).json()
    assert locked["locked"] is True
    assert locked["phase"] == "locked"


def test_shots_tell_the_browser_what_to_rasterise(client):
    body = demo(client)
    shots = client.get(f"/api/session/{body['id']}/shots").json()
    assert [job["wall_id"] for job in shots["elevations"]] == ["wall-a", "wall-b"]
    assert shots["cameras"][0]["walls"] == ["wall-a", "wall-b"]


def test_render_refuses_before_lock(client):
    body = demo(client)
    assert client.post(f"/api/session/{body['id']}/render").status_code == 409


def test_render_uses_the_uploaded_sheets_as_references(client):
    fake = FakeClient()
    app.dependency_overrides[get_image_client] = lambda: fake

    body = demo(client)
    sheets = [{"name": name, "data": PNG} for name in sheet_names(body["spec"])]
    client.post(f"/api/session/{body['id']}/lock", json={"sheets": sheets})
    result = client.post(f"/api/session/{body['id']}/render").json()

    assert len(result["renders"]) == 1  # L kitchen is one corner shot
    assert result["renders"][0]["data"]
    # the image model saw the sheets the user approved, and nothing else
    assert len(fake.images) == 1
    assert len(fake.images[0]["references"]) == 3
    assert "PHOTOGRAPH" in fake.images[0]["prompt"]
    assert "wall-a" in fake.images[0]["prompt"]


def test_one_shot_can_be_regenerated_from_the_same_packet(client):
    fake = FakeClient()
    app.dependency_overrides[get_image_client] = lambda: fake
    body = demo(client)
    sheets = [{"name": name, "data": PNG} for name in sheet_names(body["spec"])]
    client.post(f"/api/session/{body['id']}/lock", json={"sheets": sheets})
    client.post(f"/api/session/{body['id']}/render")

    again = client.post(f"/api/session/{body['id']}/render/shot-1").json()
    assert len(again["renders"]) == 1
    assert fake.images[0]["prompt"] == fake.images[1]["prompt"]
