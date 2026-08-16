"""Top-down plan SVG from a Furniture Spec."""
from __future__ import annotations

from app.models.furniture_spec import FurnitureSpec
from app.render.geometry import WallFootprint, place_walls
from app.render.svg_markup import (
    PAD,
    THIN_STROKE,
    add_line,
    add_polygon,
    add_text,
    new_svg,
    serialize,
)

TICK_CM = 8.0
DIM_OFFSET_CM = 22.0


def plan_svg(spec: FurnitureSpec) -> str:
    footprints = place_walls(spec)
    if not footprints:
        root = new_svg(PAD * 2, PAD * 2, "PLAN")
        return serialize(root)

    xs: list[float] = []
    ys: list[float] = []
    for fp in footprints:
        for x, y in fp.polygon():
            xs.append(x)
            ys.append(y)
        outside = _dim_line_points(fp)
        for x, y in outside:
            xs.append(x)
            ys.append(y)

    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    width = (max_x - min_x) + PAD * 2
    height = (max_y - min_y) + PAD * 2 + 16

    def to_svg(x: float, y: float) -> tuple[float, float]:
        return (x - min_x + PAD, max_y - y + PAD + 16)

    root = new_svg(width, height, "PLAN")
    add_text(root, PAD, 20, spec.name or "PLAN", size=12, anchor="start")

    for fp in footprints:
        pts = [to_svg(x, y) for x, y in fp.polygon()]
        add_polygon(
            root,
            pts,
            extra={"data-wall-id": fp.wall_id, "class": "wall-footprint"},
        )
        _bay_ticks(root, fp, to_svg)
        _wall_label(root, fp, to_svg)
        _length_dimension(root, fp, to_svg)

    return serialize(root)


def _bay_ticks(root, fp: WallFootprint, to_svg) -> None:
    back_dir = (-fp.inward[0], -fp.inward[1])
    for i, (x, y) in enumerate(fp.bay_dividers):
        if i == 0 or i == len(fp.bay_dividers) - 1:
            continue
        end = (x + back_dir[0] * TICK_CM, y + back_dir[1] * TICK_CM)
        a = to_svg(x, y)
        b = to_svg(*end)
        add_line(root, a[0], a[1], b[0], b[1], stroke=THIN_STROKE)


def _wall_label(root, fp: WallFootprint, to_svg) -> None:
    cx = (fp.back_start[0] + fp.front_end[0]) / 2.0
    cy = (fp.back_start[1] + fp.front_end[1]) / 2.0
    x, y = to_svg(cx, cy)
    add_text(root, x, y + 3, fp.wall_id, size=7)


def _dim_line_points(fp: WallFootprint) -> list[tuple[float, float]]:
    outward = (-fp.inward[0], -fp.inward[1])
    a = (
        fp.back_start[0] + outward[0] * DIM_OFFSET_CM,
        fp.back_start[1] + outward[1] * DIM_OFFSET_CM,
    )
    b = (
        fp.back_end[0] + outward[0] * DIM_OFFSET_CM,
        fp.back_end[1] + outward[1] * DIM_OFFSET_CM,
    )
    return [a, b]


def _length_dimension(root, fp: WallFootprint, to_svg) -> None:
    a, b = _dim_line_points(fp)
    sa = to_svg(*a)
    sb = to_svg(*b)
    back_a = to_svg(*fp.back_start)
    back_b = to_svg(*fp.back_end)
    add_line(root, back_a[0], back_a[1], sa[0], sa[1], stroke=THIN_STROKE)
    add_line(root, back_b[0], back_b[1], sb[0], sb[1], stroke=THIN_STROKE)
    add_line(root, sa[0], sa[1], sb[0], sb[1], stroke=THIN_STROKE)
    mx = (sa[0] + sb[0]) / 2.0
    my = (sa[1] + sb[1]) / 2.0
    add_text(root, mx, my - 2, f"{fp.length:.0f} cm", size=7)
