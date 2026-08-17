"""
Path addressing for spec v2.

A path is "wall-a/bay-2/row-1/col-1" and resolves segment by segment like a
filesystem. Ids are unique among siblings only; the path is what is globally
unique (progress D4).

The path is also the shared vocabulary: it is printed on the drawing, spoken
by the user, and emitted by the edit agent (plan 9.1). Most "it changed the
wrong thing" failures are reference failures, and a shared address removes
them at the source.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.models.spec import (
    DesignWall,
    Opening,
    Spec,
    SpecError,
    SplitAxis,
    distribute,
)


@dataclass
class NodeRef:
    """A resolved node, with everything an op needs to act on it."""

    path: str
    wall_id: str
    wall: DesignWall
    node: Opening
    parent: Optional[Opening]  # None when the node is a bay
    group: list[Opening]  # the sibling list the node lives in
    index: int
    axis: SplitAxis  # the axis the node is sized along
    box_w: float  # cm the node actually occupies
    box_h: float

    @property
    def is_bay(self) -> bool:
        return self.parent is None

    @property
    def extent(self) -> float:
        """The node's own size along its parent's split axis."""
        return self.box_h if self.axis is SplitAxis.ROWS else self.box_w


def resolve(spec: Spec, path: str) -> NodeRef:
    """Walk a path, carrying the box each node occupies."""
    segments = [s for s in path.split("/") if s]
    if not segments:
        raise SpecError("empty path")

    wall_id = segments[0]
    wall = spec.design_wall(wall_id)
    if len(segments) == 1:
        raise SpecError(
            f"'{path}' addresses a wall, not an opening. "
            f"Use a wall-level op, or address a bay like '{wall_id}/bay-1'."
        )

    group = wall.bays
    parent: Optional[Opening] = None
    axis = SplitAxis.COLS  # a wall's bays are a cols split (progress D2)
    box_w = spec.bay_extent(wall_id)
    box_h = wall.inner_height()
    node: Optional[Opening] = None
    index = -1

    for segment in segments[1:]:
        if node is not None:
            if node.split is None:
                raise SpecError(
                    f"'{path}': {node.id} is a leaf and has no child '{segment}'"
                )
            parent = node
            group = node.children
            axis = node.split

        index = _index_of(group, segment, path)
        extent = box_h if axis is SplitAxis.ROWS else box_w
        sizes = distribute(group, extent)
        node = group[index]
        if axis is SplitAxis.ROWS:
            box_h = sizes[index]
        else:
            box_w = sizes[index]

    assert node is not None
    return NodeRef(
        path="/".join(segments),
        wall_id=wall_id,
        wall=wall,
        node=node,
        parent=parent,
        group=group,
        index=index,
        axis=axis,
        box_w=box_w,
        box_h=box_h,
    )


def _index_of(group: list[Opening], segment: str, path: str) -> int:
    for i, child in enumerate(group):
        if child.id == segment:
            return i
    available = ", ".join(c.id for c in group) or "none"
    raise SpecError(f"'{path}': no node '{segment}' here. Available: {available}")


def list_paths(spec: Spec, wall_id: str) -> list[str]:
    """Every addressable path on a wall, in drawing order.

    This is what the edit agent is shown so it can only target nodes that
    actually exist (plan 10.3).
    """
    wall = spec.design_wall(wall_id)
    paths: list[str] = []
    for bay in wall.bays:
        paths.extend(path for path, _ in bay.walk(wall_id))
    return paths


def describe(spec: Spec, wall_id: str) -> list[dict]:
    """Flat, human-readable inventory of a wall for prompts and debugging."""
    rows: list[dict] = []
    for path in list_paths(spec, wall_id):
        ref = resolve(spec, path)
        rows.append(
            {
                "path": path,
                "label": ref.node.label,
                "split": ref.node.split.value if ref.node.split else None,
                "front": ref.node.front.type.value if ref.node.front else None,
                "w_cm": round(ref.box_w, 1),
                "h_cm": round(ref.box_h, 1),
            }
        )
    return rows
