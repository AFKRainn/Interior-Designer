/**
 * TypeScript mirror of app/models/spec.py.
 *
 * Hand-written on purpose (no codegen step), so the drift guard is
 * tests/golden/specs/*.json: those files are produced BY Python and read by
 * the solver tests. If the Pydantic model changes shape without the fixtures
 * being regenerated, the Python side fails test_fixtures_are_current and the
 * TS side fails loudly rather than drawing the wrong thing.
 */

import type { Cm } from "./sheet";

export type SplitAxis = "rows" | "cols";

export type FrontType =
  | "door"
  | "drawer"
  | "open"
  | "glass"
  | "appliance"
  | "panel"
  | "false_front";

export type Hinge = "left" | "right" | "top" | "bottom" | "none";
export type CornerMode = "yield" | "take";

export interface Front {
  type: FrontType;
  hinge: Hinge;
  handle: string;
  count: number;
}

/**
 * A node in a bay's division tree.
 *
 * ORDER IS DRAWING ORDER and the solver depends on it:
 *   rows -> children run TOP to BOTTOM
 *   cols -> children run LEFT to RIGHT
 */
export interface Opening {
  id: string;
  label: string;
  size_cm: number | null;
  flex: number | null;
  split: SplitAxis | null;
  children: Opening[];
  front: Front | null;
}

export interface DesignWall {
  id: string;
  height: Cm;
  depth: Cm;
  reveal_mm: number;
  cornice: { type: string; height: Cm };
  plinth: { type: string; height: Cm };
  side_columns: { left_cm: Cm; right_cm: Cm; detail: string };
  bays: Opening[];
}

export interface LayoutWall {
  id: string;
  label: string;
  length: Cm;
  adjacent_to: string[];
  faces: string[];
  sequence: number;
  corner: { start: CornerMode | null; end: CornerMode | null };
}

export interface Spec {
  project_id: string;
  version: number;
  units: string;
  name: string;
  layout: { type: string; walls: LayoutWall[] };
  walls: DesignWall[];
  materials: { carcass: string; doors: string; finish: string };
  hardware: { style: string; placement: string };
  brief: string;
  assumptions: { field: string; value_cm: number | null; rationale: string }[];
  render_notes: string;
}

export function layoutWall(spec: Spec, wallId: string): LayoutWall {
  const wall = spec.layout.walls.find((w) => w.id === wallId);
  if (!wall) throw new Error(`unknown wall ${wallId}`);
  return wall;
}

export function designWall(spec: Spec, wallId: string): DesignWall {
  const wall = spec.walls.find((w) => w.id === wallId);
  if (!wall) throw new Error(`unknown wall ${wallId}`);
  return wall;
}

export function orderedWalls(spec: Spec): LayoutWall[] {
  return [...spec.layout.walls].sort(
    (a, b) => a.sequence - b.sequence || a.id.localeCompare(b.id),
  );
}

export function isAdjacent(spec: Spec, a: string, b: string): boolean {
  return layoutWall(spec, a).adjacent_to.includes(b);
}

export function isFacing(spec: Spec, a: string, b: string): boolean {
  return layoutWall(spec, a).faces.includes(b);
}

/**
 * The adjacent wall at one end of a run. A closed ring wraps, so the first
 * wall's start neighbour is the last wall. Mirrors Spec.neighbour_at.
 */
export function neighbourAt(
  spec: Spec,
  wallId: string,
  end: "start" | "end",
): LayoutWall | null {
  const ordered = orderedWalls(spec);
  const ids = ordered.map((w) => w.id);
  const index = ids.indexOf(wallId);
  if (index < 0) throw new Error(`unknown wall ${wallId}`);

  const target = index + (end === "start" ? -1 : 1);
  if (target < 0 || target >= ordered.length) {
    const wrapped = ordered[((target % ordered.length) + ordered.length) % ordered.length];
    if (ordered.length < 3 || !isAdjacent(spec, wallId, wrapped.id)) return null;
    return wrapped;
  }
  const neighbour = ordered[target];
  return isAdjacent(spec, wallId, neighbour.id) ? neighbour : null;
}

/**
 * Run length after corner resolution. Exactly one wall at each corner yields
 * its neighbour's depth, so the corner square is counted once (plan 7.2).
 */
export function usableLength(spec: Spec, wallId: string): Cm {
  const layout = layoutWall(spec, wallId);
  let length = layout.length;
  for (const end of ["start", "end"] as const) {
    if (layout.corner[end] !== "yield") continue;
    const neighbour = neighbourAt(spec, wallId, end);
    if (!neighbour) {
      throw new Error(`${wallId}: corner.${end} is 'yield' but no adjacent wall sits there`);
    }
    length -= designWall(spec, neighbour.id).depth;
  }
  return length;
}

/** How far into the run the cabinetry starts, once a start corner is yielded. */
export function startOffset(spec: Spec, wallId: string): Cm {
  const layout = layoutWall(spec, wallId);
  if (layout.corner.start !== "yield") return 0;
  const neighbour = neighbourAt(spec, wallId, "start");
  return neighbour ? designWall(spec, neighbour.id).depth : 0;
}

/** Horizontal budget the bays divide: usable run minus side trim. */
export function bayExtent(spec: Spec, wallId: string): Cm {
  const wall = designWall(spec, wallId);
  return usableLength(spec, wallId) - wall.side_columns.left_cm - wall.side_columns.right_cm;
}

/** Vertical budget for a bay: carcass minus the trim bands. */
export function innerHeight(wall: DesignWall): Cm {
  return Math.max(0, wall.height - Math.max(0, wall.cornice.height) - Math.max(0, wall.plinth.height));
}

export function isLeaf(node: Opening): boolean {
  return node.split === null;
}
