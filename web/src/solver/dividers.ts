/**
 * Draggable boundaries between sibling openings.
 *
 * Derived from the solved Sheet, so a divider is always exactly on the line
 * the user can see. Dragging one emits set_size on the node before it —
 * pinning a size is what dragging a divider means — and the flex sibling
 * absorbs the difference.
 */

import type { Mm, Sheet } from "./sheet";

export interface Divider {
  id: string;
  /** The node whose size the drag changes. */
  beforePath: string;
  afterPath: string;
  axis: "rows" | "cols";
  x: Mm;
  y: Mm;
  w: Mm;
  h: Mm;
  /** Current extent of the before-node, in cm, for the drag start value. */
  beforeCm: number;
}

const TREE_KINDS = new Set(["bay", "opening"]);
/** Paper width of the grab strip. Generous: precision comes from the number field. */
const GRAB_MM = 2.5;

function parentOf(path: string): string {
  const cut = path.lastIndexOf("/");
  return cut < 0 ? "" : path.slice(0, cut);
}

export function dividers(sheet: Sheet, scale = sheet.scale): Divider[] {
  const groups = new Map<string, { path: string; x: Mm; y: Mm; w: Mm; h: Mm }[]>();
  for (const box of sheet.boxes) {
    if (!box.path || !TREE_KINDS.has(box.kind)) continue;
    const parent = parentOf(box.path);
    if (!parent) continue;
    groups.set(parent, [...(groups.get(parent) ?? []), { path: box.path, x: box.x, y: box.y, w: box.w, h: box.h }]);
  }

  const found: Divider[] = [];
  for (const [parent, children] of groups) {
    if (children.length < 2) continue;

    // Siblings either share a y (a cols split) or share an x (a rows split).
    const sameRow = children.every((child) => Math.abs(child.y - children[0].y) < 0.01);
    const axis: "rows" | "cols" = sameRow ? "cols" : "rows";
    const ordered = [...children].sort((a, b) => (axis === "cols" ? a.x - b.x : a.y - b.y));

    for (let i = 0; i < ordered.length - 1; i += 1) {
      const before = ordered[i];
      const after = ordered[i + 1];
      const beforeMm = axis === "cols" ? before.w : before.h;
      found.push({
        id: `${parent}::${before.path}`,
        beforePath: before.path,
        afterPath: after.path,
        axis,
        x: axis === "cols" ? before.x + before.w - GRAB_MM / 2 : before.x,
        y: axis === "cols" ? before.y : before.y + before.h - GRAB_MM / 2,
        w: axis === "cols" ? GRAB_MM : before.w,
        h: axis === "cols" ? before.h : GRAB_MM,
        beforeCm: round1((beforeMm * scale) / 10),
      });
    }
  }
  return found;
}

/** Paper millimetres -> model centimetres at this sheet's scale. */
export function mmToCm(mm: number, scale: number): number {
  return (mm * scale) / 10;
}

export function round1(value: number): number {
  return Math.round(value * 10) / 10;
}
