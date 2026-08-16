import unittest

from pydantic import ValidationError

from app.models.furniture_spec import (
    BaySpec,
    DesignWall,
    FurnitureSpec,
    LayoutSpec,
    LayoutType,
    LayoutWall,
)
from tests.spec_factory import l_spec, spec_from_walls, straight_spec, u_spec


class FurnitureSpecValidationTests(unittest.TestCase):
    def test_valid_straight_spec_loads(self):
        spec = straight_spec()
        self.assertEqual(spec.wall_ids(), ["wall-a"])

    def test_bay_widths_must_sum_to_wall_length(self):
        with self.assertRaises(ValidationError) as ctx:
            FurnitureSpec(
                layout=LayoutSpec(
                    type=LayoutType.STRAIGHT,
                    walls=[
                        LayoutWall(id="wall-a", label="A", length=300, sequence=0)
                    ],
                ),
                walls=[
                    DesignWall(
                        id="wall-a",
                        bays=[
                            BaySpec(id="b1", width=100),
                            BaySpec(id="b2", width=100),
                        ],
                    )
                ],
            )
        self.assertIn("bay widths", str(ctx.exception))

    def test_bay_sum_within_one_cm_is_allowed(self):
        spec = FurnitureSpec(
            layout=LayoutSpec(
                type=LayoutType.STRAIGHT,
                walls=[
                    LayoutWall(id="wall-a", label="A", length=300, sequence=0)
                ],
            ),
            walls=[
                DesignWall(
                    id="wall-a",
                    bays=[
                        BaySpec(id="b1", width=149.6),
                        BaySpec(id="b2", width=150.0),
                    ],
                )
            ],
        )
        self.assertEqual(spec.layout_wall("wall-a").length, 300)

    def test_adjacent_to_must_be_symmetric(self):
        with self.assertRaises(ValidationError) as ctx:
            spec_from_walls(
                LayoutType.L,
                [
                    LayoutWall(
                        id="wall-a",
                        length=100,
                        adjacent_to=["wall-b"],
                        sequence=0,
                    ),
                    LayoutWall(
                        id="wall-b",
                        length=100,
                        adjacent_to=[],
                        sequence=1,
                    ),
                ],
            )
        self.assertIn("symmetric", str(ctx.exception))

    def test_cannot_face_and_be_adjacent_to_same_wall(self):
        with self.assertRaises(ValidationError) as ctx:
            spec_from_walls(
                LayoutType.CUSTOM,
                [
                    LayoutWall(
                        id="wall-a",
                        length=100,
                        adjacent_to=["wall-b"],
                        faces=["wall-b"],
                        sequence=0,
                    ),
                    LayoutWall(
                        id="wall-b",
                        length=100,
                        adjacent_to=["wall-a"],
                        faces=["wall-a"],
                        sequence=1,
                    ),
                ],
            )
        self.assertIn("cannot both face and be adjacent", str(ctx.exception))

    def test_layout_and_design_ids_must_match(self):
        with self.assertRaises(ValidationError):
            FurnitureSpec(
                layout=LayoutSpec(
                    type=LayoutType.STRAIGHT,
                    walls=[LayoutWall(id="wall-a", length=100, sequence=0)],
                ),
                walls=[DesignWall(id="wall-b")],
            )

    def test_u_spec_facing_and_adjacency_helpers(self):
        spec = u_spec()
        self.assertTrue(spec.can_share_camera("wall-a", "wall-b"))
        self.assertTrue(spec.can_share_camera("wall-b", "wall-c"))
        self.assertFalse(spec.can_share_camera("wall-a", "wall-c"))
        self.assertTrue(spec.is_facing("wall-a", "wall-c"))

    def test_l_spec_can_share_only_the_corner(self):
        spec = l_spec()
        self.assertTrue(spec.can_share_camera("wall-a", "wall-b"))
        self.assertFalse(spec.can_share_camera("wall-a", "wall-a"))


if __name__ == "__main__":
    unittest.main()
