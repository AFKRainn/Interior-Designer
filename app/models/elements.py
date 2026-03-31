"""
Built-in Element Library

Pre-defined design elements that users can select while prompting.
These inject specific material/construction details into the design
brief and council prompts without requiring the user to describe
everything from scratch.

Defaults to "plain" for everything — no user action required.
"""
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Element Categories
# ---------------------------------------------------------------------------

class ElementCategory(str, Enum):
    SIDE_PANEL = "side_panel"
    EDGE_BAND = "edge_band"
    HANDLE = "handle"
    SHELF_TYPE = "shelf_type"
    BACK_PANEL = "back_panel"
    LEG_STYLE = "leg_style"
    SURFACE_FINISH = "surface_finish"
    GRAIN_PATTERN = "grain_pattern"
    DOOR_TYPE = "door_type"
    DRAWER_FRONT = "drawer_front"


# ---------------------------------------------------------------------------
# Individual Element Definition
# ---------------------------------------------------------------------------

class ElementOption(BaseModel):
    """A single selectable element option."""
    id: str
    name: str
    category: ElementCategory
    description: str
    technical_spec: str = ""  # e.g., "18mm MDF, plain flat"
    is_default: bool = False
    keywords: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# User's Element Selections
# ---------------------------------------------------------------------------

class ElementSelections(BaseModel):
    """Tracks which elements the user has selected."""
    selections: dict[str, str] = Field(
        default_factory=dict,
        description="Map of category -> selected option ID",
    )

    def get_selection(self, category: str) -> str | None:
        return self.selections.get(category)

    def set_selection(self, category: str, option_id: str):
        self.selections[category] = option_id

    def to_description(self) -> str:
        """Convert selections to a human-readable description for prompts."""
        if not self.selections:
            return "All defaults (plain/standard)"

        lines = []
        for cat_key, opt_id in self.selections.items():
            option = get_option(cat_key, opt_id)
            if option and not option.is_default:
                lines.append(f"- {option.category.value.replace('_', ' ').title()}: "
                             f"{option.name} ({option.technical_spec})")

        if not lines:
            return "All defaults (plain/standard)"

        return "Selected elements:\n" + "\n".join(lines)

    def to_technical_spec(self) -> str:
        """Produce a detailed technical specification string for the council."""
        if not self.selections:
            return ""

        specs = []
        for cat_key, opt_id in self.selections.items():
            option = get_option(cat_key, opt_id)
            if option and not option.is_default and option.technical_spec:
                specs.append(f"{option.category.value.replace('_', ' ').title()}: "
                             f"{option.technical_spec}")
        return "; ".join(specs)


# ============================================================================
# ELEMENT LIBRARY — All available options
# ============================================================================

ELEMENT_LIBRARY: dict[str, list[ElementOption]] = {

    # --- SIDE PANELS ---
    ElementCategory.SIDE_PANEL.value: [
        ElementOption(
            id="plain_18mm",
            name="Plain MDF 18mm",
            category=ElementCategory.SIDE_PANEL,
            description="Standard 18mm MDF side panel, smooth flat surface",
            technical_spec="18mm MDF, plain flat, smooth finish",
            is_default=True,
            keywords=["plain", "flat", "standard", "mdf"],
        ),
        ElementOption(
            id="plain_16mm",
            name="Plain MDF 16mm",
            category=ElementCategory.SIDE_PANEL,
            description="Standard 16mm (1.6cm) MDF side panel, smooth surface",
            technical_spec="16mm MDF, plain flat, smooth finish",
            keywords=["plain", "flat", "16mm", "mdf", "standard"],
        ),
        ElementOption(
            id="decorative_40mm",
            name="Decorative Panel 40mm",
            category=ElementCategory.SIDE_PANEL,
            description="Thick 40mm (4cm) decorative side panel with routed geometric shapes and grooves",
            technical_spec="40mm MDF/solid wood, CNC-routed decorative geometric pattern, raised panels",
            keywords=["decorative", "thick", "40mm", "4cm", "shapes", "grooves", "routed"],
        ),
        ElementOption(
            id="fluted_25mm",
            name="Fluted Panel 25mm",
            category=ElementCategory.SIDE_PANEL,
            description="25mm panel with vertical fluted/ribbed grooves",
            technical_spec="25mm MDF, vertical fluted grooves (10mm spacing), paint-grade",
            keywords=["fluted", "ribbed", "grooves", "vertical"],
        ),
        ElementOption(
            id="shaker_18mm",
            name="Shaker Style 18mm",
            category=ElementCategory.SIDE_PANEL,
            description="18mm panel with classic shaker recessed panel detail",
            technical_spec="18mm MDF, shaker-style recessed center panel, framed edges",
            keywords=["shaker", "recessed", "classic", "traditional"],
        ),
    ],

    # --- EDGE BANDING ---
    ElementCategory.EDGE_BAND.value: [
        ElementOption(
            id="matching_pvc",
            name="Matching PVC Edge",
            category=ElementCategory.EDGE_BAND,
            description="PVC edge band matching the panel color/finish",
            technical_spec="2mm PVC edge band, color-matched",
            is_default=True,
            keywords=["pvc", "matching", "standard"],
        ),
        ElementOption(
            id="solid_wood",
            name="Solid Wood Lipping",
            category=ElementCategory.EDGE_BAND,
            description="Solid hardwood edge lipping for a premium look",
            technical_spec="5mm solid hardwood lipping, sanded and finished",
            keywords=["wood", "solid", "lipping", "premium"],
        ),
        ElementOption(
            id="metal_strip",
            name="Metal Edge Strip",
            category=ElementCategory.EDGE_BAND,
            description="Thin metal edge strip for modern industrial look",
            technical_spec="1mm brushed aluminum or black steel edge strip",
            keywords=["metal", "aluminum", "steel", "industrial"],
        ),
    ],

    # --- HANDLES ---
    ElementCategory.HANDLE.value: [
        ElementOption(
            id="none",
            name="No Handles (Push-to-Open)",
            category=ElementCategory.HANDLE,
            description="Handleless design — doors and drawers open by pushing",
            technical_spec="Push-to-open (tip-on) mechanism, no visible hardware",
            is_default=True,
            keywords=["handleless", "push", "minimal", "clean"],
        ),
        ElementOption(
            id="bar_pull",
            name="Bar Pull Handle",
            category=ElementCategory.HANDLE,
            description="Horizontal bar handle, modern minimalist style",
            technical_spec="160mm/320mm center bar pull, brushed stainless or matte black",
            keywords=["bar", "pull", "modern", "linear"],
        ),
        ElementOption(
            id="recessed_channel",
            name="Recessed Channel (J-Pull)",
            category=ElementCategory.HANDLE,
            description="Integrated channel cut into the top or bottom edge of the door",
            technical_spec="Routed J-pull channel, typically 20mm deep, integrated into panel edge",
            keywords=["recessed", "channel", "j-pull", "integrated", "groove"],
        ),
        ElementOption(
            id="knob_round",
            name="Round Knob",
            category=ElementCategory.HANDLE,
            description="Small round knob handle, traditional or modern depending on finish",
            technical_spec="30-35mm diameter round knob, various finishes available",
            keywords=["knob", "round", "classic"],
        ),
        ElementOption(
            id="leather_tab",
            name="Leather Tab Pull",
            category=ElementCategory.HANDLE,
            description="Soft leather loop or tab handle, Scandinavian style",
            technical_spec="Leather tab pull, brass/copper rivets, natural or dyed leather",
            keywords=["leather", "tab", "scandinavian", "soft"],
        ),
        ElementOption(
            id="flush_pull",
            name="Flush / Inset Pull",
            category=ElementCategory.HANDLE,
            description="Flush-mounted recessed pull — sits flat with the door surface",
            technical_spec="Rectangular or oval flush-mount pull, recessed into door face",
            keywords=["flush", "inset", "recessed", "flat"],
        ),
    ],

    # --- SHELF TYPE ---
    ElementCategory.SHELF_TYPE.value: [
        ElementOption(
            id="fixed_18mm",
            name="Fixed Shelf 18mm",
            category=ElementCategory.SHELF_TYPE,
            description="Standard fixed 18mm MDF/melamine shelf",
            technical_spec="18mm MDF/melamine shelf, fixed with shelf pins or screws",
            is_default=True,
            keywords=["fixed", "standard", "18mm"],
        ),
        ElementOption(
            id="adjustable_18mm",
            name="Adjustable Shelf 18mm",
            category=ElementCategory.SHELF_TYPE,
            description="Adjustable 18mm shelf on 32mm system shelf pins",
            technical_spec="18mm shelf, adjustable via 5mm shelf pins in 32mm system rows",
            keywords=["adjustable", "movable", "pins"],
        ),
        ElementOption(
            id="glass_8mm",
            name="Glass Shelf 8mm",
            category=ElementCategory.SHELF_TYPE,
            description="Tempered glass shelf, 8mm thick, for display units",
            technical_spec="8mm tempered safety glass shelf, polished edges, on glass shelf supports",
            keywords=["glass", "tempered", "display", "transparent"],
        ),
        ElementOption(
            id="floating_thick",
            name="Thick Floating Shelf (25mm+)",
            category=ElementCategory.SHELF_TYPE,
            description="Extra-thick shelf for a substantial, floating look",
            technical_spec="25-36mm MDF or plywood shelf, concealed mounting for floating appearance",
            keywords=["thick", "floating", "substantial", "bold"],
        ),
    ],

    # --- BACK PANEL ---
    ElementCategory.BACK_PANEL.value: [
        ElementOption(
            id="recessed_3mm",
            name="Recessed 3mm HDF",
            category=ElementCategory.BACK_PANEL,
            description="Standard 3mm HDF back panel recessed into a groove",
            technical_spec="3mm HDF, recessed into 4mm groove, white or matching color",
            is_default=True,
            keywords=["thin", "hdf", "standard", "recessed"],
        ),
        ElementOption(
            id="full_18mm",
            name="Full 18mm Back Panel",
            category=ElementCategory.BACK_PANEL,
            description="Full-thickness 18mm back panel for wall-mounted or freestanding units",
            technical_spec="18mm MDF/melamine back panel, screw-fixed, adds structural rigidity",
            keywords=["thick", "structural", "18mm", "full"],
        ),
        ElementOption(
            id="open_back",
            name="Open Back (No Panel)",
            category=ElementCategory.BACK_PANEL,
            description="No back panel — the wall behind is visible",
            technical_spec="No back panel, open back design, may need wall fixing for stability",
            keywords=["open", "none", "wall-visible"],
        ),
    ],

    # --- LEG STYLE ---
    ElementCategory.LEG_STYLE.value: [
        ElementOption(
            id="none_plinth",
            name="Plinth / No Legs",
            category=ElementCategory.LEG_STYLE,
            description="Sits on a recessed plinth base (no visible legs)",
            technical_spec="Recessed plinth base, 60-80mm height, set back 30mm from front",
            is_default=True,
            keywords=["plinth", "base", "no legs", "recessed"],
        ),
        ElementOption(
            id="hairpin",
            name="Hairpin Legs",
            category=ElementCategory.LEG_STYLE,
            description="Thin metal hairpin legs, mid-century modern style",
            technical_spec="12mm steel hairpin legs, 150-200mm height, powder coated",
            keywords=["hairpin", "metal", "mid-century", "retro"],
        ),
        ElementOption(
            id="tapered_wood",
            name="Tapered Wood Legs",
            category=ElementCategory.LEG_STYLE,
            description="Tapered solid wood legs, Scandinavian style",
            technical_spec="Solid oak/walnut tapered legs, 100-150mm height, angled 5-8 degrees",
            keywords=["tapered", "wood", "scandinavian", "angled"],
        ),
        ElementOption(
            id="metal_square",
            name="Square Metal Frame",
            category=ElementCategory.LEG_STYLE,
            description="Square metal tube legs or frame base",
            technical_spec="25x25mm square steel tube legs/frame, powder coated, adjustable feet",
            keywords=["square", "metal", "frame", "industrial"],
        ),
        ElementOption(
            id="wall_mounted",
            name="Wall Mounted (No Floor Contact)",
            category=ElementCategory.LEG_STYLE,
            description="Wall-mounted — suspended off the floor entirely",
            technical_spec="Heavy-duty concealed wall mounting brackets, no floor contact",
            keywords=["wall", "mounted", "floating", "suspended"],
        ),
    ],

    # --- SURFACE FINISH ---
    ElementCategory.SURFACE_FINISH.value: [
        ElementOption(
            id="matte_paint",
            name="Matte Paint",
            category=ElementCategory.SURFACE_FINISH,
            description="Smooth matte spray-painted finish",
            technical_spec="2K polyurethane matte spray finish, smooth, low sheen",
            is_default=True,
            keywords=["matte", "paint", "spray", "smooth"],
        ),
        ElementOption(
            id="semi_gloss",
            name="Semi-Gloss Lacquer",
            category=ElementCategory.SURFACE_FINISH,
            description="Semi-gloss lacquered finish with slight sheen",
            technical_spec="2K polyurethane semi-gloss lacquer, 40-60% gloss",
            keywords=["semi-gloss", "lacquer", "sheen"],
        ),
        ElementOption(
            id="natural_oil",
            name="Natural Oil / Wax",
            category=ElementCategory.SURFACE_FINISH,
            description="Natural hardwax oil finish that shows the wood grain",
            technical_spec="Hardwax oil finish (e.g., Osmo), natural look, matte, grain-enhancing",
            keywords=["oil", "wax", "natural", "wood", "grain"],
        ),
        ElementOption(
            id="veneer",
            name="Wood Veneer",
            category=ElementCategory.SURFACE_FINISH,
            description="Real wood veneer applied over MDF substrate",
            technical_spec="0.6mm real wood veneer on MDF, lacquered or oiled topcoat",
            keywords=["veneer", "real wood", "premium"],
        ),
        ElementOption(
            id="melamine",
            name="Melamine / Laminate",
            category=ElementCategory.SURFACE_FINISH,
            description="Pre-finished melamine or HPL laminate surface",
            technical_spec="Melamine or HPL laminate surface, highly durable, various decors",
            keywords=["melamine", "laminate", "durable", "practical"],
        ),
    ],

    # --- GRAIN PATTERN ---
    ElementCategory.GRAIN_PATTERN.value: [
        ElementOption(
            id="none_solid_color",
            name="Solid Color (No Grain)",
            category=ElementCategory.GRAIN_PATTERN,
            description="Uniform solid color, no visible grain pattern",
            technical_spec="Solid color finish, no grain, uniform appearance",
            is_default=True,
            keywords=["solid", "plain", "no grain", "uniform"],
        ),
        ElementOption(
            id="straight_grain",
            name="Straight Grain",
            category=ElementCategory.GRAIN_PATTERN,
            description="Linear, straight wood grain pattern running lengthwise",
            technical_spec="Straight grain pattern, consistent direction, clean and modern",
            keywords=["straight", "linear", "clean"],
        ),
        ElementOption(
            id="cathedral_grain",
            name="Cathedral / Arched Grain",
            category=ElementCategory.GRAIN_PATTERN,
            description="Prominent arched (cathedral) grain pattern, traditional look",
            technical_spec="Cathedral/arched grain pattern, prominent figure, traditional feel",
            keywords=["cathedral", "arched", "prominent", "traditional"],
        ),
        ElementOption(
            id="quarter_sawn",
            name="Quarter-Sawn / Rift",
            category=ElementCategory.GRAIN_PATTERN,
            description="Tight, uniform grain from quarter-sawn or rift-cut lumber",
            technical_spec="Quarter-sawn or rift-cut grain, tight and uniform, premium",
            keywords=["quarter-sawn", "rift", "tight", "uniform", "premium"],
        ),
    ],

    # --- DOOR TYPE ---
    ElementCategory.DOOR_TYPE.value: [
        ElementOption(
            id="slab_flat",
            name="Slab / Flat Door",
            category=ElementCategory.DOOR_TYPE,
            description="Flat, plain slab door — minimalist and modern",
            technical_spec="18mm flat slab door, no frame or panel detail, clean edges",
            is_default=True,
            keywords=["slab", "flat", "modern", "minimal"],
        ),
        ElementOption(
            id="shaker_door",
            name="Shaker Door",
            category=ElementCategory.DOOR_TYPE,
            description="Classic shaker-style door with recessed center panel",
            technical_spec="5-piece shaker door, recessed center panel, 80mm frame width",
            keywords=["shaker", "classic", "recessed panel", "traditional"],
        ),
        ElementOption(
            id="glass_framed",
            name="Glass Front Door",
            category=ElementCategory.DOOR_TYPE,
            description="Door with glass panel (clear, frosted, or reeded)",
            technical_spec="Aluminum or wood frame door with 4mm glass panel insert",
            keywords=["glass", "display", "transparent", "frosted", "reeded"],
        ),
        ElementOption(
            id="tambour",
            name="Tambour / Slatted Door",
            category=ElementCategory.DOOR_TYPE,
            description="Tambour or slatted rolling/sliding door",
            technical_spec="Slatted tambour door, flexible slat panel on track, 8mm slats",
            keywords=["tambour", "slatted", "rolling", "sliding"],
        ),
    ],

    # --- DRAWER FRONT ---
    ElementCategory.DRAWER_FRONT.value: [
        ElementOption(
            id="integrated",
            name="Integrated / Flat Front",
            category=ElementCategory.DRAWER_FRONT,
            description="Flush, integrated drawer front matching the carcass",
            technical_spec="18mm flat drawer front, flush mount, integrated with carcass",
            is_default=True,
            keywords=["flat", "integrated", "flush"],
        ),
        ElementOption(
            id="inset_finger_pull",
            name="Inset with Finger Pull",
            category=ElementCategory.DRAWER_FRONT,
            description="Inset drawer with a routed finger pull at the top edge",
            technical_spec="18mm inset drawer front, 20mm finger pull routed into top edge",
            keywords=["inset", "finger pull", "routed"],
        ),
        ElementOption(
            id="overlay",
            name="Full Overlay",
            category=ElementCategory.DRAWER_FRONT,
            description="Drawer front overlaps the carcass sides (common in kitchens)",
            technical_spec="18mm full overlay drawer front, 2mm gap between adjacent fronts",
            keywords=["overlay", "full", "kitchen"],
        ),
    ],
}


# ============================================================================
# Lookup Helpers
# ============================================================================

def get_all_categories() -> list[str]:
    """Return all available element categories."""
    return list(ELEMENT_LIBRARY.keys())


def get_options(category: str) -> list[ElementOption]:
    """Return all options for a given category."""
    return ELEMENT_LIBRARY.get(category, [])


def get_option(category: str, option_id: str) -> ElementOption | None:
    """Find a specific option by category and ID."""
    for opt in ELEMENT_LIBRARY.get(category, []):
        if opt.id == option_id:
            return opt
    return None


def get_default(category: str) -> ElementOption | None:
    """Return the default option for a category."""
    for opt in ELEMENT_LIBRARY.get(category, []):
        if opt.is_default:
            return opt
    opts = ELEMENT_LIBRARY.get(category, [])
    return opts[0] if opts else None


def get_category_display_name(category: str) -> str:
    """Human-readable name for a category key."""
    return category.replace("_", " ").title()
