"""
Design Specification Document (DSD) — Pydantic Model

The DSD is the single source of truth for any design.
The Council agrees on it, images are generated FROM it,
and changes UPDATE it — enabling targeted modifications.
"""
from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class DesignType(str, Enum):
    FURNITURE = "furniture"
    ROOM = "room"
    BUILDING = "building"


class ChangeType(str, Enum):
    COSMETIC = "cosmetic"          # Color, texture, finish
    STRUCTURAL = "structural"      # Layout, dimensions, proportions
    ADDITIVE = "additive"          # New element added
    SUBTRACTIVE = "subtractive"    # Element removed


class ViewType(str, Enum):
    FLOOR_PLAN = "floor_plan"
    FRONT_ELEVATION = "front_elevation"
    SIDE_ELEVATION = "side_elevation"
    REAR_ELEVATION = "rear_elevation"
    PERSPECTIVE_3D_FRONT = "perspective_3d_front"
    PERSPECTIVE_3D_ANGLE = "perspective_3d_angle"
    REALISTIC_RENDER = "realistic_render"


class ViewSpec(BaseModel):
    """
    A specific view to generate, decided by the council.

    Unlike ViewType (which is just an enum), ViewSpec carries a label,
    description, and a council-authored generation_prompt — the precise
    instructions for the image generator written by the council based on
    their forensic analysis of the design.

    generation_prompt is the primary driver of image generation.
    If empty, the generator falls back to the fixed template.
    """
    type: str  # one of ViewType values, e.g. "front_elevation"
    label: str  # human-readable label, e.g. "Wall A — Sink Side"
    description: str = ""  # brief context description
    generation_prompt: str = ""  # council-authored content prompt for this view
    id: str = Field(default_factory=lambda: str(uuid4())[:8])


# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------

class Dimensions(BaseModel):
    width: Optional[str] = None
    height: Optional[str] = None
    depth: Optional[str] = None
    notes: Optional[str] = None


class StyleSpec(BaseModel):
    aesthetic: str = ""
    era: str = ""
    influences: list[str] = Field(default_factory=list)


class MaterialSpec(BaseModel):
    name: str
    usage: str = ""
    finish: str = ""


class ColorSpec(BaseModel):
    primary: Optional[str] = None
    secondary: Optional[str] = None
    accent: Optional[str] = None
    notes: Optional[str] = None


class StructuralElement(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4())[:8])
    name: str
    description: str = ""
    dimensions: Optional[Dimensions] = None
    material: Optional[str] = None
    position: str = ""
    count: int = 1


class ContextSpec(BaseModel):
    placement: str = ""
    surroundings: str = ""
    scale_reference: str = ""


class ChangeRecord(BaseModel):
    version: int
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    change_type: ChangeType
    description: str
    sections_affected: list[str] = Field(default_factory=list)
    images_regenerated: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Main DSD Model
# ---------------------------------------------------------------------------

class DesignSpecificationDocument(BaseModel):
    """
    The core data model — single source of truth for a design.

    All generation and review references this document.
    Changes create new versions while preserving history.
    """

    project_id: str = Field(default_factory=lambda: str(uuid4()))
    version: int = 1
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())

    # What is being designed
    type: DesignType = DesignType.FURNITURE
    name: str = ""
    description: str = ""

    # Physical specifications
    dimensions: Dimensions = Field(default_factory=Dimensions)
    style: StyleSpec = Field(default_factory=StyleSpec)
    materials: list[MaterialSpec] = Field(default_factory=list)
    colors: ColorSpec = Field(default_factory=ColorSpec)

    # Structure
    structural_elements: list[StructuralElement] = Field(default_factory=list)
    spatial_layout: str = ""

    # Context
    context: ContextSpec = Field(default_factory=ContextSpec)

    # Generation plan
    views_to_generate: list[ViewSpec] = Field(default_factory=list)
    generation_notes: str = ""

    @field_validator("views_to_generate", mode="before")
    @classmethod
    def _coerce_views(cls, v):
        """Backward compat: convert plain strings to ViewSpec dicts."""
        if not isinstance(v, list):
            return v
        result = []
        for item in v:
            if isinstance(item, str):
                result.append({
                    "type": item,
                    "label": item.replace("_", " ").title(),
                })
            else:
                result.append(item)
        return result

    # History
    change_history: list[ChangeRecord] = Field(default_factory=list)

    # Design Intent Preservation
    baseline_locked: bool = False
    locked_fields: list[str] = Field(
        default_factory=list,
        description=(
            "DSD field paths that are frozen after baseline lock. "
            "Modifications should NOT alter these unless the user "
            "explicitly requests it. Examples: 'dimensions', 'spatial_layout', "
            "'structural_elements', 'style.aesthetic'."
        ),
    )

    def create_new_version(
        self,
        change_type: ChangeType,
        description: str,
        sections: list[str],
    ) -> "DesignSpecificationDocument":
        """
        Create a new version of this DSD with a change recorded.

        Returns a deep copy with incremented version and the change
        appended to change_history.
        """
        new_dsd = self.model_copy(deep=True)
        new_dsd.version += 1
        new_dsd.updated_at = datetime.now().isoformat()
        new_dsd.change_history.append(
            ChangeRecord(
                version=new_dsd.version,
                change_type=change_type,
                description=description,
                sections_affected=sections,
            )
        )
        return new_dsd

    def lock_baseline(self):
        """
        Lock the current DSD as the baseline.
        Called after the first successful render (drawings approved).
        Freezes core structural/layout fields so modifications preserve intent.
        """
        self.baseline_locked = True
        self.locked_fields = [
            "type",
            "dimensions",
            "spatial_layout",
            "structural_elements",
            "style.aesthetic",
        ]
        self.updated_at = datetime.now().isoformat()

    def get_locked_summary(self) -> str:
        """Return a summary of locked fields for inclusion in prompts."""
        if not self.baseline_locked or not self.locked_fields:
            return ""
        return (
            "BASELINE-LOCKED FIELDS (do NOT modify unless user explicitly "
            "says to change these):\n"
            + "\n".join(f"  - {f}" for f in self.locked_fields)
        )

    def get_applicable_views(self) -> list[ViewSpec]:
        """
        Fallback: generate default ViewSpecs based on design type.
        Only used if the council didn't specify views.
        """
        from config import VIEWS_CONFIG

        specs = []
        design_type = self.type.value
        for view_key, view_info in VIEWS_CONFIG.items():
            if design_type in view_info["applicable_to"]:
                specs.append(ViewSpec(
                    type=view_key,
                    label=view_info["name"],
                    description=view_info["description"],
                ))
        return specs

    def to_prompt_description(self) -> str:
        """
        Convert the DSD into a detailed text description suitable
        for use in image generation prompts.
        """
        parts = []
        parts.append(f"Design: {self.name}")
        parts.append(f"Type: {self.type.value}")
        parts.append(f"Description: {self.description}")

        if self.dimensions.width or self.dimensions.height or self.dimensions.depth:
            dims = []
            if self.dimensions.width:
                dims.append(f"Width: {self.dimensions.width}")
            if self.dimensions.height:
                dims.append(f"Height: {self.dimensions.height}")
            if self.dimensions.depth:
                dims.append(f"Depth: {self.dimensions.depth}")
            parts.append(f"Dimensions: {', '.join(dims)}")
            if self.dimensions.notes:
                parts.append(f"Dimension notes: {self.dimensions.notes}")

        if self.style.aesthetic:
            parts.append(f"Style: {self.style.aesthetic}")
        if self.style.era:
            parts.append(f"Era: {self.style.era}")
        if self.style.influences:
            parts.append(f"Influences: {', '.join(self.style.influences)}")

        if self.materials:
            mat_strs = [
                f"{m.name} ({m.usage}, {m.finish})" if m.usage else m.name
                for m in self.materials
            ]
            parts.append(f"Materials: {', '.join(mat_strs)}")

        if self.colors.primary:
            color_parts = [f"Primary: {self.colors.primary}"]
            if self.colors.secondary:
                color_parts.append(f"Secondary: {self.colors.secondary}")
            if self.colors.accent:
                color_parts.append(f"Accent: {self.colors.accent}")
            parts.append(f"Colors: {', '.join(color_parts)}")

        if self.structural_elements:
            parts.append("Structural Elements:")
            for elem in self.structural_elements:
                elem_str = f"  - {elem.name}: {elem.description}"
                if elem.material:
                    elem_str += f" (material: {elem.material})"
                if elem.count > 1:
                    elem_str += f" x{elem.count}"
                parts.append(elem_str)

        if self.spatial_layout:
            parts.append(f"Spatial Layout: {self.spatial_layout}")

        if self.context.placement:
            parts.append(f"Placement: {self.context.placement}")
        if self.context.surroundings:
            parts.append(f"Surroundings: {self.context.surroundings}")

        if self.generation_notes:
            parts.append(f"Special Notes: {self.generation_notes}")

        return "\n".join(parts)
