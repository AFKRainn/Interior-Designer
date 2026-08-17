"""
FastAPI surface for build 2.

The server owns the spec, the ops and the invariants. It does NOT own the
drawings: the browser solves and renders them from the spec, so there is no
second layout engine to drift (plan 8). At lock the browser posts back the
sheets it rasterised, and those exact images become the image model's
references.

Every mutation goes through an op. There is no endpoint that accepts a spec.
"""
from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

import config
from app.agents.intake import Intake, IntakeError, compile_brief, merge_resolved
from app.agents.schemas import parse_ops
from app.agents.structure import Structure, StructureError
from app.editor.session import (
    find_wall,
    get_session,
    load_sheets,
    new_session,
    public_session,
    save_session,
    say,
    set_spec,
    store_sheets,
    undo,
    upsert_render,
)
from app.models.diff import diff_paths, summarise
from app.models.ops import OpError, apply_ops
from app.models.spec import Spec, SpecError
from app.planner.views import plan_views
from app.render.packets import (
    PacketError,
    build_packets,
    packet_for_shot,
    public_packet,
    render_packet,
)
from app.services.openrouter import OpenRouterError

app = FastAPI(title="Interior Designer")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(OpenRouterError)
async def openrouter_error(_request: Request, exc: OpenRouterError) -> JSONResponse:
    return JSONResponse(status_code=502, content={"detail": str(exc)})


# -- payloads -------------------------------------------------------------


class ImageIn(BaseModel):
    data: str
    mime_type: str = "image/png"


class BriefIn(BaseModel):
    text: str = ""
    images: list[ImageIn] = Field(default_factory=list)


class OpsIn(BaseModel):
    ops: list[dict] = Field(default_factory=list)


class EditIn(BaseModel):
    utterance: str
    wall_id: str | None = None
    selection: str | None = None


class SheetIn(BaseModel):
    name: str
    data: str
    wall_id: str | None = None


class LockIn(BaseModel):
    sheets: list[SheetIn] = Field(default_factory=list)


# -- dependencies ---------------------------------------------------------


def get_intake() -> Intake:
    return Intake()


def get_structure() -> Structure:
    return Structure()


def get_image_client():
    from app.services.openrouter import OpenRouterClient

    return OpenRouterClient()


def _require(session_id: str) -> dict:
    session = get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")
    return session


def _require_spec(session: dict) -> Spec:
    spec = session.get("spec")
    if not isinstance(spec, Spec):
        raise HTTPException(status_code=409, detail="no spec yet — build the drawings first")
    return spec


def _ok(session: dict) -> dict:
    save_session(session)
    return public_session(session)


# -- session --------------------------------------------------------------


@app.get("/api/health")
def health() -> dict:
    return {
        "ok": True,
        "intake_model": config.INTAKE_MODEL["id"],
        "structure_model": config.STRUCTURE_MODEL["id"],
        "image_model": config.IMAGE_GEN_MODEL["id"],
    }


@app.post("/api/session")
def create_session() -> dict:
    return public_session(new_session())


@app.post("/api/session/demo")
def demo_session() -> dict:
    """A worked L-kitchen, so the editor can be exercised without an API key."""
    from tests.v2_factory import l_kitchen

    session = new_session()
    session["phase"] = "edit"
    session["typology"] = "kitchen"
    session["brief"] = "Demo L-kitchen. Not from a real intake."
    set_spec(session, l_kitchen())
    say(session, "system", "Loaded the demo L-kitchen.")
    return _ok(session)


@app.get("/api/session/{session_id}")
def read_session(session_id: str) -> dict:
    return public_session(_require(session_id))


# -- intake ---------------------------------------------------------------


@app.post("/api/session/{session_id}/brief")
async def brief_turn(
    session_id: str,
    body: BriefIn,
    intake: Intake = Depends(get_intake),
) -> dict:
    session = _require(session_id)
    if session["phase"] == "locked":
        raise HTTPException(status_code=409, detail="session is locked")

    images = [image.model_dump() for image in body.images]
    say(session, "user", body.text or "(image attached)")
    try:
        first = not session["messages"]
        turn = (
            await intake.start(session["messages"], body.text, images)
            if first
            else await intake.reply(session["messages"], body.text, images)
        )
    except IntakeError as err:
        raise HTTPException(status_code=502, detail=str(err)) from err

    resolved = merge_resolved(session["messages"], turn)
    session["typology"] = turn.typology
    session["resolved"] = [item.__dict__ for item in resolved]
    session["intake"] = turn.public()
    say(session, "assistant", turn.response, {"open": turn.open})

    if turn.ready:
        session["brief"] = compile_brief(resolved, turn.typology)
        session["phase"] = "brief_ready"
    return _ok(session)


@app.post("/api/session/{session_id}/spec/build")
async def spec_build(
    session_id: str,
    structure: Structure = Depends(get_structure),
) -> dict:
    session = _require(session_id)
    if not session.get("brief"):
        raise HTTPException(status_code=409, detail="the brief is not ready yet")
    try:
        spec = await structure.build_spec(session["brief"])
    except StructureError as err:
        raise HTTPException(status_code=502, detail=str(err)) from err
    set_spec(session, spec, note="built from brief")
    session["phase"] = "edit"
    say(session, "system", f"Drawings built. {len(spec.walls)} wall(s).")
    return _ok(session)


# -- editing --------------------------------------------------------------


@app.post("/api/session/{session_id}/ops")
def apply_operations(session_id: str, body: OpsIn) -> dict:
    """Direct manipulation. The same ops the edit agent emits."""
    session = _require(session_id)
    spec = _require_spec(session)
    try:
        ops = parse_ops(body.ops)
        updated, records = apply_ops(spec, ops)
    except (OpError, SpecError) as err:
        raise HTTPException(status_code=422, detail=str(err)) from err
    set_spec(session, updated, [record.op for record in records], note="editor")
    return _ok(session)


@app.post("/api/session/{session_id}/ops/preview")
def preview_operations(session_id: str, body: OpsIn) -> dict:
    """Solve the change without committing it, for the ghost preview."""
    session = _require(session_id)
    spec = _require_spec(session)
    try:
        updated, _ = apply_ops(spec, parse_ops(body.ops))
    except (OpError, SpecError) as err:
        raise HTTPException(status_code=422, detail=str(err)) from err
    return {
        "spec": updated.model_dump(mode="json"),
        "diff": diff_paths(spec, updated),
        "summary": summarise(spec, updated),
    }


@app.post("/api/session/{session_id}/edit")
async def edit_by_chat(
    session_id: str,
    body: EditIn,
    structure: Structure = Depends(get_structure),
) -> dict:
    """Natural language -> ops. Nothing is applied here.

    The decision comes back with a restatement and, when it is confident, a
    preview of the change. The user confirms it against the drawing before it
    reaches the spec (plan 10.3).
    """
    session = _require(session_id)
    spec = _require_spec(session)
    wall_id = find_wall(spec, body.wall_id)

    say(session, "user", body.utterance)
    try:
        decision = await structure.edit(spec, wall_id, body.utterance, body.selection)
    except StructureError as err:
        raise HTTPException(status_code=502, detail=str(err)) from err

    payload = decision.public()
    if decision.must_clarify:
        question = decision.ambiguities[0]["question"] if decision.ambiguities else (
            decision.understanding or "Could you say which part you mean?"
        )
        say(session, "assistant", question, {"ambiguities": decision.ambiguities})
    else:
        updated, _ = apply_ops(spec, decision.ops)
        payload["preview"] = {
            "spec": updated.model_dump(mode="json"),
            "diff": diff_paths(spec, updated),
            "summary": summarise(spec, updated),
        }
        say(session, "assistant", decision.understanding, {"proposal": True})

    save_session(session)
    return {"session": public_session(session), "decision": payload}


@app.post("/api/session/{session_id}/undo")
def undo_last(session_id: str) -> dict:
    session = _require(session_id)
    if not undo(session):
        raise HTTPException(status_code=409, detail="nothing to undo")
    return _ok(session)


# -- lock and photoreal ---------------------------------------------------


@app.get("/api/session/{session_id}/shots")
def list_shots(session_id: str) -> dict:
    """The camera plan, so the browser knows which sheets to rasterise."""
    session = _require(session_id)
    spec = _require_spec(session)
    plan = plan_views(spec)
    return {
        "elevations": [job.model_dump() for job in plan.elevations],
        "cameras": [job.model_dump() for job in plan.cameras],
    }


@app.post("/api/session/{session_id}/lock")
def lock(session_id: str, body: LockIn) -> dict:
    session = _require(session_id)
    spec = _require_spec(session)

    required = {name for job in plan_views(spec).cameras for name in job.references}
    stored = set(store_sheets(session, [sheet.model_dump() for sheet in body.sheets]))
    missing = sorted(required - stored)
    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"the browser did not upload every sheet. Missing: {', '.join(missing)}",
        )

    session["locked"] = True
    session["phase"] = "locked"
    say(session, "system", f"Drawings locked at v{spec.version}.")
    return _ok(session)


@app.post("/api/session/{session_id}/render")
async def render_all(session_id: str, client=Depends(get_image_client)) -> dict:
    session = _require(session_id)
    spec = _require_spec(session)
    if not session["locked"]:
        raise HTTPException(status_code=409, detail="lock the drawings first")

    session["render_error"] = None
    try:
        packets = build_packets(spec, load_sheets(session))
    except PacketError as err:
        raise HTTPException(status_code=409, detail=str(err)) from err

    for packet in packets:
        try:
            data, _mime = await render_packet(client, packet)
        except PacketError as err:
            session["render_error"] = str(err)
            break
        upsert_render(session, public_packet(packet), data)
    return _ok(session)


@app.post("/api/session/{session_id}/render/{shot_id}")
async def render_one(session_id: str, shot_id: str, client=Depends(get_image_client)) -> dict:
    session = _require(session_id)
    spec = _require_spec(session)
    if not session["locked"]:
        raise HTTPException(status_code=409, detail="lock the drawings first")

    session["render_error"] = None
    try:
        packet = packet_for_shot(spec, shot_id, load_sheets(session))
        data, _mime = await render_packet(client, packet)
    except PacketError as err:
        raise HTTPException(status_code=409, detail=str(err)) from err
    upsert_render(session, public_packet(packet), data)
    return _ok(session)
