"""
Edit operations — the ONLY way a spec changes.

Build 1 edited by asking the model to "return the FULL updated spec JSON".
That allowed collateral drift, produced no diff, and gave the user nothing to
approve before it landed (plan 3.6). It is also why a wrong edit went
unnoticed for a whole session.

Here, both the UI and the edit agent emit the same named operations. An op
either applies cleanly and bumps the version, or it is rejected with a reason
and changes nothing. Geometry stays in code; the model only chooses the op
and its arguments (plan 2).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Literal, Optional, Union

from pydantic import BaseModel, Field, TypeAdapter

from app.models.paths import resolve
from app.models.spec import (
    CornerMode,
    Front,
    FrontType,
    Hinge,
    Opening,
    Spec,
    SpecError,
    SplitAxis,
    build_spec,
)


class OpError(ValueError):
    """An op was rejected. The message is shown to the user verbatim."""


# -- the catalogue --------------------------------------------------------


class SetSize(BaseModel):
    """Pin a node to a fixed extent along its parent's split axis."""

    kind: Literal["set_size"] = "set_size"
    path: str
    size_cm: float


class SetFlex(BaseModel):
    """Let a node share whatever the fixed siblings leave over."""

    kind: Literal["set_flex"] = "set_flex"
    path: str
    flex: float = 1.0


class SetLabel(BaseModel):
    kind: Literal["set_label"] = "set_label"
    path: str
    label: str


class Split(BaseModel):
    """Divide a leaf into rows or columns.

    This is the op that build 1 could not express (plan 3.1). Children
    inherit the leaf's front, so "split this door into two" yields two doors.
    """

    kind: Literal["split"] = "split"
    path: str
    axis: SplitAxis
    count: int = 2
    ratios: Optional[list[float]] = None


class Merge(BaseModel):
    """Collapse a split back into a single leaf."""

    kind: Literal["merge"] = "merge"
    path: str


class AddChild(BaseModel):
    """Add one more child to an existing split (a 4th drawer, say)."""

    kind: Literal["add_child"] = "add_child"
    path: str
    index: Optional[int] = None
    size_cm: Optional[float] = None
    flex: Optional[float] = None
    front_type: FrontType = FrontType.OPEN


class Delete(BaseModel):
    """Remove a node. If its parent is left with one child, the parent
    absorbs it rather than becoming an illegal one-child split."""

    kind: Literal["delete"] = "delete"
    path: str


class SetFront(BaseModel):
    """Change what a leaf shows. count > 1 expands into a stack (D5)."""

    kind: Literal["set_front"] = "set_front"
    path: str
    type: FrontType
    hinge: Optional[Hinge] = None
    handle: Optional[str] = None
    count: int = 1


class InsertBay(BaseModel):
    kind: Literal["insert_bay"] = "insert_bay"
    wall_id: str
    index: Optional[int] = None
    size_cm: Optional[float] = None
    flex: Optional[float] = None
    label: str = ""
    front_type: FrontType = FrontType.OPEN


class SetWall(BaseModel):
    """Envelope and trim. Only the fields given are touched."""

    kind: Literal["set_wall"] = "set_wall"
    wall_id: str
    length: Optional[float] = None
    height: Optional[float] = None
    depth: Optional[float] = None
    reveal_mm: Optional[float] = None
    cornice_height: Optional[float] = None
    plinth_height: Optional[float] = None
    side_left_cm: Optional[float] = None
    side_right_cm: Optional[float] = None


class SetCorner(BaseModel):
    """Which wall gives up its depth where two runs meet (plan 7.2)."""

    kind: Literal["set_corner"] = "set_corner"
    wall_id: str
    end: Literal["start", "end"]
    mode: Optional[CornerMode] = None


class SetMaterials(BaseModel):
    kind: Literal["set_materials"] = "set_materials"
    carcass: Optional[str] = None
    doors: Optional[str] = None
    finish: Optional[str] = None


class SetHardware(BaseModel):
    kind: Literal["set_hardware"] = "set_hardware"
    style: Optional[str] = None
    placement: Optional[str] = None


Op = Annotated[
    Union[
        SetSize,
        SetFlex,
        SetLabel,
        Split,
        Merge,
        AddChild,
        Delete,
        SetFront,
        InsertBay,
        SetWall,
        SetCorner,
        SetMaterials,
        SetHardware,
    ],
    Field(discriminator="kind"),
]

OP_ADAPTER: TypeAdapter[Op] = TypeAdapter(Op)
OP_LIST_ADAPTER: TypeAdapter[list[Op]] = TypeAdapter(list[Op])


class OpRecord(BaseModel):
    """One entry in the op log. Undo replays the log without the last entry."""

    op: Op
    version_before: int
    version_after: int
    at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# -- application ----------------------------------------------------------


def apply_op(spec: Spec, op: Op) -> Spec:
    """Apply one op to a copy, revalidate, bump the version.

    The original spec is never touched. If validation fails the caller keeps
    what it had and shows the message.
    """
    draft = spec.model_copy(deep=True)
    try:
        _MUTATORS[op.kind](draft, op)
    except SpecError as err:
        raise OpError(f"{op.kind}: {err}") from err

    try:
        # Revalidate from a plain dump so every invariant and the count
        # normalisation run again on the mutated tree.
        result = build_spec(draft.model_dump(mode="json"))
    except SpecError as err:
        raise OpError(f"{op.kind} would break the spec — {_first_line(err)}") from err

    result.version = spec.version + 1
    return result


def apply_ops(spec: Spec, ops: list[Op]) -> tuple[Spec, list[OpRecord]]:
    """All-or-nothing. A failure part-way leaves the caller's spec untouched."""
    current = spec
    records: list[OpRecord] = []
    for index, op in enumerate(ops):
        try:
            nxt = apply_op(current, op)
        except OpError as err:
            raise OpError(f"op {index + 1} of {len(ops)} failed — {err}") from err
        records.append(
            OpRecord(op=op, version_before=current.version, version_after=nxt.version)
        )
        current = nxt
    return current, records


def _first_line(err: Exception) -> str:
    text = str(err).strip()
    for line in text.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("For further information"):
            return stripped
    return text


# -- mutators (operate in place on a draft copy) --------------------------


def _set_size(spec: Spec, op: SetSize) -> None:
    ref = resolve(spec, op.path)
    ref.node.size_cm = float(op.size_cm)
    ref.node.flex = None


def _set_flex(spec: Spec, op: SetFlex) -> None:
    ref = resolve(spec, op.path)
    ref.node.flex = float(op.flex)
    ref.node.size_cm = None


def _set_label(spec: Spec, op: SetLabel) -> None:
    resolve(spec, op.path).node.label = op.label


def _split(spec: Spec, op: Split) -> None:
    ref = resolve(spec, op.path)
    node = ref.node
    if not node.is_leaf():
        raise SpecError(
            f"{op.path} is already split into {node.split.value}. "
            f"Merge it first, or split one of its children."
        )

    ratios = op.ratios if op.ratios else [1.0] * op.count
    if len(ratios) < 2:
        raise SpecError("a split needs at least 2 parts")
    if any(r <= 0 for r in ratios):
        raise SpecError("split ratios must be positive")

    prefix = "row" if op.axis is SplitAxis.ROWS else "col"
    inherited = node.front
    children = [
        Opening(
            id=f"{prefix}-{i + 1}",
            flex=float(ratio),
            front=inherited.model_copy() if inherited else Front(type=FrontType.OPEN),
        )
        for i, ratio in enumerate(ratios)
    ]

    # A pair of doors side by side hinges outward from the middle. This is
    # the exact case build 1 could not represent at all.
    if (
        op.axis is SplitAxis.COLS
        and len(children) == 2
        and inherited is not None
        and inherited.type is FrontType.DOOR
    ):
        children[0].front.hinge = Hinge.LEFT
        children[1].front.hinge = Hinge.RIGHT

    node.split = op.axis
    node.children = children
    node.front = None


def _merge(spec: Spec, op: Merge) -> None:
    ref = resolve(spec, op.path)
    node = ref.node
    if node.is_leaf():
        raise SpecError(f"{op.path} is already a single opening")
    node.front = _first_front(node) or Front(type=FrontType.OPEN)
    node.children = []
    node.split = None


def _first_front(node: Opening) -> Optional[Front]:
    if node.front is not None:
        return node.front.model_copy()
    for child in node.children:
        found = _first_front(child)
        if found is not None:
            return found
    return None


def _add_child(spec: Spec, op: AddChild) -> None:
    ref = resolve(spec, op.path)
    node = ref.node
    if node.is_leaf():
        raise SpecError(
            f"{op.path} is a single opening — split it before adding children"
        )
    prefix = "row" if node.split is SplitAxis.ROWS else "col"
    child = Opening(
        id=_next_id(node.children, prefix),
        size_cm=op.size_cm,
        flex=op.flex if (op.flex is not None or op.size_cm is not None) else 1.0,
        front=Front(type=op.front_type),
    )
    index = len(node.children) if op.index is None else max(0, op.index)
    node.children.insert(index, child)


def _next_id(group: list[Opening], prefix: str) -> str:
    used = {child.id for child in group}
    n = 1
    while f"{prefix}-{n}" in used:
        n += 1
    return f"{prefix}-{n}"


def _delete(spec: Spec, op: Delete) -> None:
    ref = resolve(spec, op.path)
    if ref.is_bay:
        ref.wall.bays.pop(ref.index)
        return

    parent = ref.parent
    assert parent is not None
    parent.children.pop(ref.index)

    # A one-child split is illegal, so the parent absorbs the survivor and
    # keeps its own id and size. Deleting one of two doors leaves one door
    # filling the opening, which is what the user means.
    if len(parent.children) == 1:
        only = parent.children[0]
        parent.split = only.split
        parent.children = only.children
        parent.front = only.front


def _set_front(spec: Spec, op: SetFront) -> None:
    ref = resolve(spec, op.path)
    node = ref.node
    if not node.is_leaf():
        raise SpecError(
            f"{op.path} is split into {node.split.value} — set the front on "
            f"one of its leaves, or merge it first"
        )
    current = node.front
    node.front = Front(
        type=op.type,
        hinge=op.hinge if op.hinge is not None else (current.hinge if current else Hinge.NONE),
        handle=op.handle if op.handle is not None else (current.handle if current else "none"),
        count=op.count,
    )


def _insert_bay(spec: Spec, op: InsertBay) -> None:
    wall = spec.design_wall(op.wall_id)
    bay = Opening(
        id=_next_id(wall.bays, "bay"),
        label=op.label,
        size_cm=op.size_cm,
        flex=op.flex if (op.flex is not None or op.size_cm is not None) else 1.0,
        front=Front(type=op.front_type),
    )
    index = len(wall.bays) if op.index is None else max(0, op.index)
    wall.bays.insert(index, bay)


def _set_wall(spec: Spec, op: SetWall) -> None:
    design = spec.design_wall(op.wall_id)
    layout = spec.layout_wall(op.wall_id)
    if op.length is not None:
        layout.length = float(op.length)
    if op.height is not None:
        design.height = float(op.height)
    if op.depth is not None:
        design.depth = float(op.depth)
    if op.reveal_mm is not None:
        design.reveal_mm = float(op.reveal_mm)
    if op.cornice_height is not None:
        design.cornice.height = float(op.cornice_height)
    if op.plinth_height is not None:
        design.plinth.height = float(op.plinth_height)
    if op.side_left_cm is not None:
        design.side_columns.left_cm = float(op.side_left_cm)
    if op.side_right_cm is not None:
        design.side_columns.right_cm = float(op.side_right_cm)


def _set_corner(spec: Spec, op: SetCorner) -> None:
    layout = spec.layout_wall(op.wall_id)
    setattr(layout.corner, op.end, op.mode)


def _set_materials(spec: Spec, op: SetMaterials) -> None:
    for field in ("carcass", "doors", "finish"):
        value = getattr(op, field)
        if value is not None:
            setattr(spec.materials, field, value)


def _set_hardware(spec: Spec, op: SetHardware) -> None:
    for field in ("style", "placement"):
        value = getattr(op, field)
        if value is not None:
            setattr(spec.hardware, field, value)


_MUTATORS = {
    "set_size": _set_size,
    "set_flex": _set_flex,
    "set_label": _set_label,
    "split": _split,
    "merge": _merge,
    "add_child": _add_child,
    "delete": _delete,
    "set_front": _set_front,
    "insert_bay": _insert_bay,
    "set_wall": _set_wall,
    "set_corner": _set_corner,
    "set_materials": _set_materials,
    "set_hardware": _set_hardware,
}
