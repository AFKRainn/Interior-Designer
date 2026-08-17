"""Edit operations — the only way a spec changes (plan 9.4)."""
from __future__ import annotations

import pytest

from app.models.ops import (
    OP_ADAPTER,
    AddChild,
    Delete,
    InsertBay,
    Merge,
    OpError,
    SetCorner,
    SetFlex,
    SetFront,
    SetHardware,
    SetLabel,
    SetMaterials,
    SetSize,
    SetWall,
    Split,
    apply_op,
    apply_ops,
)
from app.models.paths import resolve
from app.models.spec import CornerMode, FrontType, Hinge, SplitAxis
from tests.v2_factory import l_kitchen, straight_wall


# -- the regression that justifies the whole rewrite ----------------------


def test_two_doors_next_to_each_other_on_the_top_part():
    """The exact request build 1 could not represent (plan 3.1).

    Modules were always full bay width and `count` repeated vertically, so
    side-by-side fronts had no representation and the model quietly did
    something else. One op now expresses it.
    """
    spec = straight_wall()
    before = resolve(spec, "wall-a/bay-1/row-1")
    assert before.node.front.type is FrontType.DOOR

    updated = apply_op(spec, Split(path="wall-a/bay-1/row-1", axis=SplitAxis.COLS))

    row = resolve(updated, "wall-a/bay-1/row-1")
    assert row.node.split is SplitAxis.COLS
    assert [child.id for child in row.node.children] == ["col-1", "col-2"]
    assert [child.front.type for child in row.node.children] == [
        FrontType.DOOR,
        FrontType.DOOR,
    ]

    left = resolve(updated, "wall-a/bay-1/row-1/col-1")
    right = resolve(updated, "wall-a/bay-1/row-1/col-2")
    # side by side: full height each, half the width each
    assert left.box_h == right.box_h == pytest.approx(row.box_h)
    assert left.box_w == right.box_w == pytest.approx(row.box_w / 2)
    # and a door pair hinges outward from the middle
    assert (left.node.front.hinge, right.node.front.hinge) == (Hinge.LEFT, Hinge.RIGHT)


def test_the_rest_of_the_wall_is_untouched_by_a_split():
    """Build 1 rewrote the whole document on every edit (plan 3.6)."""
    spec = straight_wall()
    updated = apply_op(spec, Split(path="wall-a/bay-1/row-1", axis=SplitAxis.COLS))

    for path in ("wall-a/bay-1/row-2", "wall-a/bay-2", "wall-a/bay-3"):
        assert resolve(updated, path).node == resolve(spec, path).node
    assert updated.materials == spec.materials
    assert updated.brief == spec.brief


# -- sizing ---------------------------------------------------------------


def test_set_size_moves_the_flex_neighbour():
    spec = straight_wall()
    updated = apply_op(spec, SetSize(path="wall-a/bay-1", size_cm=140))
    assert resolve(updated, "wall-a/bay-1").box_w == pytest.approx(140)
    assert resolve(updated, "wall-a/bay-3").box_w == pytest.approx(60)


def test_a_rejected_op_changes_nothing():
    spec = straight_wall()
    with pytest.raises(OpError, match="would break the spec"):
        apply_op(spec, SetSize(path="wall-a/bay-1", size_cm=280))
    assert resolve(spec, "wall-a/bay-1").box_w == pytest.approx(100)
    assert spec.version == 1


def test_set_flex_releases_a_pinned_size():
    spec = straight_wall()
    updated = apply_op(spec, SetFlex(path="wall-a/bay-2", flex=1))
    bay_2 = resolve(updated, "wall-a/bay-2")
    assert bay_2.node.size_cm is None
    # bay-1 stays at 100; bay-2 and bay-3 share the remaining 200
    assert bay_2.box_w == pytest.approx(100)


def test_every_applied_op_bumps_the_version():
    spec = straight_wall()
    updated = apply_op(spec, SetLabel(path="wall-a/bay-2", label="Sink"))
    assert updated.version == spec.version + 1
    assert resolve(updated, "wall-a/bay-2").node.label == "Sink"


# -- structure ------------------------------------------------------------


def test_split_with_ratios():
    spec = straight_wall()
    updated = apply_op(
        spec, Split(path="wall-a/bay-2", axis=SplitAxis.ROWS, ratios=[3, 1])
    )
    top = resolve(updated, "wall-a/bay-2/row-1")
    bottom = resolve(updated, "wall-a/bay-2/row-2")
    assert top.box_h == pytest.approx(150)
    assert bottom.box_h == pytest.approx(50)


def test_split_an_already_split_node_is_refused_with_advice():
    spec = straight_wall()
    with pytest.raises(OpError, match="Merge it first"):
        apply_op(spec, Split(path="wall-a/bay-1", axis=SplitAxis.COLS))


def test_merge_collapses_back_to_one_front():
    spec = straight_wall()
    updated = apply_op(spec, Merge(path="wall-a/bay-1"))
    bay = resolve(updated, "wall-a/bay-1")
    assert bay.node.is_leaf()
    assert bay.node.front.type is FrontType.DOOR  # the first descendant front


def test_add_child_extends_a_stack():
    spec = straight_wall()
    updated = apply_op(
        spec, AddChild(path="wall-a/bay-1", front_type=FrontType.OPEN)
    )
    bay = resolve(updated, "wall-a/bay-1")
    assert [child.id for child in bay.node.children] == ["row-1", "row-2", "row-3"]
    assert resolve(updated, "wall-a/bay-1/row-3").node.front.type is FrontType.OPEN


def test_add_child_to_a_leaf_says_split_it_first():
    spec = straight_wall()
    with pytest.raises(OpError, match="split it before adding children"):
        apply_op(spec, AddChild(path="wall-a/bay-2"))


def test_deleting_one_of_two_leaves_the_survivor_filling_the_opening():
    """A one-child split is illegal, so the parent absorbs the survivor."""
    spec = apply_op(straight_wall(), Split(path="wall-a/bay-1/row-1", axis=SplitAxis.COLS))
    updated = apply_op(spec, Delete(path="wall-a/bay-1/row-1/col-2"))

    row = resolve(updated, "wall-a/bay-1/row-1")
    assert row.node.is_leaf()
    assert row.node.front.type is FrontType.DOOR
    assert row.box_w == pytest.approx(100)  # the full bay again


def test_delete_a_bay():
    spec = straight_wall()
    updated = apply_op(spec, Delete(path="wall-a/bay-2"))
    assert [bay.id for bay in updated.design_wall("wall-a").bays] == ["bay-1", "bay-3"]
    assert resolve(updated, "wall-a/bay-3").box_w == pytest.approx(200)


def test_insert_bay_defaults_to_flex_so_it_always_fits():
    spec = straight_wall()
    updated = apply_op(spec, InsertBay(wall_id="wall-a", index=0, label="New"))
    bays = updated.design_wall("wall-a").bays
    assert bays[0].id == "bay-4" and bays[0].label == "New"
    # bay-3 and the newcomer now share the 100 cm the fixed bays leave
    assert resolve(updated, "wall-a/bay-4").box_w == pytest.approx(50)


# -- fronts ---------------------------------------------------------------


def test_set_front_with_count_builds_a_stack():
    spec = straight_wall()
    updated = apply_op(
        spec, SetFront(path="wall-a/bay-2", type=FrontType.DRAWER, count=3)
    )
    bay = resolve(updated, "wall-a/bay-2")
    assert bay.node.split is SplitAxis.ROWS
    assert [child.id for child in bay.node.children] == [
        "drawer-1",
        "drawer-2",
        "drawer-3",
    ]


def test_set_front_keeps_the_handle_when_not_given():
    spec = apply_op(
        straight_wall(),
        SetFront(path="wall-a/bay-2", type=FrontType.DOOR, handle="bar"),
    )
    updated = apply_op(spec, SetFront(path="wall-a/bay-2", type=FrontType.GLASS))
    assert resolve(updated, "wall-a/bay-2").node.front.handle == "bar"


def test_set_front_on_a_split_node_is_refused():
    spec = straight_wall()
    with pytest.raises(OpError, match="merge it first"):
        apply_op(spec, SetFront(path="wall-a/bay-1", type=FrontType.DOOR))


# -- wall level -----------------------------------------------------------


def test_set_wall_length_reflows_the_bays():
    spec = straight_wall()
    updated = apply_op(spec, SetWall(wall_id="wall-a", length=400))
    assert resolve(updated, "wall-a/bay-3").box_w == pytest.approx(200)


def test_set_wall_side_columns_take_width_from_the_bays():
    spec = straight_wall()
    updated = apply_op(
        spec, SetWall(wall_id="wall-a", side_left_cm=8, side_right_cm=8)
    )
    assert updated.bay_extent("wall-a") == pytest.approx(284)
    assert resolve(updated, "wall-a/bay-3").box_w == pytest.approx(84)


def test_set_corner_changes_the_usable_run():
    spec = l_kitchen()
    assert spec.usable_length("wall-a") == 320
    updated = apply_op(
        spec, SetCorner(wall_id="wall-a", end="end", mode=CornerMode.YIELD)
    )
    assert updated.usable_length("wall-a") == 260  # 320 - wall-b depth


def test_materials_and_hardware_patch_only_named_fields():
    spec = straight_wall()
    spec = apply_op(spec, SetMaterials(carcass="birch ply", finish="matt"))
    spec = apply_op(spec, SetMaterials(finish="satin"))
    assert spec.materials.carcass == "birch ply"
    assert spec.materials.finish == "satin"

    spec = apply_op(spec, SetHardware(style="bar"))
    assert spec.hardware.style == "bar"


# -- batches and parsing --------------------------------------------------


def test_apply_ops_is_all_or_nothing():
    spec = straight_wall()
    ops = [
        SetLabel(path="wall-a/bay-2", label="Sink"),
        SetSize(path="wall-a/bay-2", size_cm=999),  # impossible
    ]
    with pytest.raises(OpError, match="op 2 of 2 failed"):
        apply_ops(spec, ops)
    assert resolve(spec, "wall-a/bay-2").node.label == ""


def test_apply_ops_records_the_log():
    spec = straight_wall()
    updated, records = apply_ops(
        spec,
        [
            Split(path="wall-a/bay-1/row-1", axis=SplitAxis.COLS),
            SetLabel(path="wall-a/bay-1/row-1/col-1", label="Left door"),
        ],
    )
    assert [r.version_before for r in records] == [1, 2]
    assert [r.version_after for r in records] == [2, 3]
    assert updated.version == 3


def test_ops_parse_from_plain_json_the_way_a_model_emits_them():
    """The edit agent returns JSON; the discriminator picks the op."""
    op = OP_ADAPTER.validate_python(
        {"kind": "split", "path": "wall-a/bay-1/row-1", "axis": "cols", "count": 2}
    )
    assert isinstance(op, Split)
    updated = apply_op(straight_wall(), op)
    assert resolve(updated, "wall-a/bay-1/row-1").node.split is SplitAxis.COLS


def test_an_unknown_path_names_what_is_available():
    spec = straight_wall()
    with pytest.raises(OpError, match="Available: bay-1, bay-2, bay-3"):
        apply_op(spec, SetSize(path="wall-a/bay-9", size_cm=50))
