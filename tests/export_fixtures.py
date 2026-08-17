"""Write the shared spec fixtures the TypeScript solver tests consume.

The solver's spec types are hand-written TypeScript mirroring the Pydantic
model. These fixtures are the drift guard: TS loads specs that PYTHON
produced, so if the model's shape changes and the fixtures are not
regenerated, test_fixtures_are_current fails and the TS tests break loudly
instead of silently drawing the wrong thing.

Run:  python -m tests.export_fixtures
"""
from __future__ import annotations

import json
from pathlib import Path

from tests import v2_factory

OUT = Path(__file__).parent / "golden" / "specs"

FIXTURES = {
    "straight": v2_factory.straight_wall,
    "l_kitchen": v2_factory.l_kitchen,
    "u_kitchen": v2_factory.u_kitchen,
    "galley": v2_factory.galley,
    "four_walls": v2_factory.four_walls,
    "nightstand": v2_factory.nightstand,
    "long_run": v2_factory.long_run,
    "two_doors": v2_factory.two_doors,
}


def render(name: str) -> str:
    spec = FIXTURES[name]()
    data = spec.model_dump(mode="json")
    # project_id is a fresh uuid per call; pin it so the files are stable.
    data["project_id"] = f"fixture-{name}"
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name in FIXTURES:
        (OUT / f"{name}.json").write_text(render(name), encoding="utf-8")
        print(f"wrote {name}.json")


if __name__ == "__main__":
    main()
