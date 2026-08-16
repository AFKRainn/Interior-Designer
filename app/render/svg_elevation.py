"""Front elevation SVG for one wall of a Furniture Spec."""
from __future__ import annotations

from app.models.furniture_spec import BaySpec, DesignWall, FurnitureSpec, ModuleSpec
from app.render.geometry import wall_height
from app.render.svg_markup import (
    INNER_STROKE,
    OUTER_STROKE,
    THIN_STROKE,
    add_line,
    add_rect,
    add_text,
    new_svg,
    serialize,
)

HANDLE_TYPES = {"door", "drawer", "glass", "appliance"}


def elevation_svg(spec: FurnitureSpec, wall_id: str) -> str:
    layout = spec.layout_wall(wall_id)
    design = spec.design_wall(wall_id)
    width = layout.length
    height = wall_height(design)

    pad_left = 56.0
    pad_right = 24.0
    pad_top = 32.0
    pad_bottom = 64.0
    svg_w = width + pad_left + pad_right
    svg_h = height + pad_top + pad_bottom

    title = layout.label or wall_id
    root = new_svg(svg_w, svg_h, f"ELEVATION {wall_id}")
    add_text(root, pad_left, 20, title, size=11, anchor="start")

    ox, oy = pad_left, pad_top
    add_rect(
        root,
        ox,
        oy,
        width,
        height,
        stroke=OUTER_STROKE,
        extra={"data-wall-id": wall_id, "class": "carcass"},
    )

    cornice_h = max(0.0, design.cornice.height)
    plinth_h = max(0.0, design.plinth.height)
    if cornice_h > 0:
        add_rect(
            root,
            ox,
            oy,
            width,
            cornice_h,
            stroke=INNER_STROKE,
            extra={"class": "cornice"},
        )
    if plinth_h > 0:
        add_rect(
            root,
            ox,
            oy + height - plinth_h,
            width,
            plinth_h,
            stroke=INNER_STROKE,
            extra={"class": "plinth"},
        )

    inner_top = oy + cornice_h
    inner_h = max(0.0, height - cornice_h - plinth_h)
    cursor_x = ox
    for bay in design.bays:
        _draw_bay(root, bay, cursor_x, inner_top, inner_h)
        cursor_x += bay.width
        add_line(
            root,
            cursor_x,
            inner_top,
            cursor_x,
            inner_top + inner_h,
            stroke=INNER_STROKE,
        )

    cols = design.side_columns
    if cols.left_cm > 0:
        add_rect(
            root,
            ox,
            inner_top,
            cols.left_cm,
            inner_h,
            stroke=THIN_STROKE,
            extra={"class": "side-column"},
        )
    if cols.right_cm > 0:
        add_rect(
            root,
            ox + width - cols.right_cm,
            inner_top,
            cols.right_cm,
            inner_h,
            stroke=THIN_STROKE,
            extra={"class": "side-column"},
        )

    _width_dimensions(root, design, ox, oy + height, width, pad_bottom)
    add_line(root, ox - 12, oy, ox - 12, oy + height, stroke=THIN_STROKE)
    add_text(root, ox - 16, oy + height / 2.0, f"{height:.0f} cm", size=7, anchor="end")

    return serialize(root)


def _draw_bay(
    root,
    bay: BaySpec,
    x: float,
    inner_top: float,
    inner_h: float,
) -> None:
    group_extra = {"data-bay-id": bay.id, "class": "bay"}
    add_rect(
        root,
        x,
        inner_top,
        bay.width,
        inner_h,
        stroke=THIN_STROKE,
        extra=group_extra,
    )
    y = inner_top + inner_h
    for module in bay.modules:
        count = max(1, module.count)
        for _ in range(count):
            y -= module.height
            _draw_module(root, module, x, y, bay.width)


def _draw_module(
    root,
    module: ModuleSpec,
    x: float,
    y: float,
    bay_width: float,
) -> None:
    kind = module.type.strip().lower()
    add_rect(
        root,
        x,
        y,
        bay_width,
        module.height,
        stroke=INNER_STROKE,
        extra={"class": f"module module-{kind}"},
    )
    if kind in {"open", "open_shelf", "shelves"}:
        add_line(
            root,
            x,
            y,
            x + bay_width,
            y,
            stroke=THIN_STROKE,
        )
        return
    if kind == "glass":
        inset = 4.0
        if bay_width > inset * 2 and module.height > inset * 2:
            add_rect(
                root,
                x + inset,
                y + inset,
                bay_width - inset * 2,
                module.height - inset * 2,
                stroke=THIN_STROKE,
            )
    if kind in HANDLE_TYPES and module.handle.strip().lower() != "none":
        _draw_handle(root, kind, x, y, bay_width, module.height)


def _draw_handle(
    root,
    kind: str,
    x: float,
    y: float,
    w: float,
    h: float,
) -> None:
    if kind == "drawer":
        hx, hy, hw, hh = x + w / 2.0 - 6.0, y + h / 2.0 - 0.8, 12.0, 1.6
    else:
        hx, hy, hw, hh = x + w - 8.0, y + h / 2.0 - 6.0, 1.6, 12.0
    add_rect(root, hx, hy, hw, hh, stroke=THIN_STROKE, extra={"class": "handle"})


def _width_dimensions(
    root,
    design: DesignWall,
    ox: float,
    carcass_bottom: float,
    width: float,
    pad_bottom: float,
) -> None:
    y1 = carcass_bottom + 14
    add_line(root, ox, y1, ox + width, y1, stroke=THIN_STROKE)
    add_text(root, ox + width / 2.0, y1 + 10, f"{width:.0f} cm", size=7)
    if not design.bays:
        return
    y2 = carcass_bottom + 32
    cursor = ox
    for bay in design.bays:
        add_line(root, cursor, carcass_bottom, cursor, y2, stroke=THIN_STROKE)
        add_text(
            root,
            cursor + bay.width / 2.0,
            y2 + 10,
            f"{bay.width:.0f}",
            size=6,
        )
        cursor += bay.width
    add_line(root, cursor, carcass_bottom, cursor, y2, stroke=THIN_STROKE)
    add_line(root, ox, y2, ox + width, y2, stroke=THIN_STROKE)
