"""SVG drawings plus overlay hitmaps for the editor."""
from __future__ import annotations

from app.models.furniture_spec import FurnitureSpec
from app.planner.views import plan_views
from app.render.geometry import wall_height
from app.render.svg_elevation import elevation_svg
from app.render.svg_plan import plan_svg

ELEV_PAD_LEFT = 56.0
ELEV_PAD_RIGHT = 24.0
ELEV_PAD_TOP = 32.0
ELEV_PAD_BOTTOM = 64.0


def drawings_payload(spec: FurnitureSpec) -> dict:
    plan = plan_views(spec)
    elevations = []
    for job in plan.elevations:
        elevations.append({
            "wall_id": job.wall_id,
            "label": job.label,
            "sheet": job.sheet,
            "svg": elevation_svg(spec, job.wall_id),
            **elevation_hitmap(spec, job.wall_id),
        })
    return {
        "plan_svg": plan_svg(spec),
        "elevations": elevations,
        "cameras": [job.model_dump() for job in plan.cameras],
    }


def elevation_hitmap(spec: FurnitureSpec, wall_id: str) -> dict:
    layout = spec.layout_wall(wall_id)
    design = spec.design_wall(wall_id)
    width = layout.length
    height = wall_height(design)
    svg_w = width + ELEV_PAD_LEFT + ELEV_PAD_RIGHT
    svg_h = height + ELEV_PAD_TOP + ELEV_PAD_BOTTOM
    ox, oy = ELEV_PAD_LEFT, ELEV_PAD_TOP
    cornice_h = max(0.0, design.cornice.height)
    plinth_h = max(0.0, design.plinth.height)
    inner_top = oy + cornice_h
    inner_h = max(0.0, height - cornice_h - plinth_h)

    bays = []
    dividers = []
    cursor = ox
    for i, bay in enumerate(design.bays):
        bays.append({
            "id": bay.id,
            "label": bay.label or bay.id,
            "width": bay.width,
            "x": cursor,
            "y": inner_top,
            "height": inner_h,
        })
        if i > 0:
            dividers.append({
                "left_bay_id": design.bays[i - 1].id,
                "right_bay_id": bay.id,
                "x": cursor,
                "y": inner_top,
                "height": inner_h,
            })
        cursor += bay.width

    return {
        "svg_width": svg_w,
        "svg_height": svg_h,
        "bays": bays,
        "dividers": dividers,
    }
