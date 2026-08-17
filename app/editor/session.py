"""
Editor sessions, persisted as JSON under data/sessions.

Build 2 changes what a session holds. There are no server-rendered drawings
any more: the browser owns the renderer, so the session carries the SPEC and
the browser draws it. What the server does own is the history — every spec
version and every op that produced it — which is what makes undo real and
what makes an edit reviewable after the fact.
"""
from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from app.models.spec import Spec, build_spec

SESSIONS: dict[str, dict] = {}

#

UNDO_DEPTH = 60


def sessions_dir() -> Path:
    from config import DATA_DIR

    path = DATA_DIR / "sessions"
    path.mkdir(parents=True, exist_ok=True)
    return path


def session_dir(session_id: str) -> Path:
    path = sessions_dir() / session_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def sheets_dir(session_id: str) -> Path:
    path = session_dir(session_id) / "sheets"
    path.mkdir(parents=True, exist_ok=True)
    return path


def render_file(session_id: str, shot_id: str) -> Path:
    return session_dir(session_id) / f"{shot_id}.png"


def new_session() -> dict:
    session: dict[str, Any] = {
        "id": str(uuid4()),
        "phase": "brief",
        "locked": False,
        "typology": "other",
        "brief": None,
        "resolved": [],
        "intake": None,
        "spec": None,
        "history": [],
        "op_log": [],
        "messages": [],
        "chat": [],
        "sheets": [],
        "renders": [],
        "render_error": None,
    }
    SESSIONS[session["id"]] = session
    save_session(session)
    return session


def get_session(session_id: str) -> dict | None:
    if session_id in SESSIONS:
        return SESSIONS[session_id]
    path = sessions_dir() / f"{session_id}.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("spec"):
        data["spec"] = build_spec(data["spec"])
    for key, default in (
        ("history", []),
        ("op_log", []),
        ("sheets", []),
        ("renders", []),
        ("resolved", []),
        ("chat", []),
        ("messages", []),
    ):
        data.setdefault(key, default)
    data.setdefault("render_error", None)
    SESSIONS[session_id] = data
    return data


def save_session(session: dict) -> None:
    payload = dict(session)
    spec = payload.get("spec")
    if isinstance(spec, Spec):
        payload["spec"] = spec.model_dump(mode="json")
        _snapshot(session["id"], spec)
    path = sessions_dir() / f"{session['id']}.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def set_spec(session: dict, spec: Spec, ops: list[Any] | None = None, note: str = "") -> None:
    """Record a new spec version, keeping the old one for undo."""
    previous = session.get("spec")
    if isinstance(previous, Spec):
        session.setdefault("history", []).append(previous.model_dump(mode="json"))
        del session["history"][:-UNDO_DEPTH]
    session["spec"] = spec
    for op in ops or []:
        session.setdefault("op_log", []).append(
            {
                "op": op.model_dump(mode="json") if hasattr(op, "model_dump") else op,
                "version": spec.version,
                "note": note,
            }
        )


def undo(session: dict) -> bool:
    history: list[dict] = session.get("history") or []
    if not history:
        return False
    session["spec"] = build_spec(history.pop())
    if session.get("op_log"):
        session["op_log"].pop()
    session["locked"] = False
    if session.get("phase") == "locked":
        session["phase"] = "edit"
    return True


def can_undo(session: dict) -> bool:
    return bool(session.get("history"))


def store_sheets(session: dict, sheets: list[dict]) -> list[str]:
    """Persist the browser's rasterised sheets. Names come from the planner."""
    folder = sheets_dir(session["id"])
    for existing in folder.glob("*.png"):
        existing.unlink()
    names: list[str] = []
    for sheet in sheets:
        name = str(sheet.get("name") or "").strip()
        data = sheet.get("data") or ""
        if not name or not data:
            continue
        (folder / name).write_bytes(base64.b64decode(data))
        names.append(name)
    session["sheets"] = names
    return names


def load_sheets(session: dict) -> dict[str, str]:
    folder = sheets_dir(session["id"])
    out: dict[str, str] = {}
    for name in session.get("sheets") or []:
        path = folder / name
        if path.exists():
            out[name] = base64.b64encode(path.read_bytes()).decode("ascii")
    return out


def upsert_render(session: dict, record: dict, image_b64: str) -> None:
    shot_id = record["shot_id"]
    render_file(session["id"], shot_id).write_bytes(base64.b64decode(image_b64))
    renders = [item for item in session.get("renders", []) if item["shot_id"] != shot_id]
    renders.append(dict(record))

    order: dict[str, int] = {}
    spec = session.get("spec")
    if isinstance(spec, Spec):
        from app.planner.views import plan_views

        order = {job.shot_id: i for i, job in enumerate(plan_views(spec).cameras)}
    renders.sort(key=lambda item: order.get(item["shot_id"], 99))
    session["renders"] = renders


def public_session(session: dict) -> dict:
    spec = session.get("spec")
    return {
        "id": session["id"],
        "phase": session["phase"],
        "locked": session["locked"],
        "typology": session.get("typology", "other"),
        "brief": session.get("brief"),
        "resolved": session.get("resolved", []),
        "intake": session.get("intake"),
        "chat": session.get("chat", []),
        "spec": spec.model_dump(mode="json") if isinstance(spec, Spec) else None,
        "can_undo": can_undo(session),
        "op_log": session.get("op_log", [])[-20:],
        "sheets": session.get("sheets", []),
        "renders": [_public_render(session["id"], item) for item in session.get("renders", [])],
        "render_error": session.get("render_error"),
        "versions": list_versions(session["id"]),
        "cost": _cost_summary(),
    }


def say(session: dict, role: str, text: str, extra: dict | None = None) -> None:
    entry = {"role": role, "text": text}
    if extra:
        entry.update(extra)
    session.setdefault("chat", []).append(entry)


def _public_render(session_id: str, item: dict) -> dict:
    out = dict(item)
    out["mime_type"] = "image/png"
    out["data"] = ""
    path = render_file(session_id, item["shot_id"])
    if path.exists():
        out["data"] = base64.b64encode(path.read_bytes()).decode("ascii")
    return out


def _snapshot(session_id: str, spec: Spec) -> None:
    folder = session_dir(session_id) / "versions"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"v{spec.version}.json"
    if not path.exists():
        path.write_text(spec.model_dump_json(indent=2), encoding="utf-8")


def list_versions(session_id: str) -> list[int]:
    folder = sessions_dir() / session_id / "versions"
    if not folder.exists():
        return []
    versions = []
    for path in folder.glob("v*.json"):
        try:
            versions.append(int(path.stem[1:]))
        except ValueError:
            continue
    return sorted(versions)


def _cost_summary() -> dict:
    from app.services.openrouter import CostTracker

    return CostTracker().get_summary()


def find_wall(spec: Optional[Spec], wall_id: str | None) -> str:
    if not isinstance(spec, Spec) or not spec.walls:
        raise ValueError("no spec yet")
    if wall_id:
        spec.design_wall(wall_id)
        return wall_id
    return spec.wall_ids()[0]
