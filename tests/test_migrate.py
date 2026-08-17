"""Build 1 spec -> spec v2, including the real sessions on disk."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.models.migrate import migrate_session, migrate_v1
from app.models.paths import resolve
from app.models.spec import FrontType, SplitAxis
from tests.v2_factory import v1_wardrobe

SESSIONS = Path(__file__).resolve().parents[1] / "data" / "sessions"


def test_a_v1_wall_becomes_a_valid_v2_spec():
    spec, _ = migrate_v1(v1_wardrobe())
    assert spec.name == "Storage wall"
    assert spec.materials.carcass == "birch ply"
    assert [bay.id for bay in spec.design_wall("wall-a").bays] == [
        "bay-1",
        "bay-2",
        "bay-3",
    ]


def test_modules_flip_from_bottom_first_to_top_first():
    """v1 stacked modules upward from the plinth; v2 rows read top-down."""
    spec, _ = migrate_v1(v1_wardrobe())
    bay = resolve(spec, "wall-a/bay-1")
    assert bay.node.split is SplitAxis.ROWS

    heights = [child.size_cm for child in bay.node.children]
    assert heights == [85.0, 35.0, 80.0]  # v1 listed 80, 35, 85 bottom-up
    assert resolve(spec, "wall-a/bay-1/door-1").box_h == pytest.approx(85)


def test_v1_count_becomes_individually_addressable_nodes():
    """A 4-drawer bank was one module with count=4 and no way to touch one."""
    spec, _ = migrate_v1(v1_wardrobe())
    bay = resolve(spec, "wall-a/bay-2")
    assert [child.id for child in bay.node.children] == [
        "door-1",
        "drawer-2",
        "drawer-3",
        "drawer-4",
        "drawer-5",
    ]
    assert resolve(spec, "wall-a/bay-2/drawer-3").box_h == pytest.approx(25)


def test_a_single_module_bay_stays_a_leaf():
    spec, _ = migrate_v1(v1_wardrobe())
    bay = resolve(spec, "wall-a/bay-3")
    assert bay.node.is_leaf()
    assert bay.node.front.type is FrontType.DOOR
    assert bay.node.front.handle == "knob"


def test_side_columns_now_take_width_and_the_last_bay_absorbs_it():
    """v1 bays summed to the full 360 cm while side columns overlapped them.

    v2 gives the columns real width, so 16 cm has to come from somewhere.
    Stated widths are kept; the last bay flexes (progress D9).
    """
    spec, report = migrate_v1(v1_wardrobe())
    assert spec.bay_extent("wall-a") == pytest.approx(344)

    assert resolve(spec, "wall-a/bay-1").box_w == pytest.approx(60)
    assert resolve(spec, "wall-a/bay-2").box_w == pytest.approx(240)
    assert resolve(spec, "wall-a/bay-3").box_w == pytest.approx(44)

    assert any("absorbs the difference" in note for note in report)


def test_every_adjustment_is_recorded_as_an_assumption():
    """I8 — the user must be able to see what the system decided."""
    spec, _ = migrate_v1(v1_wardrobe())
    assert spec.assumptions
    assert spec.assumptions[0].field == "wall-a.bays"
    assert "344" in spec.assumptions[0].rationale


def test_corner_defaults_make_the_later_wall_yield():
    data = v1_wardrobe()
    data["layout"]["type"] = "L"
    data["layout"]["walls"][0]["adjacent_to"] = ["wall-b"]
    data["layout"]["walls"].append(
        {
            "id": "wall-b",
            "label": "Wall B",
            "length": 240.0,
            "adjacent_to": ["wall-a"],
            "faces": [],
            "sequence": 1,
        }
    )
    data["walls"].append(
        {
            "id": "wall-b",
            "height": 220.0,
            "depth": 60.0,
            "cornice": {"type": "straight", "height": 10.0},
            "plinth": {"type": "recessed", "height": 10.0},
            "side_columns": {"left_cm": 0.0, "right_cm": 0.0, "detail": "plain"},
            "bays": [
                {
                    "id": "bay-1",
                    "label": "Run",
                    "width": 240.0,
                    "modules": [
                        {"type": "door", "height": 200.0, "count": 1, "handle": "bar"}
                    ],
                }
            ],
        }
    )

    spec, report = migrate_v1(data)
    assert spec.usable_length("wall-a") == 360  # takes the corner
    assert spec.usable_length("wall-b") == 180  # yields wall-a's 60 cm depth
    assert any("yields the corner" in note for note in report)


# -- the real files -------------------------------------------------------


def _session_specs() -> list[tuple[str, dict]]:
    if not SESSIONS.is_dir():
        return []
    found = []
    for path in sorted(SESSIONS.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        if isinstance(data, dict) and data.get("spec"):
            found.append((path.name, data))
    return found


REAL_SESSIONS = _session_specs()


@pytest.mark.skipif(not REAL_SESSIONS, reason="no build-1 sessions on disk")
@pytest.mark.parametrize("name,session", REAL_SESSIONS, ids=[n for n, _ in REAL_SESSIONS])
def test_real_build_1_sessions_migrate(name: str, session: dict):
    spec, report = migrate_session(session)
    assert spec is not None
    # Every wall must survive with a usable run and bays that fit.
    for wall in spec.walls:
        assert spec.bay_extent(wall.id) > 0
        for bay in wall.bays:
            assert resolve(spec, f"{wall.id}/{bay.id}").box_w > 0
    assert isinstance(report, list)
