"""The sizing rule is pinned to shared vectors.

`distribute` exists twice on purpose: Python validates it server-side, and
the TypeScript solver re-runs it in the browser during a drag. Build 1 had
exactly one duplicated layout calculation and it silently drifted (plan 3.5),
so this file is the contract that keeps the two honest. The Phase 2 solver
loads the same JSON.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.models.spec import Opening, distribute

GOLDEN = Path(__file__).parent / "golden" / "distribute.json"
CASES = json.loads(GOLDEN.read_text(encoding="utf-8"))["cases"]


def _opening(index: int, child: dict) -> Opening:
    return Opening(
        id=f"n-{index}",
        size_cm=child.get("size"),
        flex=child.get("flex") if child.get("size") is None else None,
        front={"type": "open"},
    )


@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
def test_distribute_matches_the_golden_vector(case: dict):
    children = [_opening(i, child) for i, child in enumerate(case["children"])]
    assert distribute(children, case["extent"]) == pytest.approx(case["expect"])


def test_every_case_conserves_the_extent():
    """A property the TypeScript side must hold too: sizes sum to the extent
    unless the fixed children already oversubscribed it."""
    for case in CASES:
        if not case["children"]:
            continue
        children = [_opening(i, c) for i, c in enumerate(case["children"])]
        sizes = distribute(children, case["extent"])
        fixed_total = sum(c.size_cm for c in children if c.size_cm is not None)
        if fixed_total <= case["extent"]:
            assert sum(sizes) == pytest.approx(case["extent"], abs=0.001)
        else:
            assert sum(sizes) == pytest.approx(fixed_total, abs=0.001)
