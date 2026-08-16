"""Sample Furniture Spec for the editor demo (same L-kitchen as golden tests)."""
from app.models.furniture_spec import (
    BaySpec,
    CorniceSpec,
    DesignWall,
    FurnitureSpec,
    HardwareSpec,
    LayoutSpec,
    LayoutType,
    LayoutWall,
    MaterialsSpec,
    ModuleSpec,
    PlinthSpec,
    SideColumnsSpec,
)


def l_kitchen_spec() -> FurnitureSpec:
    return FurnitureSpec(
        project_id="golden-l-kitchen",
        version=1,
        units="cm",
        name="L kitchen",
        layout=LayoutSpec(
            type=LayoutType.L,
            walls=[
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
        ),
        walls=[
            DesignWall(
                id="wall-a",
                height=220,
                depth=60,
                cornice=CorniceSpec(type="straight", height=8),
                plinth=PlinthSpec(type="recessed", height=12),
                side_columns=SideColumnsSpec(left_cm=6, right_cm=6, detail="plain"),
                bays=[
                    BaySpec(
                        id="bay-1",
                        label="Sink",
                        width=80,
                        modules=[
                            ModuleSpec(type="drawer", height=20, count=1, handle="bar"),
                            ModuleSpec(type="door", height=180, count=1, handle="bar"),
                        ],
                    ),
                    BaySpec(
                        id="bay-2",
                        label="Dishwasher",
                        width=60,
                        modules=[
                            ModuleSpec(
                                type="appliance", height=200, count=1, handle="bar"
                            ),
                        ],
                    ),
                    BaySpec(
                        id="bay-3",
                        label="Drawers",
                        width=80,
                        modules=[
                            ModuleSpec(type="drawer", height=20, count=4, handle="bar"),
                            ModuleSpec(type="door", height=120, count=1, handle="bar"),
                        ],
                    ),
                    BaySpec(
                        id="bay-4",
                        label="Open shelves",
                        width=80,
                        modules=[
                            ModuleSpec(type="open_shelf", height=50, count=4, handle=""),
                        ],
                    ),
                ],
            ),
            DesignWall(
                id="wall-b",
                height=220,
                depth=60,
                cornice=CorniceSpec(type="straight", height=8),
                plinth=PlinthSpec(type="recessed", height=12),
                side_columns=SideColumnsSpec(left_cm=6, right_cm=6, detail="plain"),
                bays=[
                    BaySpec(
                        id="bay-5",
                        label="Fridge",
                        width=90,
                        modules=[
                            ModuleSpec(type="appliance", height=200, count=1, handle="bar"),
                        ],
                    ),
                    BaySpec(
                        id="bay-6",
                        label="Pantry",
                        width=90,
                        modules=[
                            ModuleSpec(type="door", height=200, count=1, handle="bar"),
                        ],
                    ),
                ],
            ),
        ],
        materials=MaterialsSpec(
            carcass="plywood", doors="painted MDF", finish="matte white"
        ),
        hardware=HardwareSpec(
            style="bar", placement="right of doors, centered on drawers"
        ),
        brief="L-shaped kitchen. Wall A sink run 300 cm. Wall B fridge run 180 cm.",
    )
