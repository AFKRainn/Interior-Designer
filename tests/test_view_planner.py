import unittest

from app.planner.views import plan_views
from tests.spec_factory import (
    four_wall_spec,
    galley_spec,
    l_spec,
    straight_spec,
    u_spec,
)


def _wall_sets(plan):
    return [frozenset(job.walls) for job in plan.cameras]


class ViewPlannerTests(unittest.TestCase):
    def test_straight_one_elevation_one_frontal(self):
        plan = plan_views(straight_spec())
        self.assertEqual(len(plan.elevations), 1)
        self.assertEqual(plan.elevations[0].wall_id, "wall-a")
        self.assertEqual(plan.elevations[0].sheet, "elev-wall-a.svg")
        self.assertEqual(len(plan.cameras), 1)
        shot = plan.cameras[0]
        self.assertEqual(shot.camera, "frontal")
        self.assertEqual(shot.walls, ["wall-a"])
        self.assertEqual(shot.frame.left, "wall-a")
        self.assertIsNone(shot.frame.right)
        self.assertEqual(shot.exclude, [])
        self.assertEqual(shot.references, ["elev-wall-a.svg", "plan-cone.svg"])

    def test_l_two_elevations_one_corner(self):
        plan = plan_views(l_spec())
        self.assertEqual([e.wall_id for e in plan.elevations], ["wall-a", "wall-b"])
        self.assertEqual(len(plan.cameras), 1)
        shot = plan.cameras[0]
        self.assertEqual(shot.camera, "inside_corner")
        self.assertEqual(shot.walls, ["wall-a", "wall-b"])
        self.assertEqual(shot.frame.left, "wall-a")
        self.assertEqual(shot.frame.right, "wall-b")
        self.assertEqual(shot.exclude, [])
        self.assertEqual(
            shot.references,
            ["elev-wall-a.svg", "elev-wall-b.svg", "plan-cone.svg"],
        )

    def test_u_three_elevations_two_overlapping_corners(self):
        plan = plan_views(u_spec())
        self.assertEqual(len(plan.elevations), 3)
        self.assertEqual(len(plan.cameras), 2)
        self.assertEqual(_wall_sets(plan), [
            frozenset(["wall-a", "wall-b"]),
            frozenset(["wall-b", "wall-c"]),
        ])
        for shot in plan.cameras:
            self.assertEqual(shot.camera, "inside_corner")
            self.assertEqual(len(shot.walls), 2)
        self.assertEqual(plan.cameras[0].exclude, ["wall-c"])
        self.assertEqual(plan.cameras[1].exclude, ["wall-a"])
        self.assertNotIn("elev-wall-c.svg", plan.cameras[0].references)
        self.assertNotIn("elev-wall-a.svg", plan.cameras[1].references)
        self.assertTrue(self._covers_all(plan, ["wall-a", "wall-b", "wall-c"]))
        self.assertFalse(self._has_duplicate_sets(plan))

    def test_galley_two_frontals_never_one_shot(self):
        plan = plan_views(galley_spec())
        self.assertEqual(len(plan.elevations), 2)
        self.assertEqual(len(plan.cameras), 2)
        self.assertEqual(_wall_sets(plan), [
            frozenset(["wall-a"]),
            frozenset(["wall-b"]),
        ])
        for shot in plan.cameras:
            self.assertEqual(shot.camera, "frontal")
            self.assertEqual(len(shot.walls), 1)
        self.assertFalse(self._has_duplicate_sets(plan))

    def test_four_wall_opposite_corners_not_adjacent_corners(self):
        plan = plan_views(four_wall_spec())
        self.assertEqual(len(plan.elevations), 4)
        self.assertEqual(len(plan.cameras), 2)
        self.assertEqual(_wall_sets(plan), [
            frozenset(["wall-a", "wall-b"]),
            frozenset(["wall-c", "wall-d"]),
        ])
        self.assertNotIn(
            frozenset(["wall-b", "wall-c"]),
            _wall_sets(plan),
        )
        self.assertTrue(
            self._covers_all(plan, ["wall-a", "wall-b", "wall-c", "wall-d"])
        )
        self.assertEqual(plan.cameras[0].exclude, ["wall-c", "wall-d"])
        self.assertEqual(plan.cameras[1].exclude, ["wall-a", "wall-b"])
        self.assertFalse(self._has_duplicate_sets(plan))
        for shot in plan.cameras:
            self.assertEqual(shot.camera, "inside_corner")
            self.assertLessEqual(len(shot.walls), 2)
            self.assertNotIn(shot.frame.left, shot.exclude)
            if shot.frame.right:
                self.assertNotIn(shot.frame.right, shot.exclude)

    def test_facing_walls_never_share_a_camera(self):
        for spec in (u_spec(), galley_spec(), four_wall_spec()):
            plan = plan_views(spec)
            for shot in plan.cameras:
                if len(shot.walls) < 2:
                    continue
                a, b = shot.walls
                self.assertFalse(
                    spec.is_facing(a, b),
                    f"{shot.shot_id} paired facing walls {a} and {b}",
                )

    def test_every_shot_at_most_two_walls(self):
        for spec in (
            straight_spec(),
            l_spec(),
            u_spec(),
            galley_spec(),
            four_wall_spec(),
        ):
            plan = plan_views(spec)
            self.assertEqual(len(plan.elevations), len(spec.wall_ids()))
            for shot in plan.cameras:
                self.assertLessEqual(len(shot.walls), 2)
                self.assertGreaterEqual(len(shot.walls), 1)

    def test_bays_listed_only_for_walls_in_the_shot(self):
        plan = plan_views(u_spec())
        shot = plan.cameras[0]
        self.assertEqual(set(shot.bays_by_wall), set(shot.walls))
        self.assertEqual(shot.bays_by_wall["wall-a"], ["wall-a-bay-1"])
        self.assertNotIn("wall-c", shot.bays_by_wall)

    @staticmethod
    def _covers_all(plan, wall_ids):
        seen = set()
        for job in plan.cameras:
            seen.update(job.walls)
        return seen == set(wall_ids)

    @staticmethod
    def _has_duplicate_sets(plan):
        sets = _wall_sets(plan)
        return len(sets) != len(set(sets))


if __name__ == "__main__":
    unittest.main()
