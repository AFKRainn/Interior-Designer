/**
 * THE sizing rule (plan 5.1). Fixed siblings first, flex divides what is left.
 *
 * This is the one formula build 2 knowingly duplicates: Python validates with
 * it server-side, and the browser re-runs it every frame during a drag, which
 * cannot round-trip. Duplicated layout math is what caused build-1 bug 3.5,
 * so both copies are pinned to tests/golden/distribute.json. Change the
 * formula, change both, add a vector.
 */

import type { Cm } from "./sheet";
import type { Opening } from "./spec";

export interface Sizeable {
  size_cm: number | null;
  flex: number | null;
}

export function distribute(children: Sizeable[], extent: Cm): Cm[] {
  if (children.length === 0) return [];

  let fixedTotal = 0;
  let flexTotal = 0;
  for (const child of children) {
    if (child.size_cm !== null && child.size_cm !== undefined) fixedTotal += child.size_cm;
    else flexTotal += child.flex ?? 1;
  }
  const remainder = extent - fixedTotal;

  return children.map((child) => {
    if (child.size_cm !== null && child.size_cm !== undefined) {
      return round4(child.size_cm);
    }
    const share = flexTotal ? (child.flex ?? 1) / flexTotal : 0;
    return round4(Math.max(0, remainder) * share);
  });
}

export function round4(value: number): number {
  return Math.round(value * 10000) / 10000;
}

/** Sizes of a split node's children along its own axis. */
export function childSizes(node: Opening, boxW: Cm, boxH: Cm): Cm[] {
  const extent = node.split === "rows" ? boxH : boxW;
  return distribute(node.children, extent);
}
