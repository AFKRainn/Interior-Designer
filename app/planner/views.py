"""
View planner — code, not a model.

N walls → N elevation jobs.
Photoreal camera jobs from the wall graph:

  - at most two walls per shot
  - facing walls never share a shot
  - every wall appears in at least one shot
  - no two shots have the same wall set
  - adjacent chains pair along sequence; leftover wall overlaps
    the previous corner (U: A+B then B+C)
  - even chains / four-wall cycles pair (0,1), (2,3) — no wrap-around
  - galley (facing, not adjacent) → one frontal per wall
"""
from typing import Literal, Optional

from pydantic import BaseModel, Field

from app.models.spec import Spec


class ElevationJob(BaseModel):
    wall_id: str
    label: str
    sheet: str


class ShotFrame(BaseModel):
    left: str
    right: Optional[str] = None


class CameraJob(BaseModel):
    shot_id: str
    camera: Literal["inside_corner", "frontal"]
    walls: list[str]
    frame: ShotFrame
    exclude: list[str]
    references: list[str]
    bays_by_wall: dict[str, list[str]] = Field(default_factory=dict)


class ViewPlan(BaseModel):
    elevations: list[ElevationJob]
    cameras: list[CameraJob]


def elevation_sheet_name(wall_id: str) -> str:
    return f"elev-{wall_id}.png"


def plan_sheet_name(shot_id: str) -> str:
    """One plan per shot, with that shot's walls marked (plan 6, stage 3)."""
    return f"plan-{shot_id}.png"


def plan_views(spec: Spec) -> ViewPlan:
    ordered = spec.ordered_layout_walls()
    elevations = [
        ElevationJob(
            wall_id=wall.id,
            label=wall.label or wall.id,
            sheet=elevation_sheet_name(wall.id),
        )
        for wall in ordered
    ]

    wall_ids = [wall.id for wall in ordered]
    cameras = _plan_cameras(spec, wall_ids)
    return ViewPlan(elevations=elevations, cameras=cameras)


def _plan_cameras(spec: Spec, wall_ids: list[str]) -> list[CameraJob]:
    shots: list[tuple[str, ...]] = []
    i = 0
    n = len(wall_ids)

    while i < n:
        current = wall_ids[i]
        is_last = i == n - 1
        nxt = wall_ids[i + 1] if not is_last else None

        if is_last:
            if shots and spec.can_share_camera(shots[-1][-1], current):
                shots.append((shots[-1][-1], current))
            else:
                shots.append((current,))
            i += 1
            continue

        if spec.can_share_camera(current, nxt):
            shots.append((current, nxt))
            i += 2
            continue

        shots.append((current,))
        i += 1

    return [
        _build_camera_job(spec, wall_ids, shot, index)
        for index, shot in enumerate(shots, start=1)
    ]


def _build_camera_job(
    spec: Spec,
    all_wall_ids: list[str],
    shot: tuple[str, ...],
    index: int,
) -> CameraJob:
    if len(shot) == 2:
        left, right = shot
        camera: Literal["inside_corner", "frontal"] = "inside_corner"
        frame = ShotFrame(left=left, right=right)
    elif len(shot) == 1:
        left = shot[0]
        camera = "frontal"
        frame = ShotFrame(left=left, right=None)
    else:
        raise ValueError(f"shot must have 1 or 2 walls, got {shot}")

    shot_walls = list(shot)
    exclude = [wid for wid in all_wall_ids if wid not in shot_walls]
    references = [elevation_sheet_name(wid) for wid in shot_walls]
    references.append(plan_sheet_name(f"shot-{index}"))

    bays_by_wall = {
        wid: spec.design_wall(wid).bay_ids()
        for wid in shot_walls
    }

    return CameraJob(
        shot_id=f"shot-{index}",
        camera=camera,
        walls=shot_walls,
        frame=frame,
        exclude=exclude,
        references=references,
        bays_by_wall=bays_by_wall,
    )
