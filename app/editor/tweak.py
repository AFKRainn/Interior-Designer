"""Bay-width tweaks. Code, not an LLM. Wall length stays the same."""
from __future__ import annotations

from app.models.furniture_spec import FurnitureSpec

MIN_BAY_CM = 10.0


class TweakError(ValueError):
    pass


def set_bay_width(
    spec: FurnitureSpec,
    wall_id: str,
    bay_id: str,
    new_width: float,
) -> FurnitureSpec:
    data = spec.model_dump(mode="json")
    wall = _wall(data, wall_id)
    bays = wall["bays"]
    index = _bay_index(bays, bay_id)
    neighbor = index + 1 if index < len(bays) - 1 else index - 1
    if neighbor < 0:
        raise TweakError("need at least two bays to change a width")
    old = float(bays[index]["width"])
    new_width = float(new_width)
    if new_width < MIN_BAY_CM:
        raise TweakError(f"bay width must be at least {MIN_BAY_CM} cm")
    delta = new_width - old
    neighbor_new = float(bays[neighbor]["width"]) - delta
    if neighbor_new < MIN_BAY_CM:
        raise TweakError("neighbor bay would be too narrow")
    bays[index]["width"] = new_width
    bays[neighbor]["width"] = neighbor_new
    data["version"] = int(data.get("version", 1)) + 1
    return FurnitureSpec.model_validate(data)


def move_divider(
    spec: FurnitureSpec,
    wall_id: str,
    left_bay_id: str,
    delta_cm: float,
) -> FurnitureSpec:
    data = spec.model_dump(mode="json")
    wall = _wall(data, wall_id)
    bays = wall["bays"]
    index = _bay_index(bays, left_bay_id)
    if index >= len(bays) - 1:
        raise TweakError("no divider after the last bay")
    left = float(bays[index]["width"]) + float(delta_cm)
    right = float(bays[index + 1]["width"]) - float(delta_cm)
    if left < MIN_BAY_CM or right < MIN_BAY_CM:
        raise TweakError("bay would be too narrow")
    bays[index]["width"] = left
    bays[index + 1]["width"] = right
    data["version"] = int(data.get("version", 1)) + 1
    return FurnitureSpec.model_validate(data)


def _wall(data: dict, wall_id: str) -> dict:
    for wall in data["walls"]:
        if wall["id"] == wall_id:
            return wall
    raise TweakError(f"unknown wall {wall_id}")


def _bay_index(bays: list[dict], bay_id: str) -> int:
    for i, bay in enumerate(bays):
        if bay["id"] == bay_id:
            return i
    raise TweakError(f"unknown bay {bay_id}")
