"""
What changed between two specs, as paths.

This is what makes the ghost preview possible (plan 10.3). Build 1 applied
edits blind: the model rewrote the whole document and the user found out
afterwards, if at all. Here every proposed change can be drawn in red and
green before it is allowed to happen.
"""
from __future__ import annotations

from app.models.spec import Opening, Spec

Change = str  # "added" | "removed" | "changed"


def _nodes(spec: Spec) -> dict[str, Opening]:
    found: dict[str, Opening] = {}
    for wall in spec.walls:
        for bay in wall.bays:
            for path, node in bay.walk(wall.id):
                found[path] = node
    return found


def _identity(node: Opening) -> tuple:
    """The parts of a node a user would notice changing."""
    front = node.front
    return (
        node.size_cm,
        node.flex,
        node.split.value if node.split else None,
        node.label,
        front.type.value if front else None,
        front.hinge.value if front else None,
        front.handle if front else None,
        tuple(child.id for child in node.children),
    )


def diff_paths(before: Spec, after: Spec) -> dict[str, Change]:
    """path -> added / removed / changed. Unchanged paths are absent."""
    old = _nodes(before)
    new = _nodes(after)
    result: dict[str, Change] = {}

    for path in new.keys() - old.keys():
        result[path] = "added"
    for path in old.keys() - new.keys():
        result[path] = "removed"
    for path in old.keys() & new.keys():
        if _identity(old[path]) != _identity(new[path]):
            result[path] = "changed"

    # A parent whose children were replaced wholesale reads better as
    # "changed" than as a pile of unrelated adds and removes.
    for path in list(result):
        parent = path.rsplit("/", 1)[0] if "/" in path else None
        if parent and parent in new and parent in old and parent not in result:
            if _identity(old[parent]) != _identity(new[parent]):
                result[parent] = "changed"

    return result


def summarise(before: Spec, after: Spec) -> str:
    """One line for the chat log."""
    changes = diff_paths(before, after)
    if not changes:
        return "no change"
    counts: dict[str, int] = {}
    for kind in changes.values():
        counts[kind] = counts.get(kind, 0) + 1
    bits = [f"{count} {kind}" for kind, count in sorted(counts.items())]
    return ", ".join(bits)
