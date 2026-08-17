"""Camera planning is code, not a model (plan 7 / 11)."""
from __future__ import annotations

import pytest

from app.planner.views import plan_views
from tests.v2_factory import four_walls, galley, l_kitchen, straight_wall, u_kitchen

CASES = {
    "straight": (straight_wall, 1, [["wall-a"]]),
    "L": (l_kitchen, 2, [["wall-a", "wall-b"]]),
    "U": (u_kitchen, 3, [["wall-a", "wall-b"], ["wall-b", "wall-c"]]),
    "galley": (galley, 2, [["wall-a"], ["wall-b"]]),
    "four walls": (four_walls, 4, [["wall-a", "wall-b"], ["wall-c", "wall-d"]]),
}


@pytest.mark.parametrize("name", list(CASES))
def test_worked_examples(name: str):
    factory, elevations, shots = CASES[name]
    plan = plan_views(factory())
    assert len(plan.elevations) == elevations
    assert [job.walls for job in plan.cameras] == shots


def test_one_elevation_per_wall_never_asked_of_a_model():
    for factory, elevations, _ in CASES.values():
        spec = factory()
        plan = plan_views(spec)
        assert [job.wall_id for job in plan.elevations] == spec.wall_ids()
        assert len(plan.elevations) == elevations


def test_a_shot_never_holds_more_than_two_walls():
    for factory, _, _ in CASES.values():
        for job in plan_views(factory()).cameras:
            assert 1 <= len(job.walls) <= 2


def test_facing_walls_never_share_a_shot():
    """A galley photographed as one shot would be a lie about the room."""
    for factory, _, _ in CASES.values():
        spec = factory()
        for job in plan_views(spec).cameras:
            if len(job.walls) == 2:
                assert not spec.is_facing(*job.walls)


def test_every_wall_appears_somewhere():
    for factory, _, _ in CASES.values():
        spec = factory()
        seen = {wall for job in plan_views(spec).cameras for wall in job.walls}
        assert seen == set(spec.wall_ids())


def test_no_two_shots_have_the_same_wall_set():
    for factory, _, _ in CASES.values():
        shots = [frozenset(job.walls) for job in plan_views(factory()).cameras]
        assert len(shots) == len(set(shots))


def test_excludes_name_every_wall_not_in_the_shot():
    spec = u_kitchen()
    for job in plan_views(spec).cameras:
        assert set(job.walls) | set(job.exclude) == set(spec.wall_ids())
        assert not set(job.walls) & set(job.exclude)


def test_references_are_the_shot_walls_plus_its_own_plan():
    for job in plan_views(u_kitchen()).cameras:
        expected = [f"elev-{wall}.png" for wall in job.walls] + [f"plan-{job.shot_id}.png"]
        assert job.references == expected


def test_camera_type_follows_the_wall_count():
    for factory, _, _ in CASES.values():
        for job in plan_views(factory()).cameras:
            assert job.camera == ("inside_corner" if len(job.walls) == 2 else "frontal")
