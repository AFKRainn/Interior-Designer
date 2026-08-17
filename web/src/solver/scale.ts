/**
 * Model cm -> paper mm, snapped to a standard scale (plan 6.2).
 *
 * Never scale-to-fit continuously. A drawing at 1:23.7 is not a drawing, it
 * is a picture. Snapping to the ladder is what makes a 40 cm nightstand and a
 * 6 m run produce sheets that read as the same drawing set.
 */

import type { Cm, Mm, Rect } from "./sheet";
import { mm } from "./sheet";

/** ISO 5455 preferred reduction scales, plus full size. */
export const SCALE_LADDER = [1, 2, 5, 10, 20, 50, 100] as const;

export function toPaper(cm: Cm, scale: number): Mm {
  return (cm * 10) / scale;
}

export function toModel(paper: Mm, scale: number): Cm {
  return (paper * scale) / 10;
}

/** The largest scale (smallest denominator) at which the content still fits. */
export function chooseScale(
  modelW: Cm,
  modelH: Cm,
  availW: Mm,
  availH: Mm,
): number {
  for (const scale of SCALE_LADDER) {
    if (toPaper(modelW, scale) <= availW && toPaper(modelH, scale) <= availH) {
      return scale;
    }
  }
  return SCALE_LADDER[SCALE_LADDER.length - 1];
}

export interface Fit {
  scale: number;
  content: Rect;
}

/** Pick a scale, then centre the scaled content inside the available area. */
export function fitInto(modelW: Cm, modelH: Cm, area: Rect): Fit {
  const scale = chooseScale(modelW, modelH, area.w, area.h);
  const w = toPaper(modelW, scale);
  const h = toPaper(modelH, scale);
  return {
    scale,
    content: {
      x: mm(area.x + (area.w - w) / 2),
      y: mm(area.y + (area.h - h) / 2),
      w: mm(w),
      h: mm(h),
    },
  };
}

/** Dimension text: whole centimetres unless the value genuinely is not. */
export function fmtCm(value: Cm): string {
  const rounded = Math.round(value);
  return Math.abs(value - rounded) < 0.05 ? `${rounded}` : value.toFixed(1);
}
