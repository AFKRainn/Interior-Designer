"""
Domain Knowledge for Architectural and Furniture Design

Standards, rules of thumb, and common-sense completeness checks
that get injected into council prompts based on the design type.
"""

# ---------------------------------------------------------------------------
# General Design Standards (always included)
# ---------------------------------------------------------------------------

GENERAL_STANDARDS = """\
DESIGN STANDARDS & COMPLETENESS CHECKS:
- Every structural element needs a back: shelving units need back panels, 
  cabinets need backs (specify if intentionally open-backed).
- Every freestanding piece needs a base/support system: legs, plinth, 
  wall-mounting, or floor integration.
- All materials should have specified thickness (e.g., 18mm MDF, 3mm HDF back).
- Edge treatment must be considered for all exposed edges.
- If it has doors/drawers, specify the opening mechanism (hinges, slides, 
  push-to-open) and handle style.
- Hardware is implicit but should be noted: hinges, slides, shelf pins, 
  connectors, mounting brackets.
- Consider structural integrity: spans over 600mm without support need 
  reinforcement or thicker material. Tall unsupported shelves bow.
- Weight-bearing surfaces (shelves holding books, countertops) need 
  appropriate thickness (minimum 18mm, ideally 25mm+ for heavy loads).
"""

# ---------------------------------------------------------------------------
# Furniture-Specific Knowledge
# ---------------------------------------------------------------------------

FURNITURE_STANDARDS = """\
FURNITURE DESIGN STANDARDS:
- Standard shelf depth: 25-35cm for books, 40-60cm for wardrobes.
- Standard shelf spacing: 25-35cm for books, 40-50cm for folded clothes.
- Standard desk height: 72-75cm. Standing desk: 100-110cm.
- Standard seat height: 43-48cm. Counter height: 90-92cm. Bar height: 100-110cm.
- Drawer depth: typically 40-50cm (interior), front adds 18-22mm.
- Door overlay: full overlay = 2mm gap; half overlay = reveals half the carcass.
- Wardrobe hanging rail height: 160-170cm for long garments, 90-100cm for 
  folded/short garments (double rail: top at 190cm, bottom at 100cm).
- TV unit: screen center at eye level when seated (~110cm from floor).
- Bookshelf: consider a slight backward lean (1-2 degrees) for stability, 
  or wall-anchor for tall units.
- Material choice drives design: MDF for painted finishes, plywood for 
  strength and visible edges, solid wood for natural grain.
- Standard MDF thickness: 16mm (economy), 18mm (standard), 25mm (heavy-duty).
- Back panels: 3mm HDF (recessed) for cost, 18mm for structural/wall-mounted units.
"""

# ---------------------------------------------------------------------------
# Kitchen-Specific Knowledge
# ---------------------------------------------------------------------------

KITCHEN_STANDARDS = """\
KITCHEN DESIGN STANDARDS:
- Work triangle: sink, stove, and refrigerator form a triangle with total 
  perimeter of 4-8 meters. No leg should be less than 1.2m or more than 2.7m.
- Counter height: standard 90-92cm (can vary for ergonomics).
- Upper cabinets: bottom edge at 135-140cm from floor, top at 210-230cm.
- Space between counter and upper cabinets: 45-55cm.
- Sink placement: ideally under or near a window. Must have counter space 
  on both sides (minimum 40cm one side, 60cm other side).
- Dishwasher: adjacent to sink for plumbing convenience.
- Minimum walkway: 90cm for single cook, 120cm for two cooks.
- Corner solutions: lazy susan, pull-out corner unit, or blind corner.
- Stove should not be directly next to a wall or window (fire safety + splash).
- Range hood: 65-75cm above gas cooktop, 55-65cm above electric.
- Appliance garage or pantry column: plan for tall storage.
"""

# ---------------------------------------------------------------------------
# Room Layout Standards
# ---------------------------------------------------------------------------

ROOM_STANDARDS = """\
ROOM DESIGN STANDARDS:
- Door clearance: minimum 80cm clear width, swing radius must not obstruct.
- Window placement: sill height typically 90cm (living areas), 120cm (bathrooms).
- Circulation paths: minimum 90cm for main paths, 60cm for secondary.
- Furniture from walls: large pieces typically 5-15cm from wall for cleaning.
- Sofa facing TV: optimal distance is 1.5-2.5x the screen diagonal.
- Dining table clearance: 90cm minimum from table edge to wall/furniture 
  for chair movement.
- Rug sizing: should extend 45-60cm beyond furniture edges.
- Lighting: layer ambient, task, and accent. Every room needs at least two 
  light sources at different heights.
- Electrical: plan outlet placement behind furniture, beside beds, 
  near desks. Minimum 2 outlets per wall in living areas.
- Scale: furniture should fill 2/3 of the room; 1/3 should remain open.
"""

# ---------------------------------------------------------------------------
# Building/Architectural Standards
# ---------------------------------------------------------------------------

BUILDING_STANDARDS = """\
BUILDING DESIGN STANDARDS:
- Floor-to-ceiling: standard residential 2.4-2.7m, commercial 3.0-3.6m.
- Staircase: riser 15-20cm, tread 22-30cm, width minimum 90cm.
- Doorway: minimum 2.1m height, 80cm width (90cm for main entry).
- Hallway: minimum 90cm width, 120cm preferred.
- Window area: typically 10-20% of floor area for natural light.
- Structural: load-bearing walls cannot be removed. Columns on grid spacing.
"""

# ---------------------------------------------------------------------------
# Logical Completeness Checklist
# ---------------------------------------------------------------------------

COMPLETENESS_CHECKLIST = """\
LOGICAL COMPLETENESS — VERIFY THESE:
1. Does every shelf/surface have stated dimensions and thickness?
2. Does the piece have a defined back (or explicitly open-backed)?
3. Is the base/support system specified?
4. Are all edges accounted for (exposed edges need treatment)?
5. If it has doors: opening direction, hinge type, handle/opening method?
6. If it has drawers: slide type, depth, front treatment?
7. Are internal divisions and compartments clearly defined?
8. Is the overall height practical for its purpose and placement?
9. Are material finishes consistent across the piece?
10. Would this design be structurally stable as described?
"""


def get_domain_knowledge(design_type: str) -> str:
    """
    Return domain knowledge appropriate for the design type.

    Args:
        design_type: One of "furniture", "room", "building", "kitchen"

    Returns:
        Concatenated domain knowledge string for prompt injection
    """
    sections = [GENERAL_STANDARDS, COMPLETENESS_CHECKLIST]

    design_type_lower = design_type.lower().strip()

    if "kitchen" in design_type_lower:
        sections.insert(1, KITCHEN_STANDARDS)
        sections.insert(1, FURNITURE_STANDARDS)
    elif "furniture" in design_type_lower or design_type_lower in (
        "cabinet", "shelf", "desk", "wardrobe", "bookshelf", "table",
        "chair", "bed", "dresser", "sideboard", "tv unit",
    ):
        sections.insert(1, FURNITURE_STANDARDS)
    elif "room" in design_type_lower or "interior" in design_type_lower:
        sections.insert(1, ROOM_STANDARDS)
        sections.insert(1, FURNITURE_STANDARDS)
    elif "building" in design_type_lower:
        sections.insert(1, BUILDING_STANDARDS)
        sections.insert(1, ROOM_STANDARDS)
    else:
        # Default: include furniture standards (most common use case)
        sections.insert(1, FURNITURE_STANDARDS)

    return "\n\n".join(sections)
