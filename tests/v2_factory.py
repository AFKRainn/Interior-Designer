"""Spec v2 fixtures for tests."""
from __future__ import annotations

from app.models.spec import Spec, build_spec


def straight_wall() -> Spec:
    """One 300 cm run. inner height 200 (220 - 8 cornice - 12 plinth)."""
    return build_spec(
        {
            "name": "straight test run",
            "layout": {
                "type": "straight",
                "walls": [{"id": "wall-a", "label": "Wall A", "length": 300, "sequence": 0}],
            },
            "walls": [
                {
                    "id": "wall-a",
                    "height": 220,
                    "depth": 60,
                    "cornice": {"height": 8},
                    "plinth": {"height": 12},
                    "bays": [
                        {
                            "id": "bay-1",
                            "size_cm": 100,
                            "split": "rows",
                            "children": [
                                {"id": "row-1", "size_cm": 60,
                                 "front": {"type": "door", "handle": "bar"}},
                                {"id": "row-2", "flex": 1,
                                 "front": {"type": "drawer", "handle": "bar"}},
                            ],
                        },
                        {"id": "bay-2", "size_cm": 100, "front": {"type": "open"}},
                        {"id": "bay-3", "flex": 1,
                         "front": {"type": "door", "handle": "bar"}},
                    ],
                }
            ],
        }
    )


def l_kitchen() -> Spec:
    """Two adjacent runs. wall-b yields the corner, so its usable run is
    240 - 60 = 180 cm."""
    return build_spec(
        {
            "name": "L kitchen",
            "layout": {
                "type": "L",
                "walls": [
                    {
                        "id": "wall-a",
                        "length": 320,
                        "sequence": 0,
                        "adjacent_to": ["wall-b"],
                        "corner": {"end": "take"},
                    },
                    {
                        "id": "wall-b",
                        "length": 240,
                        "sequence": 1,
                        "adjacent_to": ["wall-a"],
                        "corner": {"start": "yield"},
                    },
                ],
            },
            "walls": [
                {
                    "id": "wall-a",
                    "height": 220,
                    "depth": 60,
                    "bays": [
                        {"id": "bay-1", "size_cm": 160, "front": {"type": "door"}},
                        {"id": "bay-2", "flex": 1, "front": {"type": "drawer"}},
                    ],
                },
                {
                    "id": "wall-b",
                    "height": 220,
                    "depth": 60,
                    "bays": [{"id": "bay-1", "flex": 1, "front": {"type": "open"}}],
                },
            ],
        }
    )


def v1_wardrobe() -> dict:
    """A build-1 spec shaped like the real ones on disk.

    Bay widths sum to the full 360 cm wall while side columns take another
    16 cm — exactly the case v2 has to absorb.
    """
    return {
        "project_id": "11111111-2222-3333-4444-555555555555",
        "version": 3,
        "units": "cm",
        "name": "Storage wall",
        "layout": {
            "type": "straight",
            "walls": [
                {
                    "id": "wall-a",
                    "label": "Wall A — Main Storage Wall",
                    "length": 360.0,
                    "adjacent_to": [],
                    "faces": [],
                    "sequence": 0,
                }
            ],
        },
        "walls": [
            {
                "id": "wall-a",
                "height": 220.0,
                "depth": 60.0,
                "cornice": {"type": "straight", "height": 10.0},
                "plinth": {"type": "recessed", "height": 10.0},
                "side_columns": {"left_cm": 8.0, "right_cm": 8.0, "detail": "plain"},
                "bays": [
                    {
                        "id": "bay-1",
                        "label": "Left Flanking Tower",
                        "width": 60.0,
                        "modules": [
                            {"type": "door", "height": 80.0, "count": 1, "handle": "knob"},
                            {"type": "open_shelf", "height": 35.0, "count": 1, "handle": "none"},
                            {"type": "door", "height": 85.0, "count": 1, "handle": "knob"},
                        ],
                    },
                    {
                        "id": "bay-2",
                        "label": "Centre",
                        "width": 240.0,
                        "modules": [
                            {"type": "drawer", "height": 25.0, "count": 4, "handle": "bar"},
                            {"type": "door", "height": 100.0, "count": 1, "handle": "bar"},
                        ],
                    },
                    {
                        "id": "bay-3",
                        "label": "Right Flanking Tower",
                        "width": 60.0,
                        "modules": [
                            {"type": "door", "height": 200.0, "count": 1, "handle": "knob"}
                        ],
                    },
                ],
            }
        ],
        "materials": {"carcass": "birch ply", "doors": "sprayed MDF", "finish": "matt"},
        "hardware": {"style": "knob", "placement": "centred"},
        "brief": "locked facts",
        "render_notes": "warm evening light",
    }


def u_kitchen() -> Spec:
    """Three walls in a chain. The two arms face each other across the room."""
    return build_spec(
        {
            "name": "U kitchen",
            "layout": {
                "type": "U",
                "walls": [
                    {"id": "wall-a", "label": "Left arm", "length": 300, "sequence": 0,
                     "adjacent_to": ["wall-b"], "faces": ["wall-c"],
                     "corner": {"end": "take"}},
                    {"id": "wall-b", "label": "Back run", "length": 400, "sequence": 1,
                     "adjacent_to": ["wall-a", "wall-c"],
                     "corner": {"start": "yield", "end": "take"}},
                    {"id": "wall-c", "label": "Right arm", "length": 300, "sequence": 2,
                     "adjacent_to": ["wall-b"], "faces": ["wall-a"],
                     "corner": {"start": "yield"}},
                ],
            },
            "walls": [
                {"id": "wall-a", "height": 220, "depth": 60,
                 "cornice": {"height": 6}, "plinth": {"height": 12},
                 "bays": [{"id": "bay-1", "flex": 1, "front": {"type": "door"}},
                          {"id": "bay-2", "flex": 1, "front": {"type": "drawer"}}]},
                {"id": "wall-b", "height": 220, "depth": 60,
                 "cornice": {"height": 6}, "plinth": {"height": 12},
                 "bays": [{"id": "bay-1", "size_cm": 90, "front": {"type": "appliance"}},
                          {"id": "bay-2", "flex": 1, "split": "rows",
                           "children": [{"id": "row-1", "flex": 1, "front": {"type": "glass"}},
                                        {"id": "row-2", "flex": 2, "front": {"type": "door"}}]},
                          {"id": "bay-3", "flex": 1, "front": {"type": "drawer", "count": 3}}]},
                {"id": "wall-c", "height": 220, "depth": 60,
                 "cornice": {"height": 6}, "plinth": {"height": 12},
                 "bays": [{"id": "bay-1", "flex": 1, "front": {"type": "open"}}]},
            ],
        }
    )


def galley() -> Spec:
    """Two runs facing each other across an aisle. Never adjacent."""
    return build_spec(
        {
            "name": "Galley kitchen",
            "layout": {
                "type": "galley",
                "walls": [
                    {"id": "wall-a", "label": "Sink run", "length": 320, "sequence": 0,
                     "faces": ["wall-b"]},
                    {"id": "wall-b", "label": "Hob run", "length": 320, "sequence": 1,
                     "faces": ["wall-a"]},
                ],
            },
            "walls": [
                {"id": "wall-a", "height": 220, "depth": 60,
                 "plinth": {"height": 12},
                 "bays": [{"id": "bay-1", "size_cm": 120, "front": {"type": "drawer", "count": 3}},
                          {"id": "bay-2", "flex": 1, "front": {"type": "door"}}]},
                {"id": "wall-b", "height": 220, "depth": 60,
                 "plinth": {"height": 12},
                 "bays": [{"id": "bay-1", "flex": 1, "front": {"type": "door"}}]},
            ],
        }
    )


def four_walls() -> Spec:
    """A closed ring. Every wall yields the corner at its start (D6 + wrap)."""
    walls = [("wall-a", 400), ("wall-b", 300), ("wall-c", 400), ("wall-d", 300)]
    ids = [w[0] for w in walls]
    layout = []
    design = []
    for i, (wall_id, length) in enumerate(walls):
        prev_id = ids[(i - 1) % 4]
        next_id = ids[(i + 1) % 4]
        layout.append({
            "id": wall_id, "label": wall_id.upper(), "length": length, "sequence": i,
            "adjacent_to": sorted({prev_id, next_id}),
            "faces": [ids[(i + 2) % 4]],
            "corner": {"start": "yield", "end": "take"},
        })
        design.append({
            "id": wall_id, "height": 240, "depth": 60,
            "cornice": {"height": 8}, "plinth": {"height": 10},
            "bays": [{"id": "bay-1", "flex": 1, "front": {"type": "door"}},
                     {"id": "bay-2", "flex": 1, "front": {"type": "drawer", "count": 2}}],
        })
    return build_spec({"name": "Four-wall room", "layout": {"type": "custom", "walls": layout},
                       "walls": design})


def nightstand() -> Spec:
    """40 cm wide, 50 cm tall. The small end of the readability gate."""
    return build_spec(
        {
            "name": "Nightstand",
            "layout": {"type": "straight",
                       "walls": [{"id": "wall-a", "label": "Front", "length": 40, "sequence": 0}]},
            "walls": [
                {"id": "wall-a", "height": 50, "depth": 40, "plinth": {"height": 6},
                 "bays": [{"id": "bay-1", "flex": 1, "front": {"type": "drawer", "count": 2}}]}
            ],
        }
    )


def long_run() -> Spec:
    """6 m of cabinetry. The large end of the readability gate."""
    return build_spec(
        {
            "name": "Six metre run",
            "layout": {"type": "straight",
                       "walls": [{"id": "wall-a", "label": "Long wall", "length": 600, "sequence": 0}]},
            "walls": [
                {"id": "wall-a", "height": 240, "depth": 60,
                 "cornice": {"height": 8}, "plinth": {"height": 12},
                 "side_columns": {"left_cm": 6, "right_cm": 6, "detail": "plain"},
                 "bays": [{"id": "bay-1", "size_cm": 90, "front": {"type": "appliance"}},
                          {"id": "bay-2", "flex": 1, "front": {"type": "drawer", "count": 4}},
                          {"id": "bay-3", "flex": 2, "split": "rows",
                           "children": [{"id": "row-1", "size_cm": 60, "front": {"type": "glass"}},
                                        {"id": "row-2", "flex": 1, "front": {"type": "door"}}]},
                          {"id": "bay-4", "flex": 1, "front": {"type": "open"}}]},
            ],
        }
    )


def two_doors() -> Spec:
    """straight_wall with the top of bay-1 split into a side-by-side pair.

    Carries the build-1 regression (plan 3.1) all the way through to the
    drawing layer, so the solver tests can see two doors actually drawn side
    by side rather than trusting the model alone.
    """
    from app.models.ops import Split, apply_op

    return apply_op(straight_wall(), Split(path="wall-a/bay-1/row-1", axis="cols"))
