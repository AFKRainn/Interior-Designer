"""
Refinement / Change Management Prompt Templates

Used to classify changes, update the DSD, and guide targeted regeneration.
"""

# ---------------------------------------------------------------------------
# Change Classification
# ---------------------------------------------------------------------------

CHANGE_CLASSIFICATION_PROMPT = """You are a design change analyst. The user has \
requested a modification to an existing design.

CURRENT DESIGN SPECIFICATION:
{dsd_description}

USER'S CHANGE REQUEST:
"{change_request}"

Classify this change and determine its impact. Respond with a JSON object:
{{
  "change_type": "cosmetic" | "structural" | "additive" | "subtractive",
  "description": "clear description of what needs to change",
  "dsd_sections_affected": [
    "list of DSD sections that need updating, e.g.: colors, materials, \
dimensions, structural_elements, style, spatial_layout, context"
  ],
  "views_to_regenerate": [
    "list of view types that need new images, e.g.: floor_plan, \
front_elevation, side_elevation, perspective_3d_front, perspective_3d_angle"
  ],
  "views_unaffected": [
    "list of view types that do NOT need regeneration"
  ],
  "reasoning": "why you classified the change this way and chose these views",
  "risk_level": "low | medium | high — risk of unintended side effects"
}}

CLASSIFICATION RULES:
- cosmetic: Only visual appearance changes (color, texture, finish). \
Does NOT affect layout, dimensions, or structure.
- structural: Changes to layout, dimensions, proportions, or arrangement.
- additive: Adding a new element that didn't exist before.
- subtractive: Removing an existing element.

VIEW REGENERATION RULES:
- ALL technical views (floor_plan and ALL front_elevations) MUST ALWAYS \
be listed in views_to_regenerate regardless of change type. This is \
mandatory — consistency across all views is critical.
- For L-shaped designs, include BOTH front_elevation entries.
- For U-shaped designs, include ALL THREE front_elevation entries.
- Never skip regeneration of any technical view."""

# ---------------------------------------------------------------------------
# DSD Update
# ---------------------------------------------------------------------------

DSD_UPDATE_PROMPT = """You are updating a Design Specification Document (DSD) \
based on an approved change request.

CURRENT DSD:
{current_dsd_json}

CHANGE REQUEST:
Type: {change_type}
Description: {change_description}
Sections to update: {sections_affected}

{baseline_lock_notice}

Produce the UPDATED DSD as a complete JSON object. Rules:
1. ONLY modify the sections listed in "sections_affected"
2. Keep ALL other sections EXACTLY as they are
3. Maintain all IDs, timestamps, and metadata (except updated_at)
4. The version number should be incremented by 1
5. Add this change to the change_history array
6. If baseline is locked, do NOT modify any locked fields unless \
the change request explicitly targets them. Locked fields represent \
the user's approved design intent and must be preserved.

Return the complete updated DSD JSON."""

# ---------------------------------------------------------------------------
# Targeted Regeneration
# ---------------------------------------------------------------------------

TARGETED_REGENERATION_PROMPT = """Generate a modified version of this \
architectural image. A specific change has been made to the design.

FULL UPDATED DESIGN SPECIFICATION:
{dsd_description}

CHANGE THAT WAS MADE:
{change_description}

WHAT CHANGED: {what_changed}
WHAT MUST STAY THE SAME: Everything else — layout, proportions, placement, \
and all elements not mentioned in the change.

{baseline_lock_notice}

CRITICAL: This is a targeted edit. You MUST maintain the exact same \
composition, viewpoint, proportions, and layout. ONLY apply the \
specified change. The result should look like the same image with \
just the requested modification applied. If the design has a baseline \
lock, all locked aspects (structure, dimensions, layout) MUST be \
preserved exactly.

VIEW TYPE: {view_type}
"""

# ---------------------------------------------------------------------------
# Council Quick Review (for changes)
# ---------------------------------------------------------------------------

COUNCIL_QUICK_REVIEW_PROMPT = """A change has been requested to an existing \
design. Review whether this change is valid and complete.

ORIGINAL DSD:
{original_dsd}

UPDATED DSD:
{updated_dsd}

CHANGE REQUEST: {change_description}
CHANGE TYPE: {change_type}

Review and respond with a JSON object:
{{
  "change_valid": true | false,
  "change_complete": true | false,
  "issues": ["any issues with the change"],
  "suggestions": ["any suggestions for improvement"],
  "approved": true | false
}}

A change is valid if it makes sense architecturally and doesn't \
create contradictions in the design. A change is complete if all \
necessary DSD sections were updated consistently."""
