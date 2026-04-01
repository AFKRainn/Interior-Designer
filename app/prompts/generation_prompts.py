"""
Image Generation Prompt Templates

Two-layer architecture:

  LAYER 1 — STYLE WRAPPERS:
    Each view type has a style wrapper that enforces the visual rules
    (B&W line drawing, orthographic, no shading, etc.). The style wrapper
    has a {council_content} placeholder where the council's specific
    design description is injected.

  LAYER 2 — COUNCIL CONTENT:
    The council (chairman) writes a precise, element-by-element content
    description for each view during the deliberation. This content is
    injected into the style wrapper at generation time.

  FALLBACK — FIXED TEMPLATES:
    If the council did not write a generation_prompt for a view (e.g., on
    older projects or on views added by the generator), the fixed template
    (which uses the DSD description directly) is used instead.

The separation of concerns means:
  - Style wrappers enforce VISUAL CORRECTNESS (B&W, flat 2D, etc.)
  - Council content provides DESIGN ACCURACY (what exactly to draw)
"""

# ---------------------------------------------------------------------------
# STYLE WRAPPERS — enforce visual style, inject council content
# ---------------------------------------------------------------------------

FLOOR_PLAN_STYLE_WRAPPER = """\
Generate a FLAT 2D TOP-DOWN VIEW of the design — the view you see when looking \
straight down at the object from directly above. Camera points straight down, \
zero tilt, zero angle.

This is NOT necessarily an "architectural floor plan" in the traditional sense. \
Adapt to whatever the design is:
- A cabinet, closet, wardrobe, or shelving unit: draw its rectangular footprint \
  from above — outer boundary, interior compartments/divisions as seen from the top, \
  door openings as gaps, any visible structure.
- A kitchen layout: draw the counters, island, appliances, and work zones from above.
- A room or full-floor layout: draw walls, doors, windows, and interior layout.
Do NOT force architectural floor plan conventions onto furniture or a simple unit. \
Draw what a camera pointing straight down would actually see for that specific object.

WHAT TO DRAW (exact content from expert council analysis):
{council_content}

VISUAL REQUIREMENTS — ZERO TOLERANCE:
- Background: pure white (#FFFFFF). Nothing else.
- Lines: pure black (#000000). No gray, no color, no gradient anywhere.
- Outer boundary: thick solid black lines.
- Interior divisions (shelves, walls, counters seen from above): thin black lines.
- Door openings: a straight GAP in the boundary + a short text label ("DOOR").
  NO swing arcs. NO quarter-circle curves. NO curves anywhere in the drawing.
- NO shading. NO shadows. NO gradients. NO fills. All surfaces are white.
- NO 3D effects. NO perspective. NO isometric. NO depth cues of any kind.
- The projection is perfectly orthographic from directly above.

MEASUREMENTS:
ONLY draw dimension lines if the council content above contains a specific \
stated measurement with a number (e.g., "120cm", "6 feet"). \
If no explicit numbers are given — draw ZERO measurements, ZERO dimension lines, \
ZERO numbers of any kind.

LABEL: A short label at the bottom center identifying the view \
(e.g., "TOP VIEW", "FLOOR PLAN", "PLAN VIEW" — whichever fits the object).

WRONG outputs: anything with depth, shadows, a perspective angle, 3D form, or \
gray fills. This must look like a flat line drawing viewed from directly above.\
"""

FRONT_ELEVATION_STYLE_WRAPPER = """\
Generate a PURE 2D ARCHITECTURAL FRONT ELEVATION. This is a flat frontal \
diagram — like a printed AutoCAD elevation view or a hand-drafted architectural \
elevation. NOT a 3D render. NOT a perspective drawing. \
A flat 2D diagram with black lines on white paper showing the front face only.

Think of it as: you stand directly in front of the object at infinite distance \
and look straight at the face. The face appears as a perfectly flat rectangle. \
You see NO sides. NO top. NO depth. ONLY the flat front face.

WHAT TO DRAW (exact content from expert council analysis):
{council_content}

VISUAL REQUIREMENTS — ZERO TOLERANCE:
- Background: pure white (#FFFFFF). Nothing else.
- Lines: pure black (#000000). No gray, no color, no gradient anywhere.
- Outer silhouette: thick solid black lines defining the full width and height.
- Panel/door/drawer divisions: medium black lines on the face.
- Hardware (handles, knobs): simple small symbols — circles or rectangles.
- NO shading. NO shadows. NO gradients. NO fills. Every surface is white.
- NO 3D effects. NO perspective. NO vanishing points. NO depth.
- NO visible side faces. NO visible top surface. ONLY the flat front face.
- A thin horizontal ground line at the base of the drawing.

MEASUREMENTS:
ONLY draw dimension lines if the council content above contains a specific \
stated measurement with a number (e.g., "150cm wide", "2 meters tall"). \
If the council content uses words like "estimated", "approximately", "typical", \
or describes proportions without numbers — draw ZERO measurements, ZERO numbers.

LABEL: Use the view label from the council content if stated, otherwise \
"FRONT ELEVATION", centered at the bottom.

WRONG outputs: anything with visible sides, depth, shadows, 3D form, or \
perspective. If it looks like a render — it is wrong.\
"""

SIDE_ELEVATION_STYLE_WRAPPER = """\
Generate a BLACK AND WHITE 2D ARCHITECTURAL SIDE ELEVATION — a technical line \
drawing of the side profile, flat and orthographic, as drawn by an architect.

DESIGN TO DRAW (from expert council analysis):
{council_content}

VISUAL STYLE — ABSOLUTE REQUIREMENTS:
- Background: pure white
- Lines: pure black — no gray, no color, no shading
- Thick lines: outer silhouette
- Thin lines: interior details, side-mounted elements
- NO 3D, NO perspective, NO depth cues
- View: exactly perpendicular to the side face
- You see ONLY the side profile — no front face, no rear face
- Ground line at the base

MEASUREMENTS: Only if explicitly stated in the design content above.

LABEL: "SIDE ELEVATION" or the view label from design content, at the bottom.\
"""

REAR_ELEVATION_STYLE_WRAPPER = """\
Generate a BLACK AND WHITE 2D ARCHITECTURAL REAR ELEVATION — a technical line \
drawing of the rear face, flat and orthographic.

DESIGN TO DRAW (from expert council analysis):
{council_content}

VISUAL STYLE — ABSOLUTE REQUIREMENTS:
- Background: pure white
- Lines: pure black only
- Thick lines: outer silhouette
- Thin lines: details
- NO 3D, NO shading, NO perspective
- View: perpendicular to the rear face
- Ground line at the base

MEASUREMENTS: Only if explicitly stated in the design content above.

LABEL: "REAR ELEVATION" or the label from design content.\
"""

PERSPECTIVE_3D_STYLE_WRAPPER = """\
Generate a PHOTOREALISTIC 3D PERSPECTIVE RENDER — a product visualization \
showing the design from a 3/4 front angle with natural lighting.

DESIGN TO DRAW (from expert council analysis):
{council_content}

VISUAL REQUIREMENTS:
- Full 3D perspective with depth, shadows, and lighting
- Camera: slightly above eye level, 30-45 degrees from the front-left corner
- Three faces visible: front (dominant), side, and top (partial)
- Photorealistic materials — show grain, sheen, and texture accurately
- Soft natural lighting (studio softbox or daylight simulation)
- Clean, minimal background (studio gray or simple neutral room)
- No technical lines or dimension markers — this is a visualization\
"""

REALISTIC_RENDER_STYLE_WRAPPER = """\
Generate a PHOTOREALISTIC LIFESTYLE PHOTOGRAPH — a magazine-quality interior \
image showing the design in a real-world environment.

DESIGN TO DRAW (from expert council analysis):
{council_content}

PHOTOGRAPHIC REQUIREMENTS:
- The design is the clear focal point in a fully realized interior setting
- Natural, warm lighting from realistic sources (windows, lamps)
- Contextual styling: books, plants, objects, props appropriate to the space
- Camera at eye level or slightly below — human perspective
- Hyper-realistic materials: visible grain for wood, correct sheen for metal
- The environment should feel lived-in and inviting
- Magazine-quality composition and atmosphere\
"""

# ---------------------------------------------------------------------------
# Style wrapper mapping
# ---------------------------------------------------------------------------

VIEW_STYLE_WRAPPERS = {
    "floor_plan": FLOOR_PLAN_STYLE_WRAPPER,
    "front_elevation": FRONT_ELEVATION_STYLE_WRAPPER,
    "side_elevation": SIDE_ELEVATION_STYLE_WRAPPER,
    "rear_elevation": REAR_ELEVATION_STYLE_WRAPPER,
    "perspective_3d_front": PERSPECTIVE_3D_STYLE_WRAPPER,
    "perspective_3d_angle": PERSPECTIVE_3D_STYLE_WRAPPER,
    "realistic_render": REALISTIC_RENDER_STYLE_WRAPPER,
}


def build_prompt_from_council(view_type: str, council_content: str) -> str:
    """
    Build a generation prompt using the council's content + the style wrapper.

    The council wrote council_content during deliberation — it is a precise,
    element-by-element description of exactly what to draw for this view.
    The style wrapper enforces the correct visual presentation.

    Args:
        view_type: One of the ViewType enum values
        council_content: The generation_prompt written by the chairman

    Returns:
        Complete prompt ready for the image generation model
    """
    wrapper = VIEW_STYLE_WRAPPERS.get(view_type)
    if wrapper is None:
        raise ValueError(f"Unknown view type: {view_type}")
    return wrapper.format(council_content=council_content)


# ---------------------------------------------------------------------------
# FALLBACK FIXED TEMPLATES
# Used when the council did not write a generation_prompt for a view.
# ---------------------------------------------------------------------------

BASE_GENERATION_INSTRUCTION = """\
Generate a professional architectural image based on the design specification \
below. Follow the style and format rules exactly.

DESIGN SPECIFICATION:
{dsd_description}

"""

# ---------------------------------------------------------------------------
# View-Specific Prompts
# ---------------------------------------------------------------------------

FLOOR_PLAN_PROMPT = BASE_GENERATION_INSTRUCTION + """
VIEW TYPE: TOP-DOWN VIEW (flat 2D overhead drawing)

GENERATE: A flat 2D top-down view of the design — the view you see when you \
look straight down at the object from directly above. Camera points 90 degrees \
straight down, zero tilt, zero angle.

THIS IS NOT STRICTLY AN "ARCHITECTURAL FLOOR PLAN":
Adapt to whatever the design actually is:
- A cabinet, wardrobe, closet, or shelving unit: draw its rectangular footprint \
  from above — outer walls, interior compartments/dividers, door openings as gaps.
- A kitchen layout: counters, island, appliances, work zones seen from above.
- A room or full-floor layout: walls, doors, windows, and floor layout.
Do NOT impose formal architectural floor plan conventions on furniture or a \
simple unit. Draw what a camera pointing straight down would actually show.

IMAGE STYLE — ABSOLUTE REQUIREMENTS:
1. BACKGROUND: Pure white. Nothing else.
2. LINES: Pure black only. No gray, no color, no fills, no gradients.
3. LINE WEIGHTS:
   - Thick solid black lines for outer boundary
   - Thin lines for interior divisions, shelves, counters as seen from above
4. NO SHADING. NO SHADOWS. NO FILLS. NO HATCHING. All surfaces white.
5. NO 3D EFFECTS. No perspective. No isometric. No depth. Completely flat.

VIEWPOINT:
- Camera looking STRAIGHT DOWN — 90 degrees perpendicular to the base
- No tilt, no angle whatsoever
- Pure 2D orthographic projection

WHAT TO DRAW:
- Outer boundary: thick black lines
- Interior divisions or walls: thinner black lines
- Doors: a straight gap at the door position + short text label "DOOR". NO arcs. NO curves.
- Windows (if applicable): three thin parallel lines across the opening
- Interior elements: simple outlines as seen from directly above

MEASUREMENTS — CHECK THE SPECIFICATION:
- IF specific measurements are stated with numbers (e.g., "120cm", "6 feet"): \
  ADD dimension lines with those exact values.
- IF no explicit numbers given, or notes say "estimated"/"approximate": \
  Draw ZERO measurements, ZERO numbers, ZERO dimension lines.

LABEL: A short label at the bottom center (e.g., "TOP VIEW", "PLAN VIEW", \
or "FLOOR PLAN" — whichever fits the object type).

WHAT MUST NOT APPEAR:
- 3D perspective, depth, or volume of any kind
- Isometric or angled view
- Shading, shadows, gradients, gray fills
- Anything that looks rendered instead of flat-drafted

FINAL CHECK: Does this look like a flat line drawing on white paper viewed \
straight from above? If there is ANY depth, shadow, angle, or gray — it is wrong."""

FRONT_ELEVATION_PROMPT = BASE_GENERATION_INSTRUCTION + """
VIEW TYPE: FRONT ELEVATION — 2D ARCHITECTURAL FRONTAL DRAWING

GENERATE: A professional architectural front elevation — exactly as drawn by \
architects and interior designers: clean black lines on a pure white background, \
showing the front face completely flat. Think of a technical pen drawing of the \
front face on white drafting paper.

WHAT THIS IS:
A front elevation shows the front face of the design as a perfectly flat 2D \
projection — as if you stood directly in front of it at infinite distance with \
a perfectly centered telephoto lens, but drawn as a line drawing, not a photo. \
You see ONLY the front face. No sides. No top. No depth. Just the flat face.

IMAGE STYLE — ABSOLUTE REQUIREMENTS:
1. BACKGROUND: Pure white. Nothing else.
2. LINES: Pure black only. No color. No gray. No gradients.
3. LINE WEIGHTS:
   - Thick solid black lines for the outer silhouette/boundary
   - Medium lines for major face divisions (panel lines, door/drawer edges)
   - Thin lines for details (handles, hinges, internal divisions)
   - Very thin lines for dimension lines and annotations
4. NO SHADING WHATSOEVER: No shadows. No depth gradients. No material shading. \
   Every surface is white — differentiated only by lines, not by fill.
5. NO 3D EFFECTS: No vanishing points. No perspective. No foreshortening. \
   The front face is a perfectly flat 2D plane.
6. A GROUND LINE: Single thin horizontal line at the base showing floor level.

VIEWPOINT:
- Looking DIRECTLY and PERPENDICULARLY at the front face
- No tilt up or down. No angle left or right. Perfectly centered.
- The front face fills the frame as a flat rectangle
- You see NO side faces (at most a thin edge line at the corners)
- You see NO top surface at all

WHAT TO DRAW:
- Outer boundary: thick black rectangle/silhouette for full width and height
- Panel divisions: medium lines showing where panels, doors, or drawers meet
- Hardware: simple symbolic marks — small circles for knobs, small rectangles for pulls
- Shelf lines: horizontal thin lines where shelf divisions are visible on the face
- Legs or feet: rectangular outlines at the base if present
- Frame: any visible frame or trim lines
- Ground line at the bottom
- DO NOT draw materials or textures — lines only

MEASUREMENTS — CHECK THE SPECIFICATION:
Look at the DESIGN SPECIFICATION at the top of this prompt. Find the \
"Dimensions:" section.
- IF specific measurements are listed (e.g., Width: 120cm, Height: 200cm) \
  AND the notes do NOT say "estimated" or "not specified": \
  ADD dimension lines — height dimension on the left side, width along the \
  bottom. Use standard notation (arrows or tick marks + number).
- IF no Dimensions appear, OR if the notes say "estimated", "APPROXIMATE", \
  or "not specified by client": \
  Draw NO measurements, NO numbers, NO dimension lines. Zero numbers.

LABELS: Simple text label at the bottom center identifying this elevation \
(use the view label provided in the SPECIFIC VIEW INSTRUCTIONS below if given, \
otherwise "FRONT ELEVATION").

WHAT MUST NOT APPEAR — ANY OF THESE INVALIDATES THE OUTPUT:
- Any 3D perspective, vanishing points, or depth of any kind
- Any visible side walls or top surface
- Any shading, shadows, or depth gradients
- Any photorealistic material rendering
- Any color (pure black and white only)
- Any isometric or axonometric view
- Anything that looks like a render instead of a drafted drawing

FINAL CHECK: Does this look like a flat 2D elevation line drawing that an \
architect drew on white paper? If you can see ANY sides, ANY depth, ANY \
shading — it is wrong."""

SIDE_ELEVATION_PROMPT = BASE_GENERATION_INSTRUCTION + """
VIEW TYPE: SIDE ELEVATION — STRICT 2D ORTHOGRAPHIC SIDE VIEW

YOU MUST GENERATE:
A professional technical elevation drawing showing the design viewed DIRECTLY FROM THE SIDE.
This is a CONSTRUCTION DOCUMENT showing exactly what the side profile looks like.

ABSOLUTE REQUIREMENTS — ANY DEVIATION MAKES THE OUTPUT INVALID:

1. CAMERA ANGLE (MANDATORY):
   - Camera must be positioned EXACTLY perpendicular to the side face (90 degrees from front)
   - NO tilt, NO perspective, NO angled view
   - View direction: straight from the side, parallel projection
   - The side face must be shown perfectly flat

2. DIMENSIONALITY (CRITICAL):
   - STRICTLY 2D — FLAT orthographic projection
   - NO 3D effects: NO perspective, NO vanishing points, NO foreshortening
   - NO isometric, NO 3/4 view, NO angled perspective
   - The image must show the side face as a flat 2D plane

3. VISUAL STYLE (ARCHITECTURAL STANDARD):
   - Background: pure white or very light gray
   - Lines: crisp black lines defining all edges
   - Line weights: thick lines for outer轮廓, thinner for interior
   - Include a ground line at the bottom

4. CONTENT TO INCLUDE:
   - Complete side profile轮廓
   - All visible depth dimensions and thicknesses
   - Side-mounted elements: handles, pulls, side panels
   - Material thickness indications
   - Shelf depths visible from side
   - Any side-mounted hardware or features

5. WHAT THIS SHOWS (vs Front Elevation):
   - Side elevation shows DEPTH (how deep the piece is)
   - Front elevation shows WIDTH (how wide the face is)
   - This view reveals the side thickness, side panels, side-mounted elements

6. PROHIBITED ELEMENTS (DO NOT INCLUDE):
   - 3D perspective
   - Front face details (this is side view)
   - Vanishing points
   - Isometric views
   - Photorealistic rendering
   - Background environment

OUTPUT FORMAT:
- Clean technical drawing
- Black lines on white
- Professional architectural elevation style

REMEMBER: This shows the SIDE PROFILE — what you'd see looking directly at the \
side of the object. Must be flat 2D, no perspective, no front-face details."""

REAR_ELEVATION_PROMPT = BASE_GENERATION_INSTRUCTION + """
VIEW TYPE: REAR ELEVATION — STRICT 2D ORTHOGRAPHIC REAR VIEW

YOU MUST GENERATE:
A professional technical elevation drawing showing the design viewed DIRECTLY FROM THE BACK.
This is a CONSTRUCTION DOCUMENT showing exactly what the rear face looks like.

ABSOLUTE REQUIREMENTS:

1. CAMERA ANGLE:
   - Camera EXACTLY perpendicular to the rear face
   - NO tilt, NO perspective — strict parallel projection
   - View from behind the object, looking straight at the back

2. DIMENSIONALITY:
   - STRICTLY 2D orthographic
   - NO 3D effects, NO shading, NO perspective
   - Flat technical drawing only

3. CONTENT:
   - Complete rear face轮廓
   - All rear-mounted elements: back panels, rear feet, rear hardware
   - Material indications for back surface
   - Ground line at bottom

4. STYLE:
   - Clean technical lines
   - Black and white
   - Architectural elevation conventions

PROHIBITED:
   - 3D perspective
   - Front or side details visible
   - Photorealistic rendering

REMEMBER: This is the REAR VIEW — what the back of the object looks like. \
Flat 2D, orthographic, no perspective."""

PERSPECTIVE_3D_FRONT_PROMPT = BASE_GENERATION_INSTRUCTION + """
VIEW TYPE: 3D PERSPECTIVE RENDER — FRONT ANGLE VIEW

YOU MUST GENERATE:
A photorealistic 3D rendering showing the design from a front angle.
This is a PRESENTATION IMAGE, not a technical drawing.

ABSOLUTE REQUIREMENTS:

1. CAMERA POSITION (MANDATORY):
   - Position: slightly above eye level, looking down at approximately 15-20 degrees
   - Angle: directly centered on the front face
   - Distance: close enough to show details, far enough to see full form
   - NO extreme wide-angle distortion
   - Lens: normal perspective (not fish-eye, not telephoto)

2. DIMENSIONALITY (CRITICAL — MUST BE 3D):
   - This MUST be a 3D perspective render with depth
   - Show the front face as the main visible surface
   - Show slight visibility of top surface (due to camera height)
   - Show slight visibility of side edges (left/right contours)
   - Clear depth cues: shadows, lighting gradients, occlusion

3. LIGHTING (PHOTOREALISTIC):
   - Soft, natural lighting (simulating daylight or studio softbox)
   - Main light from upper left or upper right (creates dimension)
   - Subtle fill light to reduce harsh shadows
   - Soft shadows cast onto the floor/ground plane
   - NO flat lighting, NO harsh direct flash

4. MATERIALS (MUST LOOK REAL):
   - Wood: visible grain, subtle reflectivity, natural variation
   - Metal: appropriate sheen (matte or polished as specified)
   - Paint: subtle surface variation, not perfectly flat
   - Glass: transparency, reflections, refraction if present
   - Colors must match the design specification EXACTLY

5. ENVIRONMENT:
   - Simple, clean background (studio gray/white or minimal room)
   - Ground plane/floor visible (shadows cast upon it)
   - NO distracting background elements
   - The design is the sole focus

6. RENDER QUALITY:
   - High detail: show joinery, edge details, hardware
   - Appropriate depth of field (slight blur on extreme edges acceptable)
   - Clean, professional appearance
   - No wireframes, no technical lines, no dimension markers

7. PROHIBITED:
   - Orthographic/flat 2D view (this must be 3D perspective)
   - Isometric view (must have perspective depth)
   - Multiple objects cluttering the scene
   - Extreme camera angles
   - Cartoon or stylized rendering (must be photorealistic)

OUTPUT:
A single photorealistic image that looks like a professional product \
photograph or architectural visualization render."""

PERSPECTIVE_3D_ANGLE_PROMPT = BASE_GENERATION_INSTRUCTION + """
VIEW TYPE: 3D PERSPECTIVE RENDER — THREE-QUARTER (45°) ANGLE VIEW

YOU MUST GENERATE:
A photorealistic 3D rendering showing the design from a 45-degree corner angle.
This is a PRESENTATION IMAGE showcasing the 3D form from a standard 3/4 view.

ABSOLUTE REQUIREMENTS:

1. CAMERA POSITION (MANDATORY):
   - Angle: approximately 45 degrees from the front-left corner (standard 3/4 view)
   - Height: slightly above eye level (15-20 degrees above horizontal)
   - Result: THREE faces visible — front face (largest), left side face, and top surface
   - Distance: show the entire object clearly with some surrounding space
   - NO extreme distortion, NO fisheye lens

2. DIMENSIONALITY (MUST BE 3D PERSPECTIVE):
   - Clear perspective depth with vanishing points
   - Front face visible as the primary surface (but angled, not flat-on)
   - Side face visible showing depth/thickness
   - Top surface visible due to camera height
   - Strong depth cues through lighting and shading

3. LIGHTING:
   - Soft, natural lighting creating form definition
   - Main light from upper left (typical studio setup)
   - Soft shadows defining the form's silhouette
   - Gentle gradients on surfaces showing curvature/form
   - Contact shadows where object meets ground

4. MATERIALS (PHOTOREALISTIC):
   - All materials rendered realistically
   - Surface textures visible and accurate
   - Reflective properties correct (matte vs. glossy)
   - Colors match specification exactly

5. COMPOSITION:
   - Object is the clear focal point
   - Clean, minimal background (studio or simple room)
   - Ground plane visible for shadow casting
   - Professional framing with appropriate margins

6. PROHIBITED:
   - Flat orthographic view (must be perspective)
   - Isometric (no parallel lines — must show perspective convergence)
   - More than three faces visible (no rear view peeking)
   - Cluttered backgrounds
   - Non-photorealistic rendering styles

OUTPUT:
A professional 3/4 view product render showing the design from the classic \
45-degree angle — the standard view used in product catalogs and architectural \
visualizations to showcase 3D form."""

# ---------------------------------------------------------------------------
# Realistic Lifestyle Render
# ---------------------------------------------------------------------------

REALISTIC_RENDER_PROMPT = BASE_GENERATION_INSTRUCTION + """
VIEW TYPE: PHOTOREALISTIC LIFESTYLE RENDER — ENVIRONMENTAL CONTEXT

YOU MUST GENERATE:
A stunning, photorealistic lifestyle image showing the design in a realistic \
interior environment, as if photographed for a high-end design magazine.

ABSOLUTE REQUIREMENTS:

1. SUBJECT (THE DESIGN):
   - Must be the CLEAR FOCAL POINT of the image
   - Sharp focus on the design (slight depth of field is acceptable)
   - Positioned naturally within the room/scene
   - All materials, colors, and finishes must match the specification EXACTLY
   - Show the design at proper real-world scale

2. ENVIRONMENT (CONTEXT):
   - Fully realized interior setting appropriate for the design type:
     * Furniture piece: placed in appropriate room (living room, bedroom, office)
     * Kitchen element: in a kitchen with countertops, backsplash, appliances
     * Room design: show the complete room with all specified elements
   - Realistic architecture: walls, floors, ceilings as appropriate
   - Natural lighting sources: windows, lamps, ambient room light

3. STYLING (LIFESTYLE ELEMENTS):
   Add appropriate contextual items that bring the scene to life:
   
   For Storage (shelves, cabinets, wardrobes):
   - Books (varied sizes, some upright, some stacked)
   - Plants (potted, realistic varieties)
   - Decorative objects: vases, bowls, candles, sculptures
   - Personal items: framed photos, small boxes, collectibles
   - For wardrobes: show slightly ajar with organized clothing visible
   
   For Work Surfaces (desks, tables):
   - Task lighting: a desk lamp
   - Work items: notebook, pen, laptop/tablet
   - Personal touches: coffee cup, small plant, phone
   
   For Seating:
   - Throw pillows and blankets in complementary colors
   - Side table nearby with a lamp or drink
   
   For Kitchen/Bath:
   - Functional items: towels, soap dispensers, cutting boards
   - Fresh elements: fruit bowl, herbs, flowers
   - Appliances and fixtures in background

4. LIGHTING (PHOTOGRAPHIC):
   - Natural, warm lighting (golden hour sunlight or soft daylight)
   - Light should come from realistic sources (windows, lamps)
   - Soft shadows creating depth and atmosphere
   - Avoid harsh, flat, or artificial-looking lighting
   - The scene should feel inviting and lived-in

5. CAMERA (PHOTOGRAPHIC COMPOSITION):
   - Angle: slightly below or at eye level (as a person would view it)
   - NO extreme high angles, NO bird's eye views
   - Lens: normal to slightly wide (not fisheye)
   - Composition: rule of thirds, design as primary subject
   - Include foreground, middle ground, and background elements

6. MATERIALS (HYPER-REALISTIC):
   - Wood: visible grain, appropriate sheen, natural color variation
   - Fabrics: visible weave, soft shadows in folds
   - Metal: correct reflectivity (brushed, polished, or matte as specified)
   - Stone/tile: texture and pattern
   - Glass: transparency and reflection
   - All materials should look touchable and real

7. ATMOSPHERE:
   - The image should evoke a specific mood (calm, energetic, cozy, professional)
   - Warm color temperature (slightly warm, not cold/blue)
   - Slight imperfections that make it feel real (not sterile CG)

8. PROHIBITED:
   - Flat or harsh lighting
   - Empty, sterile environments without context
   - Cartoon or stylized rendering
   - Technical lines, dimensions, or annotations (this is a photo, not a drawing)
   - Isometric or orthographic views (must be photographic perspective)
   - Floating object without environment

OUTPUT:
A magazine-quality lifestyle photograph that looks like it was shot by a \
professional interior design photographer. The viewer should want to \
live in or use this space."""

# ---------------------------------------------------------------------------
# Fallback Prompt Mapping (used when council did not write a generation_prompt)
# ---------------------------------------------------------------------------

VIEW_PROMPTS = {
    "floor_plan": FLOOR_PLAN_PROMPT,
    "front_elevation": FRONT_ELEVATION_PROMPT,
    "side_elevation": SIDE_ELEVATION_PROMPT,
    "rear_elevation": REAR_ELEVATION_PROMPT,
    "perspective_3d_front": PERSPECTIVE_3D_FRONT_PROMPT,
    "perspective_3d_angle": PERSPECTIVE_3D_ANGLE_PROMPT,
    "realistic_render": REALISTIC_RENDER_PROMPT,
}


def get_generation_prompt(view_type: str, dsd_description: str) -> str:
    """
    FALLBACK: Get a generation prompt using the fixed template + DSD description.

    Used when the council did not write a generation_prompt for this view
    (e.g., older projects, manually added views, backward compatibility).

    For new projects where the council wrote generation_prompts, use
    build_prompt_from_council() instead.
    """
    template = VIEW_PROMPTS.get(view_type)
    if template is None:
        raise ValueError(f"Unknown view type: {view_type}")
    return template.format(dsd_description=dsd_description)
