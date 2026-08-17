"""The exported fixtures must match the factories.

If this fails, run:  python -m tests.export_fixtures
The TypeScript solver tests read these files, so a stale fixture means the
two languages are describing different specs (see export_fixtures docstring).
"""
from __future__ import annotations

import pytest

from tests.export_fixtures import FIXTURES, OUT, render


@pytest.mark.parametrize("name", sorted(FIXTURES))
def test_fixture_is_current(name: str):
    path = OUT / f"{name}.json"
    assert path.exists(), f"missing fixture {name}.json - run python -m tests.export_fixtures"
    assert path.read_text(encoding="utf-8") == render(name), (
        f"{name}.json is stale - run python -m tests.export_fixtures"
    )
