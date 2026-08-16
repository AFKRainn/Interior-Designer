"""Prompts for writing and patching a Furniture Spec JSON."""

SPEC_SCHEMA_RULES = """\
Return ONE JSON object. No markdown. No commentary.

Required shape:
{
  "name": "string",
  "units": "cm",
  "layout": {
    "type": "straight" | "L" | "U" | "galley" | "custom",
    "walls": [
      {
        "id": "wall-a",
        "label": "Wall A — ...",
        "length": 300,
        "adjacent_to": ["wall-b"],
        "faces": [],
        "sequence": 0
      }
    ]
  },
  "walls": [
    {
      "id": "wall-a",
      "height": 220,
      "depth": 60,
      "cornice": {"type": "straight", "height": 8},
      "plinth": {"type": "recessed", "height": 12},
      "side_columns": {"left_cm": 6, "right_cm": 6, "detail": "plain"},
      "bays": [
        {
          "id": "bay-1",
          "label": "Sink",
          "width": 80,
          "modules": [
            {"type": "drawer", "height": 20, "count": 1, "handle": "bar"},
            {"type": "door", "height": 180, "count": 1, "handle": "bar"}
          ]
        }
      ]
    }
  ],
  "materials": {"carcass": "", "doors": "", "finish": ""},
  "hardware": {"style": "", "placement": ""},
  "brief": "copy the locked brief",
  "render_notes": ""
}

HARD RULES
- layout.walls ids MUST equal walls ids.
- adjacent_to and faces MUST be symmetric.
- A pair cannot be both adjacent and facing.
- Bay widths on a wall MUST sum to that wall's length (within 1 cm).
- Modules in a bay stack from the BOTTOM (plinth) upward. First module = bottom.
- Module types: door, drawer, open_shelf, glass, appliance.
- Wall ids: wall-a, wall-b, wall-c, ... Bay ids unique: bay-1, bay-2, ...
- L: two walls, adjacent_to each other, faces empty.
- U: three walls in sequence; the two side walls face each other; middle adjacent to both.
- Galley: two walls, faces each other, adjacent_to empty.
- Straight: one wall, adjacent_to and faces empty.
- Island is not a wall unless it has a designed face.
- Only use dimensions the brief stated. If unknown, use a stated professional default and put the default in brief.
- Do not invent extra walls.
"""

SPEC_FROM_BRIEF_PROMPT = """\
Write a Furniture Spec JSON from this locked brief.

{schema_rules}

LOCKED BRIEF:
{brief}
"""

SPEC_REPAIR_PROMPT = """\
The spec JSON failed validation. Return a corrected full spec JSON. No markdown.

Validation error:
{error}

Previous JSON:
{spec_json}

{schema_rules}
"""

SPEC_PATCH_PROMPT = """\
Apply the client's change to the Furniture Spec. Return the FULL updated spec JSON.
No markdown. Change only what they asked. Keep project_id. Increment version by 1.
Bay widths must still sum to wall length. adjacent_to/faces stay symmetric.

{schema_rules}

CURRENT SPEC JSON:
{spec_json}

CLIENT CHANGE:
{instruction}
"""
