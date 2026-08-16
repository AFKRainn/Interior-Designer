"""Build valid FurnitureSpec graphs for tests."""
from app.editor.sample import l_kitchen_spec
from app.models.furniture_spec import (
    BaySpec,
    DesignWall,
    FurnitureSpec,
    LayoutSpec,
    LayoutType,
    LayoutWall,
)


def _design_wall(wall_id: str, length: float) -> DesignWall:
    return DesignWall(
        id=wall_id,
        height=220,
        depth=60,
        bays=[
            BaySpec(
                id=f"{wall_id}-bay-1",
                label=f"{wall_id} bay 1",
                width=length,
            )
        ],
    )


def spec_from_walls(
    layout_type: LayoutType,
    walls: list[LayoutWall],
) -> FurnitureSpec:
    return FurnitureSpec(
        name=layout_type.value,
        layout=LayoutSpec(type=layout_type, walls=walls),
        walls=[_design_wall(wall.id, wall.length) for wall in walls],
    )


def straight_spec() -> FurnitureSpec:
    return spec_from_walls(
        LayoutType.STRAIGHT,
        [
            LayoutWall(
                id="wall-a",
                label="Wall A",
                length=300,
                sequence=0,
            )
        ],
    )


def l_spec() -> FurnitureSpec:
    return spec_from_walls(
        LayoutType.L,
        [
            LayoutWall(
                id="wall-a",
                label="Wall A — Sink run",
                length=300,
                adjacent_to=["wall-b"],
                sequence=0,
            ),
            LayoutWall(
                id="wall-b",
                label="Wall B — Fridge run",
                length=180,
                adjacent_to=["wall-a"],
                sequence=1,
            ),
        ],
    )


def u_spec() -> FurnitureSpec:
    return spec_from_walls(
        LayoutType.U,
        [
            LayoutWall(
                id="wall-a",
                label="Wall A — left",
                length=180,
                adjacent_to=["wall-b"],
                faces=["wall-c"],
                sequence=0,
            ),
            LayoutWall(
                id="wall-b",
                label="Wall B — back",
                length=300,
                adjacent_to=["wall-a", "wall-c"],
                sequence=1,
            ),
            LayoutWall(
                id="wall-c",
                label="Wall C — right",
                length=180,
                adjacent_to=["wall-b"],
                faces=["wall-a"],
                sequence=2,
            ),
        ],
    )


def galley_spec() -> FurnitureSpec:
    return spec_from_walls(
        LayoutType.GALLEY,
        [
            LayoutWall(
                id="wall-a",
                label="Wall A",
                length=300,
                faces=["wall-b"],
                sequence=0,
            ),
            LayoutWall(
                id="wall-b",
                label="Wall B",
                length=300,
                faces=["wall-a"],
                sequence=1,
            ),
        ],
    )


def four_wall_spec() -> FurnitureSpec:
    return spec_from_walls(
        LayoutType.CUSTOM,
        [
            LayoutWall(
                id="wall-a",
                label="Wall A",
                length=400,
                adjacent_to=["wall-b", "wall-d"],
                faces=["wall-c"],
                sequence=0,
            ),
            LayoutWall(
                id="wall-b",
                label="Wall B",
                length=300,
                adjacent_to=["wall-a", "wall-c"],
                faces=["wall-d"],
                sequence=1,
            ),
            LayoutWall(
                id="wall-c",
                label="Wall C",
                length=400,
                adjacent_to=["wall-b", "wall-d"],
                faces=["wall-a"],
                sequence=2,
            ),
            LayoutWall(
                id="wall-d",
                label="Wall D",
                length=300,
                adjacent_to=["wall-c", "wall-a"],
                faces=["wall-b"],
                sequence=3,
            ),
        ],
    )
