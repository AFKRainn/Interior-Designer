"""
Spec v2 — source of truth for build 2.

The plan and every elevation are renderings of this document. If a number is
wrong on screen, the spec is wrong, not the picture.

Build 1's flat bay/module model is gone (Phase 7 cutover). Specs saved by it
are converted on read by app/models/migrate.py.

Invariants I1-I8 are plan.txt section 5.3. The sizing rule (I3) is the only
one that matters for layout, and it applies identically at every depth:

    fixed `size_cm` siblings are laid out first; `flex` siblings divide the
    remainder. A tree therefore always fits its parent exactly.

Overflow is not caught here. It is unrepresentable.
"""
from __future__ import annotations

from enum import Enum
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, Field, ValidationError, model_validator

# Every fixed size in the document is human- or model-authored and carries
# the same kind of slop, so one tolerance serves every level (progress D8).
FIT_TOLERANCE_CM = 1.0
MIN_SIZE_CM = 1.0

DEFAULT_DEPTH_CM = 60.0
DEFAULT_HEIGHT_CM = 220.0


class SplitAxis(str, Enum):
    ROWS = "rows"
    COLS = "cols"


class FrontType(str, Enum):
    DOOR = "door"
    DRAWER = "drawer"
    OPEN = "open"
    GLASS = "glass"
    APPLIANCE = "appliance"
    PANEL = "panel"
    FALSE_FRONT = "false_front"


class Hinge(str, Enum):
    LEFT = "left"
    RIGHT = "right"
    TOP = "top"
    BOTTOM = "bottom"
    NONE = "none"


class CornerMode(str, Enum):
    """Which wall gives up its depth where two runs meet (plan 7.2)."""

    YIELD = "yield"
    TAKE = "take"


class SpecError(ValueError):
    """A spec or op violated an invariant. The message is user-facing."""


class Front(BaseModel):
    """What a leaf opening shows to the room.

    `type` and `hinge` are closed enums because the solver reads them and
    draws different geometry. `handle` is a free string because it only ever
    gets labelled, and hardware naming is endless.
    """

    type: FrontType
    hinge: Hinge = Hinge.NONE
    handle: str = "none"
    count: int = 1  # input shorthand only; normalised to 1 (plan 5.1)


class Opening(BaseModel):
    """A node in a bay's division tree.

    Leaf  -> `front` set, `split` None, no children.
    Split -> `split` set, >= 2 children, no front.

    Sizing is along the PARENT's split axis, which is why the field is
    `size_cm` and never `width`/`height` (progress D3).

    ORDER IS DRAWING ORDER, and every renderer depends on it:
      rows -> children run TOP to BOTTOM
      cols -> children run LEFT to RIGHT
    """

    id: str
    label: str = ""
    size_cm: Optional[float] = None
    flex: Optional[float] = None
    split: Optional[SplitAxis] = None
    children: list[Opening] = Field(default_factory=list)
    front: Optional[Front] = None

    @model_validator(mode="after")
    def _normalise_and_check(self) -> Opening:
        self._expand_front_count()

        if self.size_cm is not None and self.flex is not None:
            raise SpecError(
                f"{self.id}: set size_cm or flex, not both "
                f"(size_cm={self.size_cm}, flex={self.flex})"
            )
        if self.size_cm is not None and self.size_cm <= 0:
            raise SpecError(f"{self.id}: size_cm must be positive")
        if self.flex is not None and self.flex <= 0:
            raise SpecError(f"{self.id}: flex must be positive")

        # I5 — a node is a leaf with a front, or a split with children.
        if self.split is None:
            if self.children:
                raise SpecError(f"{self.id}: children require a split axis")
            if self.front is None:
                raise SpecError(
                    f"{self.id}: leaf needs a front "
                    f"(use type 'open' for an undecided or open opening)"
                )
        else:
            if self.front is not None:
                raise SpecError(
                    f"{self.id}: a split node cannot carry a front; "
                    f"the front belongs to its leaves"
                )
            if len(self.children) < 2:
                raise SpecError(
                    f"{self.id}: a {self.split.value} split needs at least "
                    f"2 children, got {len(self.children)}"
                )

        # I4 — ids unique among siblings; the path is the global address.
        ids = [child.id for child in self.children]
        duplicates = {i for i in ids if ids.count(i) > 1}
        if duplicates:
            raise SpecError(
                f"{self.id}: child ids must be unique among siblings, "
                f"repeated: {sorted(duplicates)}"
            )
        return self

    def _expand_front_count(self) -> None:
        """count > 1 is input shorthand. Expand it into real nodes (D5).

        A stack is always vertical, so it expands into a rows split of equal
        flex leaves. Each one becomes individually addressable, which is what
        makes "make the top drawer taller" resolvable.
        """
        if self.front is None or self.front.count <= 1:
            if self.front is not None:
                self.front.count = 1
            return

        count = self.front.count
        base = self.front.model_copy(update={"count": 1})
        kind = base.type.value
        self.children = [
            Opening(id=f"{kind}-{i + 1}", flex=1.0, front=base.model_copy())
            for i in range(count)
        ]
        self.split = SplitAxis.ROWS
        self.front = None

    # -- tree helpers -----------------------------------------------------

    def is_leaf(self) -> bool:
        return self.split is None

    def walk(self, prefix: str = "") -> list[tuple[str, Opening]]:
        """Every node beneath and including self, as (path, node)."""
        here = f"{prefix}/{self.id}" if prefix else self.id
        found = [(here, self)]
        for child in self.children:
            found.extend(child.walk(here))
        return found


class CorniceSpec(BaseModel):
    type: str = "straight"
    height: float = 0.0


class PlinthSpec(BaseModel):
    type: str = "recessed"
    height: float = 0.0


class SideColumnsSpec(BaseModel):
    """Vertical trim at the ends of a run. Consumes width — it is not
    drawn on top of the bays the way build 1 drew it (progress D9)."""

    left_cm: float = 0.0
    right_cm: float = 0.0
    detail: str = "plain"


class CornerSpec(BaseModel):
    """Per-end corner resolution. None means a free end (plan 7.2)."""

    start: Optional[CornerMode] = None
    end: Optional[CornerMode] = None


class DesignWall(BaseModel):
    """The designed face of one wall."""

    id: str
    height: float = DEFAULT_HEIGHT_CM
    depth: float = DEFAULT_DEPTH_CM
    reveal_mm: float = 3.0
    cornice: CorniceSpec = Field(default_factory=CorniceSpec)
    plinth: PlinthSpec = Field(default_factory=PlinthSpec)
    side_columns: SideColumnsSpec = Field(default_factory=SideColumnsSpec)
    bays: list[Opening] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_bay_ids(self) -> DesignWall:
        ids = [bay.id for bay in self.bays]
        duplicates = {i for i in ids if ids.count(i) > 1}
        if duplicates:
            raise SpecError(
                f"{self.id}: bay ids must be unique, repeated: {sorted(duplicates)}"
            )
        return self

    def bay_ids(self) -> list[str]:
        return [bay.id for bay in self.bays]

    def inner_height(self) -> float:
        """Vertical budget for a bay: carcass minus the trim bands."""
        return max(
            0.0,
            self.height - max(0.0, self.cornice.height) - max(0.0, self.plinth.height),
        )


class LayoutWall(BaseModel):
    """Topology of one wall: length, neighbours, order, corner resolution."""

    id: str
    label: str = ""
    length: float
    adjacent_to: list[str] = Field(default_factory=list)
    faces: list[str] = Field(default_factory=list)
    sequence: int = 0
    corner: CornerSpec = Field(default_factory=CornerSpec)


class LayoutType(str, Enum):
    STRAIGHT = "straight"
    L = "L"
    U = "U"
    GALLEY = "galley"
    CUSTOM = "custom"


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


class Assumption(BaseModel):
    """A default the system chose because the client never said (I8)."""

    field: str
    value_cm: Optional[float] = None
    rationale: str = ""


def distribute(children: list[Opening], extent: float) -> list[float]:
    """THE sizing rule. Fixed siblings first, flex divides the remainder.

    This formula is duplicated in the TypeScript solver (plan 7). The two
    implementations are pinned to the same golden vectors in
    tests/golden/distribute.json — change one, change both.
    """
    if not children:
        return []

    fixed_total = sum(c.size_cm for c in children if c.size_cm is not None)
    flex_kids = [c for c in children if c.size_cm is None]
    remainder = extent - fixed_total
    flex_total = sum((c.flex or 1.0) for c in flex_kids)

    sizes: list[float] = []
    for child in children:
        if child.size_cm is not None:
            sizes.append(round(child.size_cm, 4))
        else:
            share = (child.flex or 1.0) / flex_total if flex_total else 0.0
            sizes.append(round(max(0.0, remainder) * share, 4))
    return sizes


class Spec(BaseModel):
    project_id: str = Field(default_factory=lambda: str(uuid4()))
    version: int = 1
    units: str = "cm"
    name: str = ""
    layout: LayoutSpec
    walls: list[DesignWall] = Field(default_factory=list)
    materials: MaterialsSpec = Field(default_factory=MaterialsSpec)
    hardware: HardwareSpec = Field(default_factory=HardwareSpec)
    brief: str = ""
    assumptions: list[Assumption] = Field(default_factory=list)
    render_notes: str = ""

    # -- lookups ----------------------------------------------------------

    def layout_wall(self, wall_id: str) -> LayoutWall:
        for wall in self.layout.walls:
            if wall.id == wall_id:
                return wall
        raise SpecError(f"unknown wall {wall_id}")

    def design_wall(self, wall_id: str) -> DesignWall:
        for wall in self.walls:
            if wall.id == wall_id:
                return wall
        raise SpecError(f"unknown wall {wall_id}")

    def ordered_layout_walls(self) -> list[LayoutWall]:
        return sorted(self.layout.walls, key=lambda w: (w.sequence, w.id))

    def wall_ids(self) -> list[str]:
        return [wall.id for wall in self.ordered_layout_walls()]

    def is_adjacent(self, a: str, b: str) -> bool:
        return b in self.layout_wall(a).adjacent_to

    def is_facing(self, a: str, b: str) -> bool:
        return b in self.layout_wall(a).faces

    def can_share_camera(self, a: str, b: str) -> bool:
        if a == b or self.is_facing(a, b):
            return False
        return self.is_adjacent(a, b)

    # -- corners and extents (plan 7.2) -----------------------------------

    def neighbour_at(self, wall_id: str, end: str) -> Optional[LayoutWall]:
        """The adjacent wall at 'start' or 'end' of this run.

        The sequence chain defines direction: the previous wall in sequence
        sits at the start, the next one at the end. A closed cycle (four
        walls around a room) wraps, so the first wall's start neighbour is
        the last wall — otherwise that one corner could never be resolved.
        """
        ordered = self.ordered_layout_walls()
        ids = [w.id for w in ordered]
        if wall_id not in ids:
            raise SpecError(f"unknown wall {wall_id}")
        index = ids.index(wall_id)
        offset = -1 if end == "start" else 1
        neighbour_index = index + offset
        if neighbour_index < 0 or neighbour_index >= len(ordered):
            # wrap only when the chain actually closes into a ring
            wrapped = ordered[neighbour_index % len(ordered)]
            if len(ordered) < 3 or not self.is_adjacent(wall_id, wrapped.id):
                return None
            return wrapped
        neighbour = ordered[neighbour_index]
        if not self.is_adjacent(wall_id, neighbour.id):
            return None
        return neighbour

    def usable_length(self, wall_id: str) -> float:
        """Run length after corner resolution.

        Build 1 let two 60 cm runs occupy the same 60x60 cm corner twice and
        counted it in both bay sums (plan 3.4). Exactly one wall yields.
        """
        layout = self.layout_wall(wall_id)
        length = layout.length
        for end in ("start", "end"):
            mode = getattr(layout.corner, end)
            if mode is not CornerMode.YIELD:
                continue
            neighbour = self.neighbour_at(wall_id, end)
            if neighbour is None:
                raise SpecError(
                    f"{wall_id}: corner.{end} is 'yield' but no adjacent wall "
                    f"sits at that end"
                )
            length -= self.design_wall(neighbour.id).depth
        return length

    def bay_extent(self, wall_id: str) -> float:
        """Horizontal budget the bays divide: usable run minus side trim."""
        design = self.design_wall(wall_id)
        cols = design.side_columns
        return self.usable_length(wall_id) - cols.left_cm - cols.right_cm

    # -- validation -------------------------------------------------------

    @model_validator(mode="after")
    def _validate(self) -> Spec:
        self._check_graph()
        self._check_fit()
        return self

    def _check_graph(self) -> None:
        layout_ids = [w.id for w in self.layout.walls]
        design_ids = [w.id for w in self.walls]

        # A design with nothing in it is not a design. Without this the
        # editor renders a blank sheet and never says why.
        if not layout_ids:
            raise SpecError("a spec needs at least one wall")

        if len(layout_ids) != len(set(layout_ids)):
            raise SpecError("layout.walls ids must be unique")
        if len(design_ids) != len(set(design_ids)):
            raise SpecError("walls ids must be unique")
        # I1
        if set(layout_ids) != set(design_ids):
            raise SpecError(
                "layout.walls ids and walls ids must match. "
                f"layout={sorted(layout_ids)} walls={sorted(design_ids)}"
            )

        known = set(layout_ids)
        # I2
        for wall in self.layout.walls:
            for other in wall.adjacent_to:
                if other == wall.id:
                    raise SpecError(f"{wall.id} cannot be adjacent to itself")
                if other not in known:
                    raise SpecError(
                        f"{wall.id}.adjacent_to references unknown wall {other}"
                    )
                if wall.id not in self.layout_wall(other).adjacent_to:
                    raise SpecError(
                        f"adjacent_to must be symmetric: {wall.id} lists "
                        f"{other} but {other} does not list {wall.id}"
                    )
            for other in wall.faces:
                if other == wall.id:
                    raise SpecError(f"{wall.id} cannot face itself")
                if other not in known:
                    raise SpecError(
                        f"{wall.id}.faces references unknown wall {other}"
                    )
                if other in wall.adjacent_to:
                    raise SpecError(
                        f"{wall.id} cannot both face and be adjacent to {other}"
                    )
                if wall.id not in self.layout_wall(other).faces:
                    raise SpecError(
                        f"faces must be symmetric: {wall.id} lists {other} "
                        f"but {other} does not list {wall.id}"
                    )

    def _check_fit(self) -> None:
        """I3, at every depth, with one rule."""
        for design in self.walls:
            if not design.bays:
                continue
            extent = self.bay_extent(design.id)
            if extent <= 0:
                raise SpecError(
                    f"{design.id}: nothing left for bays — usable length "
                    f"{self.usable_length(design.id):.1f} cm minus side columns "
                    f"leaves {extent:.1f} cm"
                )
            widths = _check_group(design.bays, extent, design.id, SplitAxis.COLS)
            for bay, width in zip(design.bays, widths):
                _check_subtree(bay, width, design.inner_height(), design.id)


def _check_group(
    children: list[Opening],
    extent: float,
    where: str,
    axis: SplitAxis,
) -> list[float]:
    """The fit rule for one sibling group. Returns the resolved sizes."""
    fixed = [c for c in children if c.size_cm is not None]
    has_flex = len(fixed) != len(children)
    fixed_total = sum(c.size_cm for c in fixed)
    noun = "width" if axis is SplitAxis.COLS else "height"

    if fixed_total - extent > FIT_TOLERANCE_CM:
        raise SpecError(
            f"{where}: fixed {noun}s total {fixed_total:.1f} cm but only "
            f"{extent:.1f} cm is available "
            f"({', '.join(f'{c.id}={c.size_cm:.0f}' for c in fixed)})"
        )
    if not has_flex and abs(fixed_total - extent) > FIT_TOLERANCE_CM:
        raise SpecError(
            f"{where}: {noun}s total {fixed_total:.1f} cm but the opening is "
            f"{extent:.1f} cm. Either make one child flex or adjust a size "
            f"(tolerance {FIT_TOLERANCE_CM} cm)"
        )

    sizes = distribute(children, extent)
    # A flex child squeezed to nothing is never intended, and it would draw
    # as an invisible sliver rather than an error.
    for child, size in zip(children, sizes):
        if size < MIN_SIZE_CM:
            raise SpecError(
                f"{where}/{child.id}: resolves to {size:.1f} cm — nothing left "
                f"for it. The fixed siblings already use "
                f"{fixed_total:.1f} of {extent:.1f} cm."
            )
    return sizes


def _check_subtree(node: Opening, box_w: float, box_h: float, path: str) -> None:
    """Walk down, carrying the box each node actually occupies."""
    here = f"{path}/{node.id}"
    if node.is_leaf():
        return

    extent = box_h if node.split is SplitAxis.ROWS else box_w
    sizes = _check_group(node.children, extent, here, node.split)

    for child, size in zip(node.children, sizes):
        if node.split is SplitAxis.ROWS:
            _check_subtree(child, box_w, size, here)
        else:
            _check_subtree(child, size, box_h, here)


Opening.model_rebuild()


def build_spec(data: dict | Spec) -> Spec:
    """Validate a spec and fail with ONE readable sentence.

    Always use this instead of Spec.model_validate. Pydantic wraps validator
    errors in a ValidationError blob, and these messages are user-facing in
    two places that matter: the editor shows them when an op is rejected, and
    the spec-author repair loop feeds them straight back to the model
    (plan 10.2). A clean message is part of the contract.
    """
    if isinstance(data, Spec):
        data = data.model_dump(mode="json")
    try:
        return Spec.model_validate(data)
    except ValidationError as err:
        raise SpecError(explain(err)) from err


def explain(err: ValidationError) -> str:
    """Pull our own messages out of a pydantic ValidationError."""
    messages: list[str] = []
    for detail in err.errors():
        msg = str(detail.get("msg", "")).removeprefix("Value error, ").strip()
        if not msg:
            continue
        location = ".".join(str(part) for part in detail.get("loc", ()) if part != "__root__")
        if detail.get("type") != "value_error" and location:
            msg = f"{location}: {msg}"
        messages.append(msg)
    # dict.fromkeys keeps order while dropping the duplicates pydantic emits
    # when the same node fails at several nesting levels.
    return "; ".join(dict.fromkeys(messages)) or str(err)
