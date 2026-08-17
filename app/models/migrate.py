"""
Build 1 spec -> spec v2.

Two semantic changes make this more than a rename, and both can shrink the
space a wall's bays have to live in:

  1. Corner resolution — one wall at each corner now yields its neighbour's
     depth instead of both claiming the same square (plan 3.4 / progress D6).
  2. Side columns now CONSUME width instead of being drawn on top of the
     bays the way build 1 drew them (progress D9).

So a v1 wall whose bay widths summed exactly to its length will not fit v2's
budget. Rather than silently rescaling stated dimensions, the migration keeps
every stated number it can and lets the LAST bay flex to absorb the
difference. Every adjustment is reported and recorded as an assumption (I8).
"""
from __future__ import annotations

from typing import Any, Optional

from app.models.spec import (
    Assumption,
    CornerMode,
    FIT_TOLERANCE_CM,
    Front,
    FrontType,
    Hinge,
    Opening,
    Spec,
    SplitAxis,
    build_spec,
)

FRONT_TYPES = {
    "door": FrontType.DOOR,
    "drawer": FrontType.DRAWER,
    "open": FrontType.OPEN,
    "open_shelf": FrontType.OPEN,
    "shelves": FrontType.OPEN,
    "shelf": FrontType.OPEN,
    "glass": FrontType.GLASS,
    "appliance": FrontType.APPLIANCE,
    "panel": FrontType.PANEL,
    "false_front": FrontType.FALSE_FRONT,
}


class MigrationReport(list):
    """Plain list of human-readable notes about what had to change."""


def migrate_v1(data: dict[str, Any]) -> tuple[Spec, MigrationReport]:
    """Convert one build-1 spec dict into a validated spec v2."""
    report = MigrationReport()

    layout_walls = [dict(w) for w in data.get("layout", {}).get("walls", [])]
    ordered = sorted(layout_walls, key=lambda w: (w.get("sequence", 0), w.get("id", "")))
    _assign_corners(ordered, report)

    design_by_id = {w["id"]: w for w in data.get("walls", [])}
    walls_v2: list[dict[str, Any]] = []
    assumptions: list[Assumption] = []

    for layout_wall in ordered:
        wall_id = layout_wall["id"]
        source = design_by_id.get(wall_id, {})
        walls_v2.append(
            _migrate_wall(wall_id, source, layout_wall, ordered, design_by_id, report, assumptions)
        )

    spec_data = {
        "project_id": data.get("project_id"),
        "version": int(data.get("version", 1)),
        "units": data.get("units", "cm"),
        "name": data.get("name", ""),
        "layout": {
            "type": data.get("layout", {}).get("type", "custom"),
            "walls": ordered,
        },
        "walls": walls_v2,
        "materials": data.get("materials", {}) or {},
        "hardware": data.get("hardware", {}) or {},
        "brief": data.get("brief", ""),
        "assumptions": [a.model_dump() for a in assumptions],
        "render_notes": data.get("render_notes", ""),
    }
    if spec_data["project_id"] is None:
        spec_data.pop("project_id")

    return build_spec(spec_data), report


def _assign_corners(ordered: list[dict], report: MigrationReport) -> None:
    """Default rule: the later wall in sequence yields (plan 7.2 / D6)."""
    ids = [w["id"] for w in ordered]
    for index, wall in enumerate(ordered):
        adjacent = set(wall.get("adjacent_to") or [])
        corner: dict[str, Optional[str]] = {"start": None, "end": None}
        if index > 0 and ids[index - 1] in adjacent:
            corner["start"] = CornerMode.YIELD.value
            report.append(
                f"{wall['id']}: yields the corner with {ids[index - 1]} "
                f"(later wall in sequence)"
            )
        if index + 1 < len(ids) and ids[index + 1] in adjacent:
            corner["end"] = CornerMode.TAKE.value
        wall["corner"] = corner


def _migrate_wall(
    wall_id: str,
    source: dict[str, Any],
    layout_wall: dict[str, Any],
    ordered: list[dict],
    design_by_id: dict[str, Any],
    report: MigrationReport,
    assumptions: list[Assumption],
) -> dict[str, Any]:
    cornice = dict(source.get("cornice") or {})
    plinth = dict(source.get("plinth") or {})
    height = float(source.get("height") or 220.0)
    inner_height = max(
        0.0, height - float(cornice.get("height") or 0.0) - float(plinth.get("height") or 0.0)
    )

    bays = [
        _migrate_bay(wall_id, bay, inner_height, report)
        for bay in (source.get("bays") or [])
    ]

    extent = _bay_extent(wall_id, layout_wall, source, ordered, design_by_id)
    _fit_bays(wall_id, bays, extent, report, assumptions)

    return {
        "id": wall_id,
        "height": height,
        "depth": float(source.get("depth") or 60.0),
        "reveal_mm": 3.0,
        "cornice": cornice or {},
        "plinth": plinth or {},
        "side_columns": dict(source.get("side_columns") or {}),
        "bays": bays,
    }


def _bay_extent(
    wall_id: str,
    layout_wall: dict,
    source: dict,
    ordered: list[dict],
    design_by_id: dict,
) -> float:
    """Reproduce Spec.bay_extent before the Spec object exists."""
    length = float(layout_wall.get("length") or 0.0)
    ids = [w["id"] for w in ordered]
    index = ids.index(wall_id)
    corner = layout_wall.get("corner") or {}
    if corner.get("start") == CornerMode.YIELD.value and index > 0:
        neighbour = design_by_id.get(ids[index - 1], {})
        length -= float(neighbour.get("depth") or 60.0)
    if corner.get("end") == CornerMode.YIELD.value and index + 1 < len(ids):
        neighbour = design_by_id.get(ids[index + 1], {})
        length -= float(neighbour.get("depth") or 60.0)

    columns = source.get("side_columns") or {}
    return length - float(columns.get("left_cm") or 0.0) - float(columns.get("right_cm") or 0.0)


def _migrate_bay(
    wall_id: str,
    bay: dict[str, Any],
    inner_height: float,
    report: MigrationReport,
) -> dict[str, Any]:
    """v1 modules stacked bottom-up at full bay width -> a rows split."""
    bay_id = bay.get("id") or "bay"
    modules = bay.get("modules") or []

    leaves: list[Opening] = []
    for module in modules:
        kind = str(module.get("type", "")).strip().lower()
        front_type = FRONT_TYPES.get(kind)
        if front_type is None:
            front_type = FrontType.OPEN
            report.append(
                f"{wall_id}/{bay_id}: unknown module type '{kind}' -> 'open'"
            )
        handle = str(module.get("handle") or "none")
        size = float(module.get("height") or 0.0)
        # v1 `count` repeated the module vertically, so it becomes N leaves.
        for _ in range(max(1, int(module.get("count") or 1))):
            leaves.append(
                Opening(
                    id=f"{front_type.value}-{len(leaves) + 1}",
                    size_cm=size if size > 0 else None,
                    flex=None if size > 0 else 1.0,
                    front=Front(type=front_type, hinge=Hinge.NONE, handle=handle),
                )
            )

    # v1 listed modules bottom-first; v2 rows read top-down.
    leaves.reverse()
    for position, leaf in enumerate(leaves, start=1):
        leaf.id = f"{leaf.front.type.value}-{position}"

    result: dict[str, Any] = {
        "id": bay_id,
        "label": bay.get("label") or "",
        "size_cm": float(bay.get("width") or 0.0) or None,
    }

    if not leaves:
        result["front"] = Front(type=FrontType.OPEN).model_dump()
        return result
    if len(leaves) == 1:
        result["front"] = leaves[0].front.model_dump()
        return result

    _fit_stack(wall_id, bay_id, leaves, inner_height, report)
    result["split"] = SplitAxis.ROWS.value
    result["children"] = [leaf.model_dump() for leaf in leaves]
    return result


def _fit_stack(
    wall_id: str,
    bay_id: str,
    leaves: list[Opening],
    inner_height: float,
    report: MigrationReport,
) -> None:
    """Build 1 never checked that module heights filled the bay (plan 3.3).

    Whatever the old stack summed to, the v2 tree must fit exactly. The top
    leaf absorbs any difference.
    """
    total = sum(leaf.size_cm or 0.0 for leaf in leaves)
    if inner_height <= 0 or abs(total - inner_height) <= FIT_TOLERANCE_CM:
        return

    top = leaves[0]
    remainder = inner_height - (total - (top.size_cm or 0.0))
    if remainder <= 0:
        for leaf in leaves:
            leaf.flex = leaf.size_cm or 1.0
            leaf.size_cm = None
        report.append(
            f"{wall_id}/{bay_id}: stack was {total:.0f} cm in a {inner_height:.0f} cm "
            f"opening - all parts made proportional"
        )
        return

    top.size_cm = None
    top.flex = 1.0
    report.append(
        f"{wall_id}/{bay_id}: stack was {total:.0f} cm in a {inner_height:.0f} cm "
        f"opening - '{top.id}' now fills the remainder ({remainder:.0f} cm)"
    )


def _fit_bays(
    wall_id: str,
    bays: list[dict[str, Any]],
    extent: float,
    report: MigrationReport,
    assumptions: list[Assumption],
) -> None:
    """Absorb the width the corner and side columns now take."""
    if not bays or extent <= 0:
        return
    total = sum(float(bay.get("size_cm") or 0.0) for bay in bays)
    if abs(total - extent) <= FIT_TOLERANCE_CM:
        return

    last = bays[-1]
    remainder = extent - (total - float(last.get("size_cm") or 0.0))
    if remainder >= 1.0:
        last["size_cm"] = None
        last["flex"] = 1.0
        note = (
            f"{wall_id}: bays summed to {total:.0f} cm but only {extent:.0f} cm "
            f"is available after corner and side columns - "
            f"'{last['id']}' now absorbs the difference ({remainder:.0f} cm)"
        )
    else:
        for bay in bays:
            bay["flex"] = float(bay.get("size_cm") or 1.0)
            bay["size_cm"] = None
        note = (
            f"{wall_id}: bays summed to {total:.0f} cm in a {extent:.0f} cm run - "
            f"all bay widths made proportional"
        )
    report.append(note)
    assumptions.append(
        Assumption(field=f"{wall_id}.bays", value_cm=round(extent, 1), rationale=note)
    )


def migrate_session(session: dict[str, Any]) -> tuple[Optional[Spec], MigrationReport]:
    """Migrate the spec inside a build-1 session file, if it has one."""
    spec_data = session.get("spec")
    if not spec_data:
        return None, MigrationReport()
    return migrate_v1(spec_data)
