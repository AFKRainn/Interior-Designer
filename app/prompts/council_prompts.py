"""
Council Deliberation Prompt Templates

Redesigned for forensic precision and genuine expert debate.
Each round builds on the previous with evidence-based reasoning:

  Round 1: Independent forensic analysis — each member examines the image
           and brief independently, citing specific visual evidence for
           every element they identify.

  Round 2: Point-by-point expert debate — members challenge each other's
           interpretations, defend their evidence, and only concede when
           genuinely convinced by stronger evidence.

  Round 3: Final convergence — members declare their final position on each
           element, explicitly tracking what changed and why, what held firm
           and on what grounds.

  Chairman: Synthesizes the debate into a DSD, tagging consensus vs.
            majority decisions vs. chairman judgment calls.
"""

# ---------------------------------------------------------------------------
# System Prompt — Expert Identity
# ---------------------------------------------------------------------------

COUNCIL_SYSTEM_PROMPT = """\
You are a {role_description} serving on an elite architectural design council.

YOUR CORE PRINCIPLE — EVIDENCE ABOVE AGREEMENT:
You do not seek to agree with your colleagues. You seek the most accurate \
interpretation of what the client has shown and described. Every element you \
identify must be backed by specific evidence from the image or text.

- State EXACTLY what you see (observation) and what you conclude (interpretation).
- NEVER state a conclusion without citing your evidence.
- If a colleague sees something differently, challenge them specifically.
- ONLY concede a position if they provide genuinely stronger evidence.
- NEVER change your view just because a colleague is assertive.
- If you are convinced, say EXACTLY what convinced you.

YOUR ANALYTICAL LENS:
{role_description} — bring this expertise to every analysis. See what others \
might miss through your specific expert perspective.

{domain_knowledge}"""


# ---------------------------------------------------------------------------
# Round 1: Independent Analysis — Text Only
# ---------------------------------------------------------------------------

ROUND1_TEXT_PROMPT = """\
Analyze the following design description. You will share this analysis with \
two expert colleagues who may interpret things differently — write it as if \
you are building a case you are prepared to defend.

CLIENT BRIEF:
{user_input}

Work through this in four phases, writing out each phase before the JSON:

=== PHASE 1: USER NEEDS ANALYSIS ===
Extract every explicit and implied requirement from the brief:
- Primary design goal (what exactly is being designed)
- Physical requirements: dimensions stated (ONLY state if explicitly given), spatial needs, capacity
- Material and finish preferences (stated or strongly implied)
- Style and aesthetic requirements
- Functional requirements (how it will be used, who uses it)
- Placement and context (where it will go, what is around it)
- Any constraints or special requirements
Mark each: (EXPLICITLY STATED) / (REASONABLY IMPLIED) / (MY ASSUMPTION)

=== PHASE 2: DESIGN INTENT INFERENCE ===
Go beyond what was literally said. What problem is the client trying to solve? \
What experience should this design create? What standard architectural or \
design conventions apply here that the client may have assumed without stating?

=== PHASE 3: GAPS AND ASSUMPTIONS ===
List what is NOT specified but must be decided. For each assumption, state \
the architectural or design reasoning behind it.
Mark each: (STANDARD PRACTICE) / (REASONABLE INFERENCE) / (MY ASSUMPTION — CHALLENGEABLE)

=== PHASE 4: PRE-EMPTIVE VULNERABILITY CHECK ===
Where is your interpretation most likely to be wrong? List 2-3 specific points \
and what evidence would change your mind. This demonstrates analytical rigor \
and helps your colleagues focus their scrutiny.

=== STRUCTURED INTERPRETATION ===
Now your full structured interpretation as JSON:
{{
  "type": "furniture" | "room" | "building",
  "name": "clear descriptive name for this design",
  "description": "rich, detailed description of the design",
  "dimensions": {{
    "width": "explicit stated value with unit, or null if not specified",
    "height": "explicit stated value with unit, or null if not specified",
    "depth": "explicit stated value with unit, or null if not specified",
    "notes": "state source — 'explicitly stated in brief', 'estimated from context', or 'not specified'"
  }},
  "style": {{
    "aesthetic": "overall style (modern, rustic, industrial, etc.)",
    "era": "design era or null",
    "influences": ["design influences"]
  }},
  "materials": [
    {{"name": "material", "usage": "where used", "finish": "surface finish"}}
  ],
  "colors": {{
    "primary": "main color or null if unspecified",
    "secondary": "secondary color or null",
    "accent": "accent color or null",
    "notes": "confidence and source"
  }},
  "structural_elements": [
    {{
      "name": "element name",
      "description": "full description of what this is and how it appears",
      "material": "material",
      "position": "precise spatial position in the design",
      "count": 1
    }}
  ],
  "spatial_layout": "how all elements relate to each other spatially",
  "context": {{
    "placement": "where this design would be placed",
    "surroundings": "what is around it",
    "scale_reference": "human / room / building scale"
  }},
  "views_recommended": [
    {{
      "type": "floor_plan",
      "label": "Floor Plan",
      "description": "top-down 2D view showing spatial layout and all elements"
    }},
    {{
      "type": "front_elevation",
      "label": "Front Elevation — Wall A",
      "description": "frontal 2D view of the main face"
    }}
  ],
  "generation_notes": "precise instructions critical for accurate image generation",
  "confidence_level": "HIGH | MEDIUM | LOW",
  "key_assumptions": ["list every major assumption made — these may be challenged"]
}}

VIEWS DECISION — you decide exactly which views are needed:
- Always exactly 1 floor_plan.
- 1 front_elevation per distinct wall/face: single-face = 1, L-shaped = 2,
  U-shaped = 3, full room = up to 4. Each must have a UNIQUE descriptive label.
- Add side_elevation or rear_elevation if needed for this specific design.
- No 3D renders here — those are generated separately."""


# ---------------------------------------------------------------------------
# Round 1: Independent Analysis — Image Only
# ---------------------------------------------------------------------------

ROUND1_IMAGE_PROMPT = """\
You are analyzing a design sketch or reference image submitted by the client. \
This image is your PRIMARY physical evidence. Examine it with the precision of \
a forensic analyst. You will share this analysis with two expert colleagues \
who will challenge your interpretations — build a case you can defend.

BRIEF FROM DESIGN CONSULTANT (client's stated needs):
{additional_context}

Work through FIVE phases, writing out each phase in full before the JSON:

=== PHASE 1: FORENSIC IMAGE SCAN ===
Examine every part of the image systematically. For each element you identify, \
use this format:
[ELEMENT]: [Exactly what I see] → [What I interpret this as] | \
CONFIDENCE: HIGH/MEDIUM/LOW | EVIDENCE: [specific visual cue that led me here]

Work through in this order:

A) OVERALL FORM:
   What is the general shape? (rectangular, L-shaped, U-shaped, irregular?)
   How many distinct sections or zones?
   Approximate aspect ratio (height vs. width)?
   Freestanding, wall-mounted, or built-in?

B) BOUNDARIES AND STRUCTURAL SHELL:
   What defines the outer edges? (walls, side panels, casing?)
   Any corners, angles, recesses, or curves?
   What is the structural frame or enclosure made of (inferred)?

C) OPENINGS — analyze every potential opening with care:
   - Is there a DOOR? Evidence: (hinges shown? handle visible? panel line suggesting a leaf? gap in frame?)
     If yes: position (left/right/center), approximate relative size, swing direction if discernible.
   - Is there a WINDOW? Evidence: (frame lines? glazing indication — cross-hatching, thin parallel lines?)
     If yes: position on wall, approximate size relative to wall.
   - Any PASSAGES, arches, or cutouts?
   IMPORTANT — for any rectangle or break in a wall: is this a door, window, shelf
   opening, or decorative panel? State your evidence for each conclusion.

D) INTERIOR ELEMENTS (scan left to right, top to bottom):
   For each: what do I see (lines, shapes) → what is it → count and position →
   relative size (what fraction of the overall height/width does it occupy?)

E) PROPORTIONS AND SCALE:
   Any scale reference visible? (human figure, door frame, standard object?)
   What dimension annotations or numbers are visible in the sketch?
   Are internal proportions internally consistent?

F) ANNOTATIONS:
   Are there any numbers, letters, arrows, or dimension markers visible in the image?
   If yes: exactly what do they say, and what do they label?
   Any written notes in the drawing?

G) MATERIAL CUES:
   Does the drawing style, line density, or hatching suggest specific materials?
   What surface finish does the sketch imply?

H) DRAWING QUALITY AND INTENT:
   Hand sketch, CAD, or photo?
   Precision level: (very precise = treat as reliable; rough = proportional guide only)
   Are certain areas more carefully drawn? (emphasis = important detail)

=== PHASE 2: USER NEEDS ANALYSIS ===
From the consultant brief, extract:
- Primary design goal
- Explicitly stated dimensions (if any — ONLY include if clearly stated)
- Required materials, finishes, colors
- Functional requirements
- Style preferences
- Context and placement
- Special requirements

=== PHASE 3: IMAGE vs. NEEDS CROSS-REFERENCE ===
For each key design element, compare image vs. brief:
  "Image shows: [X] | Brief states: [Y] | Status: ALIGNED / CONFLICT / IMAGE ONLY / BRIEF ONLY"
If CONFLICT: "I trust the [IMAGE / BRIEF] more because: [reason]"

Conflict resolution rules:
- Spatial geometry and layout → trust the IMAGE (it is physical evidence)
- Materials and colors → trust the BRIEF (more explicitly stated)
- Dimensions → prefer explicitly stated numbers; sketch annotations override guesses
- If image and brief directly contradict: state both and explain your resolution

=== PHASE 4: PRE-EMPTIVE VULNERABILITY CHECK ===
Before your colleagues challenge you, honestly flag where you are most likely wrong:
1. [Element]: I said [interpretation]. This could be wrong if [alternative].
   Evidence that would change my mind: [what to look for]
2. [Second element]: same structure
3. (Optional third)
This is not weakness — it is analytical precision.

=== PHASE 5: STRUCTURED INTERPRETATION ===
Your full structured interpretation as JSON:
{{
  "type": "furniture" | "room" | "building",
  "name": "clear descriptive name",
  "description": "rich description combining ALL evidence from image and brief",
  "dimensions": {{
    "width": "exact stated/annotated value with unit, or null if not visible/stated",
    "height": "exact stated/annotated value with unit, or null",
    "depth": "exact stated/annotated value with unit, or null",
    "notes": "CRITICAL — state source: 'explicitly in brief', 'annotation visible in sketch', \
'estimated from scale reference [X] — APPROXIMATE', or 'not specified'"
  }},
  "style": {{
    "aesthetic": "style as evidenced by image + brief combined",
    "era": "design era or null",
    "influences": ["design influences"]
  }},
  "materials": [
    {{"name": "material", "usage": "where used", "finish": "finish",
      "source": "image_evidence | brief_stated | inferred"}}
  ],
  "colors": {{
    "primary": "color or null if genuinely unspecified",
    "secondary": "color or null",
    "accent": "color or null",
    "notes": "source and confidence level"
  }},
  "structural_elements": [
    {{
      "name": "element name",
      "description": "description with evidence basis",
      "material": "material",
      "position": "precise position in the design",
      "count": 1,
      "confidence": "HIGH | MEDIUM | LOW"
    }}
  ],
  "spatial_layout": "spatial layout based on forensic image analysis",
  "context": {{
    "placement": "placement context",
    "surroundings": "any visible surroundings",
    "scale_reference": "scale reference used for dimension estimates"
  }},
  "views_recommended": [
    {{
      "type": "floor_plan",
      "label": "Floor Plan",
      "description": "top-down 2D view showing layout and all elements"
    }},
    {{
      "type": "front_elevation",
      "label": "Front Elevation — Wall A",
      "description": "frontal 2D view of the main face"
    }}
  ],
  "generation_notes": "precise instructions for accurate image generation — \
list every key element that MUST appear and any proportions critical to get right",
  "image_analysis_notes": "summary of key forensic findings from the image scan",
  "confidence_level": "HIGH | MEDIUM | LOW",
  "disputed_elements": [
    "elements you expect your colleagues to challenge, and your evidence for each"
  ]
}}

VIEWS DECISION: 1 floor_plan always. 1 front_elevation per distinct wall/face.
L-shaped = 2, U-shaped = 3, full room = up to 4. Unique descriptive labels.
Do NOT include 3D renders here."""


# ---------------------------------------------------------------------------
# Round 1: Independent Analysis — Mixed (Image + Text)
# ---------------------------------------------------------------------------

ROUND1_MIXED_PROMPT = """\
You are analyzing a design that the client has provided BOTH as a sketch/image \
AND as a text description. The image is your PRIMARY physical evidence of the \
geometry and layout. The text expresses the client's INTENT and requirements. \
Analyze both with forensic precision. You will debate your findings with two \
expert colleagues.

TEXT DESCRIPTION (client's stated intent and requirements):
{user_text}

[The sketch/image is attached — study it alongside this text.]

Work through FIVE phases before the JSON:

=== PHASE 1: FORENSIC IMAGE SCAN ===
Examine every part of the image systematically. For each element:
[ELEMENT]: [What I see] → [What I interpret] | CONFIDENCE: HIGH/MEDIUM/LOW | \
EVIDENCE: [specific visual cue]

Cover in order:

A) OVERALL FORM: General shape, zones, aspect ratio, freestanding or built-in?

B) BOUNDARIES: Outer walls/edges, corners, structural enclosure?

C) OPENINGS — examine carefully:
   - Doors: hinges, handles, panel lines suggesting swing/sliding?
   - Windows: frame lines, glazing indication?
   - Passages, archways, cutouts?
   For ANY rectangle or wall break: door / window / shelf opening / decorative panel?
   State visual evidence for every conclusion.

D) INTERIOR ELEMENTS (left to right, top to bottom):
   Each: what do I see → what is it → position and count → relative size?

E) PROPORTIONS AND ANNOTATIONS:
   Any scale reference visible? Numbers or dimension markers in the drawing?
   Internally consistent proportions?

F) MATERIAL CUES: Drawing style, hatching, or line density suggesting materials?

G) DRAWING PRECISION: Hand sketch vs. CAD? Precision level?
   More carefully drawn areas = higher importance.

=== PHASE 2: TEXT BRIEF ANALYSIS ===
What does the text explicitly state vs. imply?
- Primary design goal
- Specific dimensions (ONLY note if clearly stated — do not infer from rough sketch)
- Materials, finishes, colors
- Functional requirements
- Style and aesthetic
- Context and placement
- Special requirements

=== PHASE 3: IMAGE vs. TEXT CROSS-REFERENCE ===
For each key element:
  "Image: [X] | Text: [Y] | Status: ALIGNED / CONFLICT / IMAGE ONLY / TEXT ONLY"

Conflict resolution:
- Spatial geometry and layout → trust IMAGE
- Materials, colors, finishes → trust TEXT
- Dimensions → prefer explicitly stated numbers; sketch annotations beat text estimates
- Mark every conflict: which source wins and why

=== PHASE 4: PRE-EMPTIVE VULNERABILITY CHECK ===
Where is your interpretation most likely wrong? 2-3 specific elements:
[Element]: I said [X]. Could be wrong if [Y]. Evidence that would change my mind: [Z].

=== PHASE 5: STRUCTURED INTERPRETATION ===
{{
  "type": "furniture" | "room" | "building",
  "name": "clear name",
  "description": "rich description merging image geometry with text intent",
  "dimensions": {{
    "width": "exact stated value with unit, or null",
    "height": "exact stated value with unit, or null",
    "depth": "exact stated value with unit, or null",
    "notes": "source — 'text states', 'sketch annotation', \
'estimated from [reference] — APPROXIMATE', or 'not specified'"
  }},
  "style": {{
    "aesthetic": "style from both sources",
    "era": "era or null",
    "influences": ["influences"]
  }},
  "materials": [
    {{"name": "material", "usage": "where", "finish": "finish",
      "source": "image_evidence | text_stated | inferred"}}
  ],
  "colors": {{
    "primary": "color or null",
    "secondary": "color or null",
    "accent": "color or null",
    "notes": "source and confidence"
  }},
  "structural_elements": [
    {{
      "name": "element",
      "description": "description with evidence source",
      "material": "material",
      "position": "precise position",
      "count": 1,
      "confidence": "HIGH | MEDIUM | LOW"
    }}
  ],
  "spatial_layout": "spatial layout from image analysis reconciled with text",
  "context": {{
    "placement": "placement",
    "surroundings": "surroundings",
    "scale_reference": "scale reference"
  }},
  "views_recommended": [
    {{
      "type": "floor_plan",
      "label": "Floor Plan",
      "description": "top-down 2D view of the layout"
    }},
    {{
      "type": "front_elevation",
      "label": "Front Elevation — Wall A",
      "description": "frontal 2D view of the main face"
    }}
  ],
  "generation_notes": "precise instructions for faithful reproduction — \
list every critical element and proportion that must be correct",
  "image_analysis_notes": "forensic image scan summary",
  "confidence_level": "HIGH | MEDIUM | LOW",
  "discrepancies": "all image-text conflicts found and how each was resolved"
}}

VIEWS DECISION: 1 floor_plan. 1 front_elevation per distinct wall/face.
L-shaped = 2, U-shaped = 3, full room = up to 4. Unique descriptive labels.
No 3D renders."""


# ---------------------------------------------------------------------------
# Round 2: Cross-Review Debate
# ---------------------------------------------------------------------------

ROUND2_REVIEW_PROMPT = """\
You have completed your independent analysis. Now you see what your two expert \
colleagues found from the SAME design input. Engage in genuine expert debate. \
Your goal is to reach the most accurate interpretation — not the most agreeable one.

YOUR ROUND 1 ANALYSIS:
{own_interpretation}

---
{other_member_1_name}'s ROUND 1 ANALYSIS:
{other_interpretation_1}

---
{other_member_2_name}'s ROUND 1 ANALYSIS:
{other_interpretation_2}

---

DEBATE RULES:
1. Address EVERY significant disagreement — skipping one means it is unresolved.
2. For every disagreement: cite your specific evidence (what you see or read).
3. Challenge your colleague's evidence: what might they have misread or overlooked?
4. Only concede if their evidence is genuinely stronger. State exactly WHY.
5. Only say "I hold firm" with a specific re-statement of your evidence.
6. Acknowledge anything your colleagues identified that you missed.
7. Propose synthesis where both interpretations might partially be correct.

Structure your response EXACTLY as follows:

=== AGREEMENTS ===
[List what all analyses agree on — brief confirmation only]

=== POINT-BY-POINT DEBATE ===
[Address every significant disagreement. For each point:]

POINT: [The specific element or aspect in dispute]
My Round 1 position: [What I concluded]
My evidence: [The specific visual cue or text reference I based this on]
{other_member_1_name} says: [Their interpretation of this element]
Their apparent evidence: [The basis they appear to be using]
{other_member_2_name} says: [Their interpretation]
Their apparent evidence: [The basis they appear to be using]
My verdict: HOLDING FIRM | CONCEDING to [member name] | PROPOSING SYNTHESIS
Reason: [The specific logic — what clinches it, or what I am now seeing differently]

[Repeat for every significant disagreement]

=== ELEMENTS MY COLLEAGUES IDENTIFIED THAT I MISSED ===
[Things others found that you overlooked. For each: accept with reasoning, or
dispute with evidence.]

=== REVISED POSITION SUMMARY ===
After this debate: what changed in your understanding, what held firm, and \
are there any points you believe remain genuinely unresolved?

=== UPDATED INTERPRETATION ===
Your updated structured interpretation as JSON, incorporating debate outcomes:
{{
  "type": "furniture" | "room" | "building",
  "name": "name",
  "description": "updated description reflecting debate outcomes",
  "dimensions": {{
    "width": "value with unit, or null",
    "height": "value with unit, or null",
    "depth": "value with unit, or null",
    "notes": "source — 'explicitly stated', 'sketch annotation', \
'estimated — APPROXIMATE', or 'not specified'"
  }},
  "style": {{"aesthetic": "style", "era": "era or null", "influences": ["influences"]}},
  "materials": [{{"name": "material", "usage": "usage", "finish": "finish"}}],
  "colors": {{
    "primary": "color or null", "secondary": "color or null",
    "accent": "color or null", "notes": "notes"
  }},
  "structural_elements": [
    {{
      "name": "element", "description": "description",
      "material": "material", "position": "position", "count": 1
    }}
  ],
  "spatial_layout": "updated spatial layout",
  "context": {{"placement": "placement", "surroundings": "surroundings", "scale_reference": "scale"}},
  "views_recommended": [
    {{"type": "floor_plan", "label": "Floor Plan", "description": "top-down 2D view"}},
    {{"type": "front_elevation", "label": "Front Elevation — Wall A",
      "description": "frontal 2D view"}}
  ],
  "generation_notes": "updated generation instructions incorporating debate outcomes",
  "confidence_level": "HIGH | MEDIUM | LOW",
  "positions_held_firm": [
    "elements where you maintained your Round 1 position against challenge, with evidence"
  ],
  "positions_changed": [
    "elements where you changed your interpretation and the specific reason why"
  ]
}}"""


# ---------------------------------------------------------------------------
# Round 3: Convergence — Final Position
# ---------------------------------------------------------------------------

ROUND3_CONVERGENCE_PROMPT = """\
You have analyzed, debated, and refined your interpretation through two rounds. \
Now produce your FINAL, DEFINITIVE interpretation. This is your last opportunity \
to get it right — the chairman will synthesize from your final outputs.

YOUR ROUND 1 (initial forensic analysis):
{own_round1}

YOUR ROUND 2 (cross-review debate):
{own_round2}

{other_member_1_name}'s ROUND 2 debate:
{other_round2_1}

{other_member_2_name}'s ROUND 2 debate:
{other_round2_2}

Review ALL debate outcomes from all three members. Some arguments in your \
colleagues' Round 2 responses may contain new evidence that further refines \
your understanding even now.

Your final response MUST include:

=== FINAL POSITION DECLARATION ===
For every significant element in the design, explicitly declare your final stance:

[UNCHANGED]: Element — [interpretation] — held through all rounds because [evidence]
[REVISED R1→R2]: Element — was [old], now [new] because [what specifically convinced me]
[REVISED R2→R3]: Element — was [old], now [new] after seeing [specific new argument/evidence]
[HELD FIRM against {other_member_1_name} / {other_member_2_name}]: Element — \
I maintain [interpretation] despite [their position] because [my evidence outweighs theirs]
[UNRESOLVED — best judgment]: Element — genuine ambiguity. \
I read it as [interpretation], acknowledging [the alternative]. Chairman should note this.

=== DESIGN INTENT SYNTHESIS ===
Beyond individual elements: what is the client's overall design intent? \
What kind of object/space is this and what experience should it create? \
What are the 3 most critical elements to get exactly right in the final specification?

=== FINAL STRUCTURED INTERPRETATION ===
{{
  "type": "furniture" | "room" | "building",
  "name": "final authoritative name",
  "description": "final comprehensive description — the definitive account of this design",
  "dimensions": {{
    "width": "final value with unit — or null if genuinely not specified",
    "height": "final value with unit — or null if genuinely not specified",
    "depth": "final value with unit — or null if genuinely not specified",
    "notes": "CRITICAL: 'explicitly stated in brief', 'visible annotation in sketch', \
'estimated from [reference] — APPROXIMATE', or 'not specified by client'"
  }},
  "style": {{"aesthetic": "final style", "era": "era or null", "influences": ["influences"]}},
  "materials": [{{"name": "material", "usage": "usage", "finish": "finish"}}],
  "colors": {{
    "primary": "color or null", "secondary": "color or null",
    "accent": "color or null", "notes": "confidence and source"
  }},
  "structural_elements": [
    {{
      "name": "element",
      "description": "full final description with confidence basis",
      "material": "material",
      "position": "precise position",
      "count": 1
    }}
  ],
  "spatial_layout": "final definitive spatial layout",
  "context": {{"placement": "placement", "surroundings": "surroundings", "scale_reference": "scale"}},
  "views_recommended": [
    {{
      "type": "floor_plan",
      "label": "Floor Plan",
      "description": "top-down 2D architectural floor plan"
    }},
    {{
      "type": "front_elevation",
      "label": "Front Elevation — [descriptive name]",
      "description": "frontal 2D elevation of [this specific face]"
    }}
  ],
  "generation_notes": "final precise instructions for accurate image generation — \
include every element that must appear, critical proportions, and any debate-resolved \
specifics the generation model must know",
  "confidence_level": "HIGH | MEDIUM | LOW",
  "debate_summary": "what key debates occurred and how they were resolved",
  "unresolved_ambiguities": [
    "any remaining genuine uncertainties the chairman should be aware of"
  ]
}}

VIEWS DECISION: 1 floor_plan. 1 front_elevation per distinct wall/face.
L-shaped = 2, U-shaped = 3, full room = up to 4. Unique descriptive labels.
Do NOT include 3D renders."""


# ---------------------------------------------------------------------------
# Chairman Synthesis
# ---------------------------------------------------------------------------

CHAIRMAN_SYNTHESIS_PROMPT = """\
You are the Chairman of the design council. Three expert architects have \
completed a full three-round deliberation process — forensic image analysis, \
point-by-point expert debate, and final convergence. They brought different \
expert lenses, challenged each other's evidence, and declared their final \
positions with explicit reasoning.

Your job: synthesize their final interpretations into ONE authoritative \
Design Specification Document.

=== COUNCIL MEMBERS' FINAL INTERPRETATIONS ===

CLAUDE'S FINAL INTERPRETATION:
{claude_final}

---
GPT'S FINAL INTERPRETATION:
{gpt_final}

---
GEMINI'S FINAL INTERPRETATION:
{gemini_final}

---

YOUR SYNTHESIS PROCESS:
For each element of the design specification, determine which category it falls into:

A) STRONG CONSENSUS: All three agree on this element → use this directly, high confidence.

B) MAJORITY DECISION: Two agree, one differs → use the majority. Note the dissent in
   generation_notes if it is significant.

C) CHAIRMAN CALL: All three differ, or the majority may be wrong → use your expert
   judgment. Explain your reasoning in generation_notes. Flag to the client.

SPECIAL RULES:

DIMENSIONS:
- Only include as a final dimension if AT LEAST TWO members confirm it was
  explicitly stated (in the brief or visible as an annotation in the sketch).
- If a member marked a dimension as "estimated" or "APPROXIMATE" and no other
  member confirms it as explicit, set that dimension to null and note it.
- Never invent or assume dimensions — an inaccurate number is worse than null.

STRUCTURAL ELEMENTS:
- Include elements that AT LEAST TWO members independently identified.
- Include elements only ONE member saw if their evidence was highly specific and
  compelling. Note the lower confidence in generation_notes.
- If members disagreed about what an element IS (door vs. window, shelf vs.
  drawer), and it remains unresolved, describe both possibilities and instruct
  the generation model on the more likely interpretation.

UNRESOLVED AMBIGUITIES:
- Where members flagged "UNRESOLVED" items, make a reasoned chairman call.
- Note these in generation_notes so the generation model handles them correctly.
- Note them in consensus_notes so the client knows.

VIEWS:
- Honor the consensus on the geometry (L-shaped, straight, etc.).
- Always 1 floor_plan, then the appropriate number of elevations.

Your response has TWO parts — output BOTH in this exact order:

PART 1 — THE DSD JSON (output this first, as a clean JSON object):

{{
  "type": "furniture" | "room" | "building",
  "name": "authoritative design name",
  "description": "comprehensive authoritative description",
  "dimensions": {{
    "width": "explicit client-stated value with unit, or null",
    "height": "explicit client-stated value with unit, or null",
    "depth": "explicit client-stated value with unit, or null",
    "notes": "if explicit: 'explicitly stated by client'. If not: 'not specified by client'"
  }},
  "style": {{
    "aesthetic": "consensus style",
    "era": "era or null",
    "influences": ["consensus influences"]
  }},
  "materials": [
    {{"name": "material", "usage": "usage", "finish": "finish"}}
  ],
  "colors": {{
    "primary": "final color or null",
    "secondary": "final secondary or null",
    "accent": "final accent or null",
    "notes": "confidence and source"
  }},
  "structural_elements": [
    {{
      "name": "element name",
      "description": "authoritative description",
      "material": "material",
      "position": "precise position",
      "count": 1
    }}
  ],
  "spatial_layout": "authoritative spatial layout description",
  "context": {{
    "placement": "placement",
    "surroundings": "surroundings",
    "scale_reference": "scale"
  }},
  "views_to_generate": [
    {{
      "type": "floor_plan",
      "label": "Floor Plan",
      "description": "top-down 2D architectural floor plan"
    }},
    {{
      "type": "front_elevation",
      "label": "Front Elevation — [descriptive name]",
      "description": "frontal 2D view of [specific face]"
    }}
  ],
  "generation_notes": "special instructions applying across all views",
  "consensus_notes": "summary: (A) strong consensus, (B) majority decisions, (C) chairman calls"
}}

VIEWS rules: Always 1 floor_plan. 1 front_elevation per distinct wall/face.
L-shaped = 2, U-shaped = 3, full room = up to 4. Unique descriptive labels.
No 3D renders in views_to_generate.

---

PART 2 — VIEW GENERATION PROMPTS (output this immediately after the JSON):

This is equally critical as the DSD. The image generation AI has NEVER seen the \
original design — your words are its ONLY reference. You are directing a skilled \
drafter who must produce an exact drawing based solely on what you write. \
A vague description produces a wrong image. A step-by-step, exhaustive description \
produces an accurate one.

MANDATORY STRUCTURE — every VIEW_PROMPT must follow this pattern:

  STEP 1 — OVERALL FORM: State the overall shape, proportions, and general layout.
    (e.g., "A wide horizontal rectangle, approximately 3× wider than tall, \
    divided into 5 vertical sections of unequal width.")
  STEP 2 — OUTER BOUNDARY: Describe the perimeter/outer frame in full detail.
  STEP 3 onward — SECTIONS: Walk through each major section from left to right \
    (or top to bottom for vertical layouts). For each section name it, state its \
    proportional width or height relative to its neighbors, describe all internal \
    subdivisions, and list every element it contains with position and appearance.
  Continue until EVERY element identified by the council has been described.
  FINAL STEP — CONCLUSION: A single closing sentence beginning with "CONCLUSION:" \
    that summarizes what the completed drawing looks like as a whole.

MANDATORY LENGTH:
- Simple piece (1-2 sections): minimum 10 lines.
- Medium piece (3-4 sections): minimum 15 lines.
- Complex piece (5+ sections, multi-level, or asymmetric): minimum 20 lines.
A VIEW_PROMPT shorter than 10 lines is NEVER acceptable. A one-paragraph summary \
is NEVER acceptable. If the design is complex, write 25-30 lines.

DIMENSIONS RULE (apply to every view type):
NEVER include specific measurements unless the client explicitly stated them. \
Check the dimensions.notes field — if it says "not specified by client", use \
NO numbers anywhere. Describe proportions relatively: "the upper half", "the left \
third", "roughly twice as wide as tall", "narrower than the central zone". \
Never write estimated or assumed numbers as if they are real client-stated values.

Use EXACTLY this format — one block per view, using the EXACT label from the JSON:

GENERATION_PROMPTS_START
VIEW_PROMPT: [exact label from JSON, e.g. "Floor Plan"]
STEP 1 — OVERALL FORM: [description]
STEP 2 — OUTER BOUNDARY: [description]
STEP 3 — [section name]: [description]
[continue steps...]
CONCLUSION: [single summary sentence]
VIEW_PROMPT_END

VIEW_PROMPT: [exact label from JSON, e.g. "Front Elevation — Wall A"]
[same step-by-step structure]
VIEW_PROMPT_END
GENERATION_PROMPTS_END

---
SPECIFIC RULES PER VIEW TYPE:

FOR FLOOR PLAN VIEW_PROMPT:
Describe ONLY what is visible from directly above — camera mounted on the ceiling \
looking straight down at a cross-section. This is NOT a description of heights or \
the 3D form. Every element is a flat 2D shape.

Cover in your steps:
- STEP 1: Overall footprint shape (rectangular, L-shaped, U-shaped, etc.) and \
  proportions (e.g., "wider than deep, roughly 4:1 ratio").
- STEP 2: Outer boundary — thick wall lines forming the full perimeter. Describe \
  any projections, recesses, or asymmetry.
- For each internal zone (left to right): describe the interior layout as thin \
  rectangles, lines, and shapes seen from above. Include:
    * Cabinet/shelving units: thin rectangles showing their depth footprint
    * Partitions: thin vertical or horizontal lines
    * Legs/feet: small squares or circles at their exact floor positions
    * Door openings: a STRAIGHT GAP in the wall boundary at the door position. \
      Write: "a door opening gap in [position] of [wall], labeled 'DOOR'." \
      NO swing arcs. NO quarter-circle curves. NO curved lines of any kind.
    * Labels/annotations: text identifying each zone by name
- CONCLUSION: Describe the completed floor plan as a labeled top-down diagram.

FOR FRONT ELEVATION VIEW_PROMPT:
Describe ONLY what is visible on the flat front face — looking straight at it, \
perfectly perpendicular. You see ONLY the flat 2D face. No sides. No top. No depth.

Cover in your steps:
- STEP 1: Overall silhouette — outer rectangle, width-to-height ratio \
  (e.g., "landscape rectangle, roughly 5:2 width-to-height").
- STEP 2: Outer frame/plinth — any trim panel, border reveal, or base plinth. \
  Describe its position and proportional height.
- For each vertical section (left to right): state its proportional width, then \
  describe top-to-bottom what is drawn in that section:
    * Open shelving: horizontal shelf lines at their vertical positions, described \
      as fractions ("at the one-third and two-thirds heights")
    * Closed cabinet doors: a rectangle outline filling the section, with any \
      panel reveal lines inside it
    * Drawers: stacked rectangles with their dividing lines, labeled
    * Hardware: type (bar handle, circular knob, recessed pull), position \
      (centered, bottom quarter, etc.)
    * Any decorative molding, grooves, or reveal lines on the face
- Ground line: a thin horizontal line at the base of the entire drawing.
- CONCLUSION: Describe the completed elevation as a flat labeled drawing.

FOR SIDE ELEVATION VIEW_PROMPT:
What you see looking straight at the side face: depth, total height, side profile \
silhouette, side-mounted elements (handles, panels), visible shelf depths. \
Same step-by-step structure.

FOR REALISTIC RENDER / 3D VIEW_PROMPT:
Full photographic description in steps: materials (exact colors, textures, \
finishes for every surface), lighting setup (source type, direction, warm/cool, \
intensity), environment (room type, floor material, wall color), contextual \
styling props, camera position and angle, overall mood and atmosphere. \
Same step-by-step structure with a CONCLUSION.

This document and the generation prompts drive ALL image generation. \
Every element the council identified must appear in the relevant VIEW_PROMPT. \
Thorough, step-by-step prompts produce accurate images. Vague prompts do not."""


# ---------------------------------------------------------------------------
# Council Quick Review (used by Refiner after DSD modifications)
# ---------------------------------------------------------------------------

COUNCIL_QUICK_REVIEW_PROMPT = """\
The design specification has been modified based on a client change request.
Review the modification and assess whether it is correct and complete.

ORIGINAL DSD:
{original_dsd}

CHANGE REQUEST:
{change_request}

UPDATED DSD:
{updated_dsd}

Assess the modification:
{{
  "approved": true | false,
  "issues": ["list any problems with the modification"],
  "suggestions": ["any improvements to the modification"],
  "reasoning": "brief explanation of your assessment"
}}

Be concise and focused — this is a quick review, not a full deliberation."""
