"""FastAPI for the furniture editor."""
from __future__ import annotations

import json
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.agents.brief import Brief
from app.agents.spec_author import SpecAuthor, SpecAuthorError
from app.editor.drawings import drawings_payload
from app.editor.sample import l_kitchen_spec
from app.editor.session import (
    get_session,
    new_session,
    public_session,
    save_session,
    upsert_render,
)
from app.editor.tweak import TweakError, move_divider, set_bay_width
from app.models.furniture_spec import FurnitureSpec
from app.render.photoreal import (
    PhotorealError,
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
    status = exc.status_code if exc.status_code in {400, 401, 402, 403, 429} else 502
    return JSONResponse(status_code=status, content={"detail": str(exc)})


class ImageIn(BaseModel):
    data: str
    mime_type: str = "image/png"


class BriefStartIn(BaseModel):
    text: str = ""
    images: list[ImageIn] = Field(default_factory=list)


class BriefReplyIn(BaseModel):
    text: str = ""
    images: list[ImageIn] = Field(default_factory=list)


class TextIn(BaseModel):
    text: str


class BayWidthIn(BaseModel):
    wall_id: str
    bay_id: str
    width: float


class DividerIn(BaseModel):
    wall_id: str
    left_bay_id: str
    delta_cm: float


def get_brief() -> Brief:
    return Brief()


def get_author() -> SpecAuthor:
    return SpecAuthor()


def get_image_client():
    from app.services.openrouter import OpenRouterClient

    return OpenRouterClient()


def _require(session_id: str) -> dict:
    session = get_session(session_id)
    if session is None:
        raise HTTPException(404, "session not found")
    return session


def _draw(session: dict) -> dict | None:
    spec = session.get("spec")
    if not isinstance(spec, FurnitureSpec):
        return None
    return drawings_payload(spec)


def _ok(session: dict) -> dict:
    save_session(session)
    return public_session(session, _draw(session))


@app.get("/api/health")
def health() -> dict:
    from app.services.openrouter import CostTracker

    return {"ok": True, "cost": CostTracker().get_summary()}


@app.post("/api/session")
def create_session() -> dict:
    return _ok(new_session())


@app.post("/api/session/demo")
def demo_session() -> dict:
    session = new_session()
    spec = l_kitchen_spec()
    spec.project_id = session["id"]
    session["spec"] = spec
    session["brief"] = spec.brief
    session["phase"] = "edit"
    session["chat"] = [
        {"role": "assistant", "text": "Demo L-kitchen loaded. Tweak bays or chat a change."}
    ]
    return _ok(session)


@app.get("/api/session/{session_id}")
def read_session(session_id: str) -> dict:
    return _ok(_require(session_id))


@app.post("/api/session/{session_id}/brief/start")
async def brief_start(
    session_id: str,
    body: BriefStartIn,
    brief: Brief = Depends(get_brief),
) -> dict:
    session = _require(session_id)
    if session["locked"]:
        raise HTTPException(409, "session is locked")
    images = [img.model_dump() for img in body.images] or None
    result = await brief.start(body.text or None, images)
    session["messages"] = result["messages"]
    session["brief"] = result.get("brief")
    session["chat"] = _visible_chat(result["messages"])
    if result["status"] == "confirmed" and result.get("brief"):
        session["phase"] = "brief_ready"
    else:
        session["phase"] = "brief"
    return _ok(session)


@app.post("/api/session/{session_id}/brief/reply")
async def brief_reply(
    session_id: str,
    body: BriefReplyIn,
    brief: Brief = Depends(get_brief),
) -> dict:
    session = _require(session_id)
    if session["locked"]:
        raise HTTPException(409, "session is locked")
    images = [img.model_dump() for img in body.images] or None
    result = await brief.reply(session["messages"], body.text, images)
    session["messages"] = result["messages"]
    session["brief"] = result.get("brief")
    session["chat"] = _visible_chat(result["messages"])
    if result["status"] == "confirmed" and result.get("brief"):
        session["phase"] = "brief_ready"
    return _ok(session)


@app.post("/api/session/{session_id}/spec/build")
async def spec_build(
    session_id: str,
    author: SpecAuthor = Depends(get_author),
) -> dict:
    session = _require(session_id)
    if session["locked"]:
        raise HTTPException(409, "session is locked")
    if not session.get("brief"):
        raise HTTPException(400, "brief is not confirmed yet")
    try:
        spec = await author.from_brief(session["brief"], session.get("messages"))
    except SpecAuthorError as exc:
        raise HTTPException(422, str(exc)) from exc
    spec.project_id = session["id"]
    session["spec"] = spec
    session["phase"] = "edit"
    return _ok(session)


@app.post("/api/session/{session_id}/spec/patch")
async def spec_patch(
    session_id: str,
    body: TextIn,
    author: SpecAuthor = Depends(get_author),
) -> dict:
    session = _require(session_id)
    _editable(session)
    spec = session["spec"]
    try:
        updated = await author.patch(spec, body.text)
    except SpecAuthorError as exc:
        raise HTTPException(422, str(exc)) from exc
    session["spec"] = updated
    session["chat"] = session.get("chat", []) + [
        {"role": "user", "text": body.text},
        {"role": "assistant", "text": "Spec updated."},
    ]
    return _ok(session)


@app.post("/api/session/{session_id}/spec/bay-width")
def spec_bay_width(session_id: str, body: BayWidthIn) -> dict:
    session = _require(session_id)
    _editable(session)
    try:
        session["spec"] = set_bay_width(
            session["spec"], body.wall_id, body.bay_id, body.width
        )
    except TweakError as exc:
        raise HTTPException(400, str(exc)) from exc
    return _ok(session)


@app.post("/api/session/{session_id}/spec/divider")
def spec_divider(session_id: str, body: DividerIn) -> dict:
    session = _require(session_id)
    _editable(session)
    try:
        session["spec"] = move_divider(
            session["spec"], body.wall_id, body.left_bay_id, body.delta_cm
        )
    except TweakError as exc:
        raise HTTPException(400, str(exc)) from exc
    return _ok(session)


@app.post("/api/session/{session_id}/lock")
def lock_session(session_id: str) -> dict:
    session = _require(session_id)
    if not isinstance(session.get("spec"), FurnitureSpec):
        raise HTTPException(400, "no spec to lock")
    session["locked"] = True
    session["phase"] = "locked"
    return _ok(session)


@app.post("/api/session/{session_id}/render")
async def render_all(session_id: str, client=Depends(get_image_client)) -> dict:
    session = _locked_spec(session_id)
    return await _render_shots(session, build_packets(session["spec"]), client, fill_missing=True)


@app.post("/api/session/{session_id}/render/{shot_id}")
async def render_one(
    session_id: str,
    shot_id: str,
    client=Depends(get_image_client),
) -> dict:
    session = _locked_spec(session_id)
    try:
        packet = packet_for_shot(session["spec"], shot_id)
    except PhotorealError as exc:
        raise HTTPException(404, str(exc)) from exc
    return await _render_shots(session, [packet], client, fill_missing=False)


async def _render_shots(session: dict, packets: list, client, fill_missing: bool) -> dict:
    existing = {item["shot_id"] for item in session.get("renders", [])}
    session["render_error"] = None
    try:
        for packet in packets:
            if fill_missing and packet.shot_id in existing:
                continue
            data, _mime = await render_packet(client, packet)
            upsert_render(session, public_packet(packet), data)
    except PhotorealError as exc:
        session["render_error"] = str(exc)
        save_session(session)
        raise HTTPException(502, str(exc)) from exc
    return _ok(session)


def _locked_spec(session_id: str) -> dict:
    session = _require(session_id)
    if not session.get("locked"):
        raise HTTPException(409, "lock drawings before photoreal")
    if not isinstance(session.get("spec"), FurnitureSpec):
        raise HTTPException(400, "no spec to render")
    return session


def _editable(session: dict) -> None:
    if session["locked"]:
        raise HTTPException(409, "session is locked")
    if not isinstance(session.get("spec"), FurnitureSpec):
        raise HTTPException(400, "no spec yet")


def _visible_chat(messages: list[dict]) -> list[dict]:
    visible = []
    for msg in messages:
        role = msg.get("role")
        if role not in ("user", "assistant"):
            continue
        content = msg.get("content", "")
        if isinstance(content, list):
            texts = [
                part.get("text", "")
                for part in content
                if isinstance(part, dict) and part.get("type") == "text"
            ]
            content = " ".join(texts)
        if not isinstance(content, str):
            continue
        text = content
        if role == "assistant":
            try:
                parsed = json.loads(content)
                text = parsed.get("response") or content
            except (json.JSONDecodeError, TypeError):
                text = content
        if text.strip():
            visible.append({"role": role, "text": text})
    return visible
