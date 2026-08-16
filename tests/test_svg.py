import math
import unittest
from pathlib import Path

from app.planner.views import plan_views
from app.render.geometry import place_walls
from app.render.svg_elevation import elevation_svg
from app.render.svg_plan import plan_svg
from tests.spec_factory import (
    four_wall_spec,
    galley_spec,
    l_kitchen_spec,
    l_spec,
    straight_spec,
    u_spec,
)

GOLDEN_DIR = Path(__file__).parent / "golden"


def _almost(a, b, places=5):
    return math.isclose(a[0], b[0], abs_tol=10 ** (-places)) and math.isclose(
        a[1], b[1], abs_tol=10 ** (-places)
    )


class GeometryTests(unittest.TestCase):
    def test_l_walls_meet_at_right_angle(self):
        a, b = place_walls(l_spec())
        self.assertTrue(_almost(a.back_end, b.back_start), (a.back_end, b.back_start))
        dot = a.direction[0] * b.direction[0] + a.direction[1] * b.direction[1]
        self.assertAlmostEqual(dot, 0.0, places=6)

    def test_four_wall_loop_closes(self):
        fps = place_walls(four_wall_spec())
        self.assertEqual(len(fps), 4)
        self.assertTrue(_almost(fps[-1].back_end, fps[0].back_start))

    def test_galley_fronts_face_each_other_with_aisle(self):
        a, b = place_walls(galley_spec())
        self.assertAlmostEqual(a.inward[0] + b.inward[0], 0.0, places=6)
        self.assertAlmostEqual(a.inward[1] + b.inward[1], 0.0, places=6)
        gap = abs(b.front_start[1] - a.front_start[1])
        self.assertAlmostEqual(gap, 120.0, places=5)

    def test_u_has_three_footprints(self):
        self.assertEqual(len(place_walls(u_spec())), 3)


class SvgTests(unittest.TestCase):
    def test_plan_is_svg_and_labels_each_wall(self):
        svg = plan_svg(l_kitchen_spec())
        self.assertTrue(svg.startswith("<?xml"))
        self.assertIn("<svg", svg)
        self.assertIn('data-wall-id="wall-a"', svg)
        self.assertIn('data-wall-id="wall-b"', svg)
        self.assertIn("300 cm", svg)
        self.assertIn("180 cm", svg)

    def test_elevation_has_cornice_plinth_bays(self):
        svg = elevation_svg(l_kitchen_spec(), "wall-a")
        self.assertIn('data-wall-id="wall-a"', svg)
        self.assertIn('class="cornice"', svg)
        self.assertIn('class="plinth"', svg)
        self.assertIn('data-bay-id="bay-1"', svg)
        self.assertIn('data-bay-id="bay-4"', svg)
        self.assertIn("module-open_shelf", svg)
        self.assertIn("220 cm", svg)
        self.assertIn("300 cm", svg)

    def test_planner_elevations_each_render(self):
        spec = l_kitchen_spec()
        plan = plan_views(spec)
        self.assertEqual(len(plan.elevations), 2)
        for job in plan.elevations:
            svg = elevation_svg(spec, job.wall_id)
            self.assertIn(f'data-wall-id="{job.wall_id}"', svg)

    def test_straight_plan_has_one_footprint(self):
        svg = plan_svg(straight_spec())
        self.assertEqual(svg.count("wall-footprint"), 1)

    def test_l_kitchen_plan_matches_golden(self):
        self._assert_golden("l_kitchen_plan.svg", plan_svg(l_kitchen_spec()))

    def test_l_kitchen_elevation_a_matches_golden(self):
        self._assert_golden(
            "l_kitchen_elev_wall_a.svg",
            elevation_svg(l_kitchen_spec(), "wall-a"),
        )

    def test_l_kitchen_elevation_b_matches_golden(self):
        self._assert_golden(
            "l_kitchen_elev_wall_b.svg",
            elevation_svg(l_kitchen_spec(), "wall-b"),
        )

    def _assert_golden(self, filename: str, actual: str) -> None:
        path = GOLDEN_DIR / filename
        self.assertTrue(path.exists(), f"missing golden file {path}")
        expected = path.read_text(encoding="utf-8").replace("\r\n", "\n")
        self.assertEqual(actual.replace("\r\n", "\n"), expected)


if __name__ == "__main__":
    unittest.main()
