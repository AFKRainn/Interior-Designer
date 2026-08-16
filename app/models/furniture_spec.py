"""
Furniture Spec — source of truth for the new pipeline.

Plan view and every elevation are renderings of this document.
The view planner reads layout.walls (ids, adjacency, facing, sequence).
"""
from enum import Enum
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


BAY_SUM_TOLERANCE_CM = 1.0


class LayoutType(str, Enum):
    STRAIGHT = "straight"
    L = "L"
    U = "U"
    GALLEY = "galley"
    CUSTOM = "custom"


class CorniceSpec(BaseModel):
    type: str = "straight"
    height: float = 0.0


class PlinthSpec(BaseModel):
    type: str = "recessed"
    height: float = 0.0


class SideColumnsSpec(BaseModel):
    left_cm: float = 0.0
    right_cm: float = 0.0
    detail: str = "plain"


class ModuleSpec(BaseModel):
    type: str
    height: float = 0.0
    count: int = 1
    handle: str = ""


class BaySpec(BaseModel):
    id: str
    label: str = ""
    width: float
    modules: list[ModuleSpec] = Field(default_factory=list)


class DesignWall(BaseModel):
    """The designed face of one wall: bays, trim, height, depth."""

    id: str
    height: float = 0.0
    depth: float = 0.0
    cornice: CorniceSpec = Field(default_factory=CorniceSpec)
    plinth: PlinthSpec = Field(default_factory=PlinthSpec)
    side_columns: SideColumnsSpec = Field(default_factory=SideColumnsSpec)
    bays: list[BaySpec] = Field(default_factory=list)

    def bay_ids(self) -> list[str]:
        return [bay.id for bay in self.bays]

    def bay_width_sum(self) -> float:
        return sum(bay.width for bay in self.bays)


class LayoutWall(BaseModel):
    """Topology of one wall in the room: length, neighbours, order."""

    id: str
    label: str = ""
    length: float
    adjacent_to: list[str] = Field(default_factory=list)
    faces: list[str] = Field(default_factory=list)
    sequence: int = 0


class LayoutSpec(BaseModel):
    type: LayoutType = LayoutType.CUSTOM
    walls: list[LayoutWall] = Field(default_factory=list)


class MaterialsSpec(BaseModel):
    carcass: str = ""
    doors: str = ""
    finish: str = ""


class HardwareSpec(BaseModel):
    style: str = ""
    placement: str = ""


class FurnitureSpec(BaseModel):
    project_id: str = Field(default_factory=lambda: str(uuid4()))
    version: int = 1
    units: str = "cm"
    name: str = ""
    layout: LayoutSpec
    walls: list[DesignWall] = Field(default_factory=list)
    materials: MaterialsSpec = Field(default_factory=MaterialsSpec)
    hardware: HardwareSpec = Field(default_factory=HardwareSpec)
    brief: str = ""
    render_notes: str = ""

    @model_validator(mode="after")
    def validate_spec(self) -> "FurnitureSpec":
        layout_ids = [wall.id for wall in self.layout.walls]
        design_ids = [wall.id for wall in self.walls]

        if len(layout_ids) != len(set(layout_ids)):
            raise ValueError("layout.walls ids must be unique")
        if len(design_ids) != len(set(design_ids)):
            raise ValueError("walls ids must be unique")

        if set(layout_ids) != set(design_ids):
            raise ValueError(
                "layout.walls ids and walls ids must match. "
                f"layout={sorted(layout_ids)} walls={sorted(design_ids)}"
            )

        id_set = set(layout_ids)

        for wall in self.layout.walls:
            for other in wall.adjacent_to:
                if other == wall.id:
                    raise ValueError(f"{wall.id} cannot be adjacent to itself")
                if other not in id_set:
                    raise ValueError(
                        f"{wall.id}.adjacent_to references unknown wall {other}"
                    )
            for other in wall.faces:
                if other == wall.id:
                    raise ValueError(f"{wall.id} cannot face itself")
                if other not in id_set:
                    raise ValueError(
                        f"{wall.id}.faces references unknown wall {other}"
                    )
                if other in wall.adjacent_to:
                    raise ValueError(
                        f"{wall.id} cannot both face and be adjacent to {other}"
                    )

        for wall in self.layout.walls:
            for other_id in wall.adjacent_to:
                other = self.layout_wall(other_id)
                if wall.id not in other.adjacent_to:
                    raise ValueError(
                        f"adjacent_to must be symmetric: {wall.id} lists "
                        f"{other_id} but {other_id} does not list {wall.id}"
                    )
            for other_id in wall.faces:
                other = self.layout_wall(other_id)
                if wall.id not in other.faces:
                    raise ValueError(
                        f"faces must be symmetric: {wall.id} lists {other_id} "
                        f"but {other_id} does not list {wall.id}"
                    )

        for design in self.walls:
            if not design.bays:
                continue
            layout_wall = self.layout_wall(design.id)
            delta = abs(design.bay_width_sum() - layout_wall.length)
            if delta > BAY_SUM_TOLERANCE_CM:
                raise ValueError(
                    f"{design.id}: bay widths sum to {design.bay_width_sum()} "
                    f"but wall length is {layout_wall.length} "
                    f"(tolerance {BAY_SUM_TOLERANCE_CM} cm)"
                )

            bay_ids = design.bay_ids()
            if len(bay_ids) != len(set(bay_ids)):
                raise ValueError(f"{design.id}: bay ids must be unique")

        return self

    def layout_wall(self, wall_id: str) -> LayoutWall:
        for wall in self.layout.walls:
            if wall.id == wall_id:
                return wall
        raise KeyError(wall_id)

    def design_wall(self, wall_id: str) -> DesignWall:
        for wall in self.walls:
            if wall.id == wall_id:
                return wall
        raise KeyError(wall_id)

    def ordered_layout_walls(self) -> list[LayoutWall]:
        return sorted(self.layout.walls, key=lambda wall: (wall.sequence, wall.id))

    def wall_ids(self) -> list[str]:
        return [wall.id for wall in self.ordered_layout_walls()]

    def is_adjacent(self, a: str, b: str) -> bool:
        return b in self.layout_wall(a).adjacent_to

    def is_facing(self, a: str, b: str) -> bool:
        return b in self.layout_wall(a).faces

    def can_share_camera(self, a: str, b: str) -> bool:
        if a == b:
            return False
        if self.is_facing(a, b):
            return False
        return self.is_adjacent(a, b)
