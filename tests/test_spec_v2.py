"""Spec v2 invariants (plan 5.3) and the one sizing rule (I3)."""
from __future__ import annotations

import pytest

from app.models.paths import describe, list_paths, resolve
from app.models.spec import SpecError, SplitAxis, build_spec, distribute
from tests.v2_factory import l_kitchen, straight_wall


# -- the sizing rule ------------------------------------------------------


def test_flex_absorbs_the_remainder():
    spec = straight_wall()
    # 300 cm run, two 100 cm bays fixed, the third is flex.
    assert distribute(spec.design_wall("wall-a").bays, 300) == [100, 100, 100]


def test_nested_flex_absorbs_the_remainder():
    spec = straight_wall()
    bay = resolve(spec, "wall-a/bay-1")
    row_2 = resolve(spec, "wall-a/bay-1/row-2")
    # inner height 200, row-1 pinned at 60, so row-2 takes 140.
    assert bay.box_h == pytest.approx(200)
    assert row_2.box_h == pytest.approx(140)


def test_overflow_is_unrepresentable_not_merely_invalid():
    """Build 1 bug 3.3: a stack taller than its opening drew off the sheet.

    With flex there is no arithmetic for the author to get wrong.
    """
    spec = straight_wall()
    data = spec.model_dump(mode="json")
    rows = data["walls"][0]["bays"][0]["children"]
    rows[0]["size_cm"] = 190  # row-2 is flex, so it simply shrinks to 10
    rebuilt = build_spec(data)
    assert resolve(rebuilt, "wall-a/bay-1/row-2").box_h == pytest.approx(10)


def test_fixed_siblings_over_budget_are_rejected():
    spec = straight_wall()
    data = spec.model_dump(mode="json")
    rows = data["walls"][0]["bays"][0]["children"]
    rows[0]["size_cm"] = 150
    rows[1] = {"id": "row-2", "size_cm": 150, "front": {"type": "drawer"}}
    with pytest.raises(SpecError, match="only 200.0 cm is available"):
        build_spec(data)


def test_all_fixed_must_fill_the_opening():
    spec = straight_wall()
    data = spec.model_dump(mode="json")
    data["walls"][0]["bays"][2] = {
        "id": "bay-3",
        "size_cm": 50,  # 100 + 100 + 50 != 300, and nothing is flex
        "front": {"type": "door"},
    }
    with pytest.raises(SpecError, match="Either make one child flex"):
        build_spec(data)


def test_flex_squeezed_to_nothing_is_an_error_not_a_sliver():
    spec = straight_wall()
    data = spec.model_dump(mode="json")
    data["walls"][0]["bays"][1]["size_cm"] = 200  # 100 + 200 = the whole run
    with pytest.raises(SpecError, match="nothing left for it"):
        build_spec(data)


def test_tolerance_allows_a_centimetre_of_slop():
    spec = straight_wall()
    data = spec.model_dump(mode="json")
    data["walls"][0]["bays"] = [
        {"id": "bay-1", "size_cm": 150, "front": {"type": "door"}},
        {"id": "bay-2", "size_cm": 149.5, "front": {"type": "door"}},
    ]
    build_spec(data)  # 299.5 vs 300 is inside FIT_TOLERANCE_CM


# -- count normalisation (D5) ---------------------------------------------


def test_front_count_expands_into_addressable_nodes():
    spec = straight_wall()
    data = spec.model_dump(mode="json")
    data["walls"][0]["bays"][1] = {
        "id": "bay-2",
        "size_cm": 100,
        "front": {"type": "drawer", "count": 3},
    }
    rebuilt = build_spec(data)

    bay = resolve(rebuilt, "wall-a/bay-2")
    assert bay.node.split is SplitAxis.ROWS
    assert bay.node.front is None
    assert [c.id for c in bay.node.children] == ["drawer-1", "drawer-2", "drawer-3"]
    # each drawer is now a real node with its own height
    assert resolve(rebuilt, "wall-a/bay-2/drawer-2").box_h == pytest.approx(200 / 3)


def test_stored_specs_never_keep_count_above_one():
    spec = straight_wall()
    data = spec.model_dump(mode="json")
    data["walls"][0]["bays"][1]["front"] = {"type": "drawer", "count": 4}
    rebuilt = build_spec(data)
    for _, node in rebuilt.design_wall("wall-a").bays[1].walk():
        if node.front is not None:
            assert node.front.count == 1


# -- node shape (I5) ------------------------------------------------------


def test_leaf_without_a_front_is_rejected():
    with pytest.raises(SpecError, match="leaf needs a front"):
        build_spec(
            {
                "layout": {"walls": [{"id": "wall-a", "length": 100}]},
                "walls": [{"id": "wall-a", "bays": [{"id": "bay-1", "flex": 1}]}],
            }
        )


def test_split_node_cannot_carry_a_front():
    with pytest.raises(SpecError, match="cannot carry a front"):
        build_spec(
            {
                "layout": {"walls": [{"id": "wall-a", "length": 100}]},
                "walls": [
                    {
                        "id": "wall-a",
                        "bays": [
                            {
                                "id": "bay-1",
                                "flex": 1,
                                "split": "rows",
                                "front": {"type": "door"},
                                "children": [
                                    {"id": "row-1", "flex": 1, "front": {"type": "door"}},
                                    {"id": "row-2", "flex": 1, "front": {"type": "door"}},
                                ],
                            }
                        ],
                    }
                ],
            }
        )


def test_split_needs_at_least_two_children():
    with pytest.raises(SpecError, match="at least 2 children"):
        build_spec(
            {
                "layout": {"walls": [{"id": "wall-a", "length": 100}]},
                "walls": [
                    {
                        "id": "wall-a",
                        "bays": [
                            {
                                "id": "bay-1",
                                "flex": 1,
                                "split": "cols",
                                "children": [
                                    {"id": "col-1", "flex": 1, "front": {"type": "door"}}
                                ],
                            }
                        ],
                    }
                ],
            }
        )


def test_size_and_flex_are_mutually_exclusive():
    with pytest.raises(SpecError, match="not both"):
        build_spec(
            {
                "layout": {"walls": [{"id": "wall-a", "length": 100}]},
                "walls": [
                    {
                        "id": "wall-a",
                        "bays": [
                            {
                                "id": "bay-1",
                                "size_cm": 100,
                                "flex": 1,
                                "front": {"type": "door"},
                            }
                        ],
                    }
                ],
            }
        )


def test_sibling_ids_must_be_unique_but_may_repeat_across_parents():
    spec = l_kitchen()
    # both walls legitimately have a "bay-1"
    assert resolve(spec, "wall-a/bay-1").node is not resolve(spec, "wall-b/bay-1").node

    data = spec.model_dump(mode="json")
    data["walls"][0]["bays"][1]["id"] = "bay-1"
    with pytest.raises(SpecError, match="bay ids must be unique"):
        build_spec(data)


# -- graph (I1, I2) -------------------------------------------------------


def test_wall_id_sets_must_match():
    spec = straight_wall()
    data = spec.model_dump(mode="json")
    data["walls"][0]["id"] = "wall-z"
    with pytest.raises(SpecError, match="must match"):
        build_spec(data)


def test_adjacency_must_be_symmetric():
    spec = l_kitchen()
    data = spec.model_dump(mode="json")
    data["layout"]["walls"][1]["adjacent_to"] = []
    with pytest.raises(SpecError, match="symmetric"):
        build_spec(data)


def test_a_pair_cannot_be_both_adjacent_and_facing():
    spec = l_kitchen()
    data = spec.model_dump(mode="json")
    data["layout"]["walls"][0]["faces"] = ["wall-b"]
    data["layout"]["walls"][1]["faces"] = ["wall-a"]
    with pytest.raises(SpecError, match="cannot both face and be adjacent"):
        build_spec(data)


# -- corners (plan 7.2, the fix for build 1 bug 3.4) ----------------------


def test_yielding_wall_gives_up_the_neighbours_depth():
    spec = l_kitchen()
    assert spec.usable_length("wall-a") == 320  # takes the corner
    assert spec.usable_length("wall-b") == 180  # 240 - 60 yielded


def test_corner_square_is_counted_once():
    """Build 1 let both runs claim the same 60x60 corner."""
    spec = l_kitchen()
    total = spec.usable_length("wall-a") + spec.usable_length("wall-b")
    raw = sum(w.length for w in spec.layout.walls)
    assert raw - total == pytest.approx(60)


def test_yield_without_a_neighbour_is_rejected():
    spec = straight_wall()
    data = spec.model_dump(mode="json")
    data["layout"]["walls"][0]["corner"] = {"start": "yield"}
    with pytest.raises(SpecError, match="no adjacent wall"):
        build_spec(data)


def test_side_columns_consume_width_rather_than_overlapping_bays():
    """Build 1 drew side columns on top of the bays (progress D9)."""
    spec = straight_wall()
    data = spec.model_dump(mode="json")
    data["walls"][0]["side_columns"] = {"left_cm": 8, "right_cm": 8, "detail": "plain"}
    rebuilt = build_spec(data)
    assert rebuilt.bay_extent("wall-a") == 284
    assert resolve(rebuilt, "wall-a/bay-3").box_w == pytest.approx(84)


# -- paths (D4) -----------------------------------------------------------


def test_paths_resolve_to_the_right_box():
    spec = straight_wall()
    ref = resolve(spec, "wall-a/bay-1/row-1")
    assert ref.box_w == pytest.approx(100)
    assert ref.box_h == pytest.approx(60)
    assert ref.parent is not None and ref.parent.id == "bay-1"
    assert ref.axis is SplitAxis.ROWS


def test_unknown_segment_lists_what_is_available():
    spec = straight_wall()
    with pytest.raises(SpecError, match="Available: row-1, row-2"):
        resolve(spec, "wall-a/bay-1/row-9")


def test_descending_into_a_leaf_is_a_clear_error():
    spec = straight_wall()
    with pytest.raises(SpecError, match="is a leaf"):
        resolve(spec, "wall-a/bay-2/row-1")


def test_list_paths_covers_every_node_in_drawing_order():
    spec = straight_wall()
    assert list_paths(spec, "wall-a") == [
        "wall-a/bay-1",
        "wall-a/bay-1/row-1",
        "wall-a/bay-1/row-2",
        "wall-a/bay-2",
        "wall-a/bay-3",
    ]


def test_describe_reports_real_centimetres():
    spec = straight_wall()
    rows = {row["path"]: row for row in describe(spec, "wall-a")}
    assert rows["wall-a/bay-1/row-2"]["h_cm"] == 140.0
    assert rows["wall-a/bay-1/row-2"]["front"] == "drawer"
