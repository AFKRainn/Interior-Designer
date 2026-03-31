"""
Quality Review Prompt Templates

Used by the council to review generated images against the DSD.
"""

# ---------------------------------------------------------------------------
# Image Quality Review
# ---------------------------------------------------------------------------

QUALITY_REVIEW_PROMPT = """You are a senior architect reviewing a generated \
architectural image for accuracy and quality.

DESIGN SPECIFICATION (what the image SHOULD show):
{dsd_description}

VIEW TYPE: {view_type}
VIEW DESCRIPTION: {view_description}

The attached image was generated based on this specification. \
Review it carefully and score it on the following criteria (1-10 each):

Respond with a JSON object:
{{
  "scores": {{
    "dimensional_accuracy": <1-10>,
    "material_color_accuracy": <1-10>,
    "style_adherence": <1-10>,
    "view_correctness": <1-10>,
    "overall_quality": <1-10>
  }},
  "average_score": <calculated average>,
  "approved": <true if average >= {min_score}, false otherwise>,
  "feedback": {{
    "strengths": ["what the image does well"],
    "issues": ["specific problems that need fixing"],
    "suggestions": ["concrete suggestions for improvement"]
  }},
  "regeneration_prompt_additions": "If not approved, provide specific \
instructions to add to the generation prompt to fix the issues"
}}

Be strict but fair. The goal is professional architectural quality. \
Score dimensional_accuracy based on whether proportions match. \
Score material_color_accuracy based on whether materials and colors match. \
Score style_adherence based on whether the overall style matches. \
Score view_correctness based on whether this is the correct view type. \
Score overall_quality based on professional presentation quality."""

# ---------------------------------------------------------------------------
# Comparative Review (for refinement — before/after)
# ---------------------------------------------------------------------------

CHANGE_VERIFICATION_PROMPT = """You are verifying that a design change was \
applied correctly. Compare the original and modified images.

REQUESTED CHANGE:
{change_description}

CHANGE TYPE: {change_type}
SECTIONS AFFECTED: {sections_affected}

Two images are attached:
1. ORIGINAL image (before the change)
2. MODIFIED image (after the change)

Verify:
1. Was the requested change applied correctly?
2. Were there any UNINTENDED changes?
3. Does everything else remain identical?

Respond with a JSON object:
{{
  "change_applied_correctly": true | false,
  "unintended_changes": [
    "list any changes that were NOT requested"
  ],
  "verification_passed": true | false,
  "notes": "any additional observations"
}}

Be extremely careful about unintended changes. The goal is to modify \
ONLY what was requested and keep everything else identical."""
