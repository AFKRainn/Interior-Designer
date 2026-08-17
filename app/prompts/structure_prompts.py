"""Structure agent prompts: brief -> spec, and utterance -> edit ops."""

OPENING_TREE_RULES = """\
A spec describes walls. Each wall has BAYS. Each bay is an OPENING TREE.

An opening either:
  - is a LEAF and carries a front:
      {"id":"row-1","size_cm":60,"front":{"type":"door","hinge":"left","handle":"bar"}}
  - or SPLITS into 2+ children:
      {"id":"bay-2","size_cm":90,"split":"rows","children":[ ... ]}

split "rows" divides top to bottom. split "cols" divides left to right.
Children are written in DRAWING ORDER: rows top-first, cols left-first.

SIZING — the only rule, and it applies at every depth:
  size_cm  = a fixed extent along the parent's split axis
  flex     = a share of whatever the fixed siblings leave over
  Use exactly one of them per node. Prefer flex wherever the brief did not
  state a number: flex always fits, so you cannot produce an invalid spec by
  getting arithmetic wrong. Give a node size_cm only when the client stated
  that measurement.

Two doors side by side in the top of a bay is a rows split whose first child
is a cols split:
  {"id":"bay-2","size_cm":90,"split":"rows","children":[
     {"id":"row-1","size_cm":60,"split":"cols","children":[
        {"id":"col-1","flex":1,"front":{"type":"door","hinge":"left","handle":"bar"}},
        {"id":"col-2","flex":1,"front":{"type":"door","hinge":"right","handle":"bar"}}]},
     {"id":"row-2","flex":1,"front":{"type":"drawer","count":3,"handle":"bar"}}]}

front.count > 1 is shorthand for a stack of that many equal fronts.
front.type is one of door, drawer, open, glass, appliance, panel, false_front.
Use "open" for an opening with no front.

Ids are unique among SIBLINGS only. Use readable ones: bay-1, row-1, col-1.

LAYOUT:
  layout.walls carries length, adjacent_to, faces, sequence, corner.
  adjacent_to and faces are symmetric. A pair is never both.
  L: two walls adjacent. U: three in sequence, the outer two face each other,
  the middle adjacent to both. Galley: two walls facing, not adjacent.
  Straight: one wall.
  CORNERS: where two runs meet, exactly one wall yields the other's depth.
  The later wall in sequence yields: give it corner {"start":"yield"} and
  give its neighbour corner {"end":"take"}. Bay sizes are measured against
  the run AFTER yielding, so prefer flex bays at a corner.
"""

SPEC_FROM_BRIEF = """\
Write a Furniture Spec as one JSON object. No markdown, no commentary.

{rules}

Shape:
{{
  "name": "...",
  "units": "cm",
  "layout": {{"type":"straight|L|U|galley|custom","walls":[
      {{"id":"wall-a","label":"...","length":320,"adjacent_to":[],"faces":[],
       "sequence":0,"corner":{{"start":null,"end":null}}}}]}},
  "walls": [
    {{"id":"wall-a","height":220,"depth":60,"reveal_mm":3,
      "cornice":{{"type":"straight","height":8}},
      "plinth":{{"type":"recessed","height":12}},
      "side_columns":{{"left_cm":0,"right_cm":0,"detail":"plain"}},
      "bays":[ ... openings ... ]}}
  ],
  "materials": {{"carcass":"","doors":"","finish":""}},
  "hardware": {{"style":"","placement":""}},
  "brief": "copy the locked brief",
  "assumptions": [{{"field":"plinth","value_cm":12,"rationale":"professional default"}}],
  "render_notes": ""
}}

Use only dimensions the brief states. Where it does not state one, use flex
and record the choice in assumptions. Do not invent extra walls or bays.

LOCKED BRIEF:
{brief}
"""

SPEC_REPAIR = """\
That spec failed validation. Return a corrected FULL spec JSON, no markdown.

The validator said:
{error}

Fix exactly that. The commonest cause is fixed sizes that do not add up —
switch a sibling to flex rather than fudging numbers.

{rules}

Previous attempt:
{spec_json}
"""

EDIT_SYSTEM = """\
You turn one sentence from a client into edit operations on a furniture spec.

You do not compute geometry. You choose an operation and its arguments; code
does the arithmetic and rejects anything that does not fit. Every op targets
a PATH like "wall-a/bay-2/row-1". Only use paths from the list you are given.

OPERATIONS
  set_size(path, size_cm)        pin a node's extent
  set_flex(path, flex)           let it share the remainder
  set_label(path, label)
  split(path, axis, count|ratios)  divide a LEAF into rows or cols
  merge(path)                    collapse a split back to one front
  add_child(path, index?, front_type?)   one more child in an existing split
  delete(path)
  set_front(path, type, hinge?, handle?, count?)   leaf only
  insert_bay(wall_id, index?, size_cm?|flex?, label?)
  delete via delete(path) for a bay too
  set_wall(wall_id, length? height? depth? reveal_mm? cornice_height?
           plinth_height? side_left_cm? side_right_cm?)
  set_corner(wall_id, end, mode)
  set_materials(carcass? doors? finish?)
  set_hardware(style? placement?)

"Two doors next to each other" in an existing single front is
  split(path, "cols", count=2)  — the children inherit the door and hinge
  outward automatically. Do not try to build it any other way.

Sizes are centimetres. Convert mm before emitting.

UNDERSTANDING: restate the change in the drawing's own words, naming the
paths. The client sees this sentence before anything is applied, so it is
your one chance to be caught being wrong.

AMBIGUITY IS A REQUIRED FIELD, NOT A MOOD. If the sentence could mean two
different edits, put the question in `ambiguities` with concrete options and
set action "clarify". Cases that are genuinely ambiguous:
  - a reference that matches several nodes ("the top part", "the big door")
  - a number with no unit or no obvious target
  - an instruction that would need a change you were not asked for
Cases that are NOT ambiguous — just do them:
  - a clear path or an obvious single match
  - a professional default the client plainly does not care about
  - anything the current selection already disambiguates

Set action "propose" only when you would bet the change is right. Otherwise
"clarify" and emit no ops.
"""

EDIT_USER = """\
Wall on screen: {wall_id}
Current selection: {selection}

Addressable nodes:
{inventory}

Materials: {materials}
Hardware: {hardware}

The client says:
{utterance}
"""

EDIT_RETRY = """\
Your previous ops were rejected: {error}

Emit corrected ops for the same request, or set action "clarify" if the
request cannot be satisfied as stated.
"""
