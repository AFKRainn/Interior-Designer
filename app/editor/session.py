"""In-memory editor sessions, persisted as JSON under data/sessions."""
from __future__ import annotations

import base64
import json
from pathlib import Path
from uuid import uuid4

from app.models.furniture_spec import FurnitureSpec

SESSIONS: dict[str, dict] = {}


def sessions_dir() -> Path:
    from config import DATA_DIR

    path = DATA_DIR / "sessions"
    path.mkdir(parents=True, exist_ok=True)
    return path


def render_dir(session_id: str) -> Path:
    path = sessions_dir() / session_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def render_file(session_id: str, shot_id: str) -> Path:
    return render_dir(session_id) / f"{shot_id}.png"


def versions_dir(session_id: str) -> Path:
    path = render_dir(session_id) / "versions"
    path.mkdir(parents=True, exist_ok=True)
    return path


def new_session() -> dict:
    session = {
        "id": str(uuid4()),
        "phase": "brief",
        "locked": False,
        "brief": None,
        "spec": None,
        "messages": [],
        "chat": [],
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
        data["spec"] = FurnitureSpec.model_validate(data["spec"])
    SESSIONS[session_id] = data
    data.setdefault("renders", [])
    data.setdefault("render_error", None)
    return data


def save_session(session: dict) -> None:
    snapshot_spec(session)
    payload = dict(session)
    spec = payload.get("spec")
    if isinstance(spec, FurnitureSpec):
        payload["spec"] = spec.model_dump(mode="json")
    path = sessions_dir() / f"{session['id']}.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def public_session(session: dict, drawings: dict | None = None) -> dict:
    spec = session.get("spec")
    out = {
        "id": session["id"],
        "phase": session["phase"],
        "locked": session["locked"],
        "brief": session.get("brief"),
        "chat": session.get("chat", []),
        "spec": spec.model_dump(mode="json") if isinstance(spec, FurnitureSpec) else spec,
        "drawings": drawings,
        "renders": [_public_render(session["id"], item) for item in session.get("renders", [])],
        "render_error": session.get("render_error"),
        "spec_versions": list_spec_versions(session["id"]),
        "cost": _cost_summary(),
    }
    return out


def upsert_render(session: dict, record: dict, image_b64: str) -> None:
    shot_id = record["shot_id"]
    path = render_file(session["id"], shot_id)
    path.write_bytes(base64.b64decode(image_b64))
    stored = dict(record)
    stored["file"] = path.name
    renders = [item for item in session.get("renders", []) if item["shot_id"] != shot_id]
    renders.append(stored)
    order = {item["shot_id"]: index for index, item in enumerate(renders)}
    spec = session.get("spec")
    if isinstance(spec, FurnitureSpec):
        from app.planner.views import plan_views

        order = {
            job.shot_id: index
            for index, job in enumerate(plan_views(spec).cameras)
        }
    renders.sort(key=lambda item: order.get(item["shot_id"], 99))
    session["renders"] = renders


def _public_render(session_id: str, item: dict) -> dict:
    out = {
        "shot_id": item["shot_id"],
        "camera": item.get("camera"),
        "walls": item.get("walls", []),
        "frame": item.get("frame"),
        "exclude": item.get("exclude", []),
        "prompt": item.get("prompt", ""),
        "references": item.get("references", []),
        "mime_type": "image/png",
        "data": "",
    }
    path = render_file(session_id, item["shot_id"])
    if path.exists():
        out["data"] = base64.b64encode(path.read_bytes()).decode("ascii")
    return out


def snapshot_spec(session: dict) -> None:
    spec = session.get("spec")
    if not isinstance(spec, FurnitureSpec):
        return
    path = versions_dir(session["id"]) / f"v{spec.version}.json"
    if path.exists():
        return
    path.write_text(spec.model_dump_json(indent=2), encoding="utf-8")


def list_spec_versions(session_id: str) -> list[dict]:
    folder = sessions_dir() / session_id / "versions"
    if not folder.exists():
        return []
    versions = []
    for path in folder.glob("v*.json"):
        try:
            version = int(path.stem[1:])
        except ValueError:
            continue
        versions.append({"version": version, "file": path.name})
    versions.sort(key=lambda item: item["version"])
    return versions


def _cost_summary() -> dict:
    from app.services.openrouter import CostTracker

    return CostTracker().get_summary()
