"""
Place walls in 2D from the Furniture Spec graph.

Sequence order. First wall along +X, interior toward +Y.
Each next adjacent wall turns 90° CCW at the previous wall's back end.
A facing (galley) wall is placed parallel, fronts looking at each other
across GALLEY_AISLE_CM.

1 unit = 1 cm.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.models.furniture_spec import DesignWall, FurnitureSpec, LayoutWall

GALLEY_AISLE_CM = 120.0
DEFAULT_DEPTH_CM = 60.0
DEFAULT_HEIGHT_CM = 220.0

Vec = tuple[float, float]


def _add(a: Vec, b: Vec) -> Vec:
    return (a[0] + b[0], a[1] + b[1])


def _scale(v: Vec, s: float) -> Vec:
    return (v[0] * s, v[1] * s)


def _rot90_ccw(v: Vec) -> Vec:
    return (-v[1], v[0])


@dataclass
class WallFootprint:
    wall_id: str
    label: str
    back_start: Vec
    back_end: Vec
    front_end: Vec
    front_start: Vec
    direction: Vec
    inward: Vec
    length: float
    depth: float
    bay_dividers: list[Vec] = field(default_factory=list)
    bay_midpoints: list[tuple[Vec, str]] = field(default_factory=list)

    def polygon(self) -> list[Vec]:
        return [self.back_start, self.back_end, self.front_end, self.front_start]


def wall_depth(design: DesignWall) -> float:
    return design.depth if design.depth > 0 else DEFAULT_DEPTH_CM


def wall_height(design: DesignWall) -> float:
    return design.height if design.height > 0 else DEFAULT_HEIGHT_CM


def place_walls(spec: FurnitureSpec) -> list[WallFootprint]:
    ordered = spec.ordered_layout_walls()
    if not ordered:
        return []

    placed: dict[str, WallFootprint] = {}
    unplaced = list(ordered)

    first = unplaced.pop(0)
    placed[first.id] = _footprint(
        spec, first, origin=(0.0, 0.0), direction=(1.0, 0.0), inward=(0.0, 1.0)
    )
    last_id = first.id

    while unplaced:
        nxt = _next_wall(spec, last_id, unplaced)
        if nxt is None:
            nxt = unplaced[0]
            bbox = _bbox(list(placed.values()))
            origin = (bbox[2] + 80.0, 0.0)
            direction = (1.0, 0.0)
            inward = (0.0, 1.0)
            placed[nxt.id] = _footprint(spec, nxt, origin, direction, inward)
        elif spec.is_adjacent(last_id, nxt.id):
            prev = placed[last_id]
            origin = prev.back_end
            direction = _rot90_ccw(prev.direction)
            inward = _rot90_ccw(prev.inward)
            placed[nxt.id] = _footprint(spec, nxt, origin, direction, inward)
        elif spec.is_facing(last_id, nxt.id):
            placed[nxt.id] = _place_facing(spec, placed[last_id], nxt)
        else:
            prev = placed[last_id]
            origin = _add(prev.back_end, (80.0, 0.0))
            placed[nxt.id] = _footprint(
                spec, nxt, origin, prev.direction, prev.inward
            )

        unplaced = [wall for wall in unplaced if wall.id != nxt.id]
        last_id = nxt.id

    return [placed[wall.id] for wall in ordered]


def _next_wall(
    spec: FurnitureSpec,
    last_id: str,
    unplaced: list[LayoutWall],
) -> LayoutWall | None:
    for wall in unplaced:
        if spec.is_adjacent(last_id, wall.id):
            return wall
    for wall in unplaced:
        if spec.is_facing(last_id, wall.id):
            return wall
    return None


def _place_facing(
    spec: FurnitureSpec,
    prev: WallFootprint,
    nxt: LayoutWall,
) -> WallFootprint:
    depth = wall_depth(spec.design_wall(nxt.id))
    origin = _add(prev.front_start, _scale(prev.inward, GALLEY_AISLE_CM + depth))
    return _footprint(
        spec,
        nxt,
        origin=origin,
        direction=prev.direction,
        inward=_scale(prev.inward, -1.0),
    )


def _footprint(
    spec: FurnitureSpec,
    layout_wall: LayoutWall,
    origin: Vec,
    direction: Vec,
    inward: Vec,
) -> WallFootprint:
    design = spec.design_wall(layout_wall.id)
    length = layout_wall.length
    depth = wall_depth(design)
    back_start = origin
    back_end = _add(origin, _scale(direction, length))
    front_start = _add(origin, _scale(inward, depth))
    front_end = _add(back_end, _scale(inward, depth))

    dividers = [front_start]
    mids: list[tuple[Vec, str]] = []
    cursor = 0.0
    for bay in design.bays:
        mid = _add(front_start, _scale(direction, cursor + bay.width / 2.0))
        mids.append((mid, bay.label or bay.id))
        cursor += bay.width
        dividers.append(_add(front_start, _scale(direction, cursor)))
    if not design.bays:
        dividers.append(front_end)

    return WallFootprint(
        wall_id=layout_wall.id,
        label=layout_wall.label or layout_wall.id,
        back_start=back_start,
        back_end=back_end,
        front_end=front_end,
        front_start=front_start,
        direction=direction,
        inward=inward,
        length=length,
        depth=depth,
        bay_dividers=dividers,
        bay_midpoints=mids,
    )


def _bbox(footprints: list[WallFootprint]) -> tuple[float, float, float, float]:
    xs: list[float] = []
    ys: list[float] = []
    for fp in footprints:
        for x, y in fp.polygon():
            xs.append(x)
            ys.append(y)
    return (min(xs), min(ys), max(xs), max(ys))
