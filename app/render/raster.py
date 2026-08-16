"""CAD rasters for photoreal reference images.

Pillow, not an SVG parser. plan_svg() goldens are untouched.
2 px per cm. Black stroke, white fill.
"""
from __future__ import annotations

import io
import math

from PIL import Image, ImageDraw

from app.models.furniture_spec import FurnitureSpec
from app.planner.views import CameraJob
from app.render.geometry import Vec, place_walls, wall_height

PX_PER_CM = 2.0
PAD_PX = 48
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
CONE_FILL = (210, 210, 210)
STROKE = 2


def png_bytes(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.convert("RGB").save(buffer, format="PNG")
    return buffer.getvalue()


def elevation_png(spec: FurnitureSpec, wall_id: str) -> Image.Image:
    layout = spec.layout_wall(wall_id)
    design = spec.design_wall(wall_id)
    width = layout.length
    height = wall_height(design)
    pad_left, pad_right, pad_top, pad_bottom = 56.0, 24.0, 32.0, 64.0
    img_w = _px(width + pad_left + pad_right)
    img_h = _px(height + pad_top + pad_bottom)
    image = Image.new("RGB", (img_w, img_h), WHITE)
    draw = ImageDraw.Draw(image)

    ox, oy = pad_left, pad_top
    _rect(draw, ox, oy, width, height, width_px=3)
    draw.text((_px(ox), _px(8)), layout.label or wall_id, fill=BLACK)

    cornice_h = max(0.0, design.cornice.height)
    plinth_h = max(0.0, design.plinth.height)
    if cornice_h > 0:
        _rect(draw, ox, oy, width, cornice_h)
    if plinth_h > 0:
        _rect(draw, ox, oy + height - plinth_h, width, plinth_h)

    inner_top = oy + cornice_h
    inner_h = max(0.0, height - cornice_h - plinth_h)
    cursor = ox
    for bay in design.bays:
        _rect(draw, cursor, inner_top, bay.width, inner_h)
        y = inner_top + inner_h
        for module in bay.modules:
            count = max(1, module.count)
            for _ in range(count):
                y -= module.height
                _rect(draw, cursor, y, bay.width, module.height)
        cursor += bay.width
        _vline(draw, cursor, inner_top, inner_top + inner_h)

    return image


def plan_cone_png(spec: FurnitureSpec, job: CameraJob) -> Image.Image:
    footprints = place_walls(spec)
    if not footprints:
        return Image.new("RGB", (PAD_PX * 2, PAD_PX * 2), WHITE)

    cam, left_pt, right_pt = camera_cone(spec, job)
    xs: list[float] = [cam[0], left_pt[0], right_pt[0]]
    ys: list[float] = [cam[1], left_pt[1], right_pt[1]]
    for fp in footprints:
        for x, y in fp.polygon():
            xs.append(x)
            ys.append(y)

    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    img_w = max(1, _px(max_x - min_x) + PAD_PX * 2)
    img_h = max(1, _px(max_y - min_y) + PAD_PX * 2 + 16)
    image = Image.new("RGB", (img_w, img_h), WHITE)
    draw = ImageDraw.Draw(image)

    def to_px(x: float, y: float) -> tuple[int, int]:
        return (
            int(round((x - min_x) * PX_PER_CM + PAD_PX)),
            int(round((max_y - y) * PX_PER_CM + PAD_PX + 16)),
        )

    cone = [to_px(*cam), to_px(*left_pt), to_px(*right_pt)]
    draw.polygon(cone, fill=CONE_FILL, outline=BLACK)
    draw.text(to_px(*cam), "CAM", fill=BLACK)

    for fp in footprints:
        pts = [to_px(x, y) for x, y in fp.polygon()]
        draw.polygon(pts, outline=BLACK, fill=WHITE)
        cx = (fp.back_start[0] + fp.front_end[0]) / 2.0
        cy = (fp.back_start[1] + fp.front_end[1]) / 2.0
        draw.text(to_px(cx, cy), fp.wall_id, fill=BLACK)

    draw.text((PAD_PX, 8), f"{spec.name or 'PLAN'} {job.shot_id}", fill=BLACK)
    return image


def camera_cone(spec: FurnitureSpec, job: CameraJob) -> tuple[Vec, Vec, Vec]:
    placed = {fp.wall_id: fp for fp in place_walls(spec)}
    if job.camera == "frontal":
        fp = placed[job.frame.left]
        mid = _mid(fp.front_start, fp.front_end)
        cam = _add(mid, _scale(fp.inward, 80.0))
        return cam, fp.front_start, fp.front_end

    left = placed[job.frame.left]
    right_id = job.frame.right or job.walls[-1]
    right = placed[right_id]
    corner = _front_intersection(left, right) or left.front_end
    inward = _add(left.inward, right.inward)
    cam = _add(corner, _scale(_unit(inward), 80.0))
    return cam, left.front_start, right.front_end


def _front_intersection(left, right) -> Vec | None:
    return _intersect(
        left.front_start,
        left.direction,
        right.front_start,
        right.direction,
    )


def _intersect(p: Vec, d1: Vec, q: Vec, d2: Vec) -> Vec | None:
    det = d1[0] * d2[1] - d1[1] * d2[0]
    if abs(det) < 1e-9:
        return None
    dx, dy = q[0] - p[0], q[1] - p[1]
    t = (dx * d2[1] - dy * d2[0]) / det
    return (p[0] + t * d1[0], p[1] + t * d1[1])


def _px(cm: float) -> int:
    return int(round(cm * PX_PER_CM))


def _rect(draw: ImageDraw.ImageDraw, x: float, y: float, w: float, h: float, width_px: int = STROKE) -> None:
    x0, y0 = _px(x), _px(y)
    x1, y1 = _px(x + w), _px(y + h)
    draw.rectangle([x0, y0, x1, y1], outline=BLACK, width=width_px)


def _vline(draw: ImageDraw.ImageDraw, x: float, y0: float, y1: float) -> None:
    px = _px(x)
    draw.line([(px, _px(y0)), (px, _px(y1))], fill=BLACK, width=STROKE)


def _add(a: Vec, b: Vec) -> Vec:
    return (a[0] + b[0], a[1] + b[1])


def _scale(v: Vec, s: float) -> Vec:
    return (v[0] * s, v[1] * s)


def _mid(a: Vec, b: Vec) -> Vec:
    return ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)


def _unit(v: Vec) -> Vec:
    length = math.hypot(v[0], v[1])
    if length < 1e-9:
        return (0.0, 1.0)
    return (v[0] / length, v[1] / length)
