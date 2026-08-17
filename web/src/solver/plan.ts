/**
 * Top-down plan: spec -> Sheet (plan 7.2).
 *
 * Corner resolution is the point of this module. Build 1 started each next
 * wall at the previous wall's back end and rotated 90 degrees, so two 60 cm
 * runs occupied the SAME 60x60 cm square and both counted it in their bay
 * sums (bug 3.4). Here exactly one wall at each corner yields, and the corner
 * square is drawn once, owned by the wall that took it.
 *
 * Model space is y-UP (walls face inward). Paper space is y-down, like SVG
 * and CSS, so the conversion flips y.
 */

import { distribute } from "./distribute";
import { fitInto, fmtCm, toPaper } from "./scale";
import {
  A3_LANDSCAPE,
  emitFrame,
  emitTitleBlock,
  GUTTER,
  STROKE,
  TEXT_MM,
  drawingRect,
  mm,
} from "./sheet";
import type { Box, Cm, Hit, Line, Mm, Rect, Sheet, SheetConfig, Text } from "./sheet";
import {
  bayExtent,
  designWall,
  isAdjacent,
  isFacing,
  neighbourAt,
  orderedWalls,
  startOffset,
  usableLength,
} from "./spec";
import type { Spec } from "./spec";

const AISLE_CM = 120;
const DETACHED_GAP_CM = 80;
/** Paper offset from a wall's back line to its dimension line. */
const DIM_OFFSET_MM = 6;

type Vec = readonly [number, number];

const add = (a: Vec, b: Vec): Vec => [a[0] + b[0], a[1] + b[1]];
const scaleVec = (v: Vec, k: number): Vec => [v[0] * k, v[1] * k];
const rot90 = (v: Vec): Vec => [-v[1], v[0]];
const negate = (v: Vec): Vec => [-v[0], -v[1]];

export interface Footprint {
  wallId: string;
  label: string;
  /** Start of the geometric wall line, before any yielded corner. */
  origin: Vec;
  dir: Vec;
  inward: Vec;
  /** Start of the cabinetry run itself. */
  runStart: Vec;
  length: Cm;
  depth: Cm;
  /** Axis-aligned model rect (y-up). */
  minX: Cm;
  minY: Cm;
  maxX: Cm;
  maxY: Cm;
  /** The corner square this wall owns, if it took one. */
  corner: { minX: Cm; minY: Cm; maxX: Cm; maxY: Cm; withWall: string } | null;
}

/** Place every wall in model space, resolving corners as we go. */
export function placeWalls(spec: Spec): Footprint[] {
  const ordered = orderedWalls(spec);
  const placed: Footprint[] = [];

  let origin: Vec = [0, 0];
  let dir: Vec = [1, 0];
  let inward: Vec = [0, 1];

  ordered.forEach((wall, index) => {
    const design = designWall(spec, wall.id);

    if (index > 0) {
      const prev = placed[index - 1];
      const prevWall = ordered[index - 1];
      if (isAdjacent(spec, prevWall.id, wall.id)) {
        // The junction is at the previous wall's FULL length, not its usable
        // run: yielding shortens the cabinetry, not the room.
        origin = add(prev.origin, scaleVec(prev.dir, prevWall.length));
        dir = rot90(prev.dir);
        inward = rot90(prev.inward);
      } else if (isFacing(spec, prevWall.id, wall.id)) {
        origin = add(
          prev.origin,
          scaleVec(prev.inward, prev.depth + AISLE_CM + design.depth),
        );
        dir = prev.dir;
        inward = negate(prev.inward);
      } else {
        const maxX = Math.max(...placed.map((f) => f.maxX));
        origin = [maxX + DETACHED_GAP_CM, 0];
        dir = [1, 0];
        inward = [0, 1];
      }
    }

    const offset = startOffset(spec, wall.id);
    const runStart = add(origin, scaleVec(dir, offset));
    const length = usableLength(spec, wall.id);
    const runEnd = add(runStart, scaleVec(dir, length));
    const frontStart = add(runStart, scaleVec(inward, design.depth));
    const frontEnd = add(runEnd, scaleVec(inward, design.depth));

    const xs = [runStart[0], runEnd[0], frontStart[0], frontEnd[0]];
    const ys = [runStart[1], runEnd[1], frontStart[1], frontEnd[1]];

    const footprint: Footprint = {
      wallId: wall.id,
      label: wall.label || wall.id,
      origin,
      dir,
      inward,
      runStart,
      length,
      depth: design.depth,
      minX: Math.min(...xs),
      minY: Math.min(...ys),
      maxX: Math.max(...xs),
      maxY: Math.max(...ys),
      corner: null,
    };

    // If this wall TAKES a corner at its far end, it owns that square.
    if (wall.corner.end === "take") {
      const neighbour = neighbourAt(spec, wall.id, "end");
      if (neighbour) {
        const nDepth = designWall(spec, neighbour.id).depth;
        const a = add(runStart, scaleVec(dir, length - nDepth));
        const b = add(runEnd, scaleVec(inward, design.depth));
        footprint.corner = {
          minX: Math.min(a[0], b[0]),
          minY: Math.min(a[1], b[1]),
          maxX: Math.max(a[0], b[0]),
          maxY: Math.max(a[1], b[1]),
          withWall: neighbour.id,
        };
      }
    }

    placed.push(footprint);
  });

  return placed;
}

export interface PlanOptions {
  /**
   * Walls this shot is looking at. Marked on the sheet so the image model can
   * see the viewpoint, which is the whole point of shipping a plan with a
   * camera packet (plan section 6, stage 3).
   */
  highlight?: string[];
  label?: string;
}

export function solvePlan(
  spec: Spec,
  cfg: SheetConfig = A3_LANDSCAPE,
  options: PlanOptions = {},
): Sheet {
  const highlight = new Set(options.highlight ?? []);
  const footprints = placeWalls(spec);

  const boxes: Box[] = [];
  const lines: Line[] = [];
  const texts: Text[] = [];
  const hits: Hit[] = [];

  const drawing = drawingRect(cfg);
  emitFrame(cfg, boxes);

  if (footprints.length === 0) {
    emitTitleBlock(cfg, texts, { name: spec.name, view: "Plan", scale: 1, units: spec.units });
    return {
      view: "plan",
      title: spec.name || "Plan",
      scale: 1,
      sheet: { w: cfg.w, h: cfg.h },
      drawing,
      area: drawing,
      content: { x: drawing.x, y: drawing.y, w: 0, h: 0 },
      boxes,
      lines,
      texts,
      hits,
    };
  }

  const minX = Math.min(...footprints.map((f) => f.minX));
  const minY = Math.min(...footprints.map((f) => f.minY));
  const maxX = Math.max(...footprints.map((f) => f.maxX));
  const maxY = Math.max(...footprints.map((f) => f.maxY));

  // Paper room for the dimension ring, reserved before choosing a scale.
  const pad = GUTTER.dimGap + GUTTER.dimBand;
  const area: Rect = {
    x: drawing.x + pad,
    y: drawing.y + GUTTER.viewLabel + pad,
    w: drawing.w - pad * 2,
    h: drawing.h - GUTTER.viewLabel - pad * 2,
  };
  const { scale, content } = fitInto(maxX - minX, maxY - minY, area);

  const px = (cm: Cm): Mm => toPaper(cm, scale);
  const X = (cm: Cm): Mm => mm(content.x + px(cm - minX));
  const Y = (cm: Cm): Mm => mm(content.y + px(maxY - cm));
  /** Direction vectors flip in y when they cross into paper space. */
  const paperDir = (v: Vec): Vec => [v[0], -v[1]];

  emitTitleBlock(cfg, texts, {
    name: spec.name,
    view: "Plan",
    scale,
    units: spec.units,
  });
  texts.push({
    id: "view-label",
    x: drawing.x,
    y: mm(drawing.y + TEXT_MM.label),
    size: TEXT_MM.label,
    anchor: "start",
    value: options.label ? `PLAN - ${options.label}` : "PLAN",
  });

  for (const fp of footprints) {
    const rect = {
      x: X(fp.minX),
      y: Y(fp.maxY),
      w: mm(px(fp.maxX - fp.minX)),
      h: mm(px(fp.maxY - fp.minY)),
    };
    const inShot = highlight.has(fp.wallId);
    boxes.push({
      id: fp.wallId,
      kind: inShot ? "in-shot" : "footprint",
      path: fp.wallId,
      ...rect,
      stroke: STROKE.outline,
      label: inShot ? `${fp.label} (in shot)` : fp.label,
    });
    hits.push({ id: fp.wallId, path: fp.wallId, ...rect });

    if (fp.corner) {
      boxes.push({
        id: `${fp.wallId}#corner`,
        kind: "corner",
        x: X(fp.corner.minX),
        y: Y(fp.corner.maxY),
        w: mm(px(fp.corner.maxX - fp.corner.minX)),
        h: mm(px(fp.corner.maxY - fp.corner.minY)),
        stroke: STROKE.thin,
        label: `corner with ${fp.corner.withWall}`,
      });
    }

    emitBayDividers(fp);
    emitWallLabel(fp, rect);
    emitLengthDim(fp);
  }

  function emitBayDividers(fp: Footprint): void {
    const wall = designWall(spec, fp.wallId);
    if (wall.bays.length < 2) return;
    const widths = distribute(wall.bays, bayExtent(spec, fp.wallId));
    let cursor = wall.side_columns.left_cm;
    widths.slice(0, -1).forEach((width, index) => {
      cursor += width;
      const back = add(fp.runStart, scaleVec(fp.dir, cursor));
      const front = add(back, scaleVec(fp.inward, fp.depth));
      lines.push({
        id: `${fp.wallId}/${wall.bays[index].id}#divider`,
        kind: "divider",
        x1: X(back[0]),
        y1: Y(back[1]),
        x2: X(front[0]),
        y2: Y(front[1]),
        stroke: STROKE.partition,
      });
    });
  }

  function emitWallLabel(fp: Footprint, rect: Rect): void {
    if (rect.w < 8 || rect.h < 5) return;
    const vertical = Math.abs(fp.dir[0]) < 0.5;
    texts.push({
      id: `${fp.wallId}#label`,
      x: mm(rect.x + rect.w / 2),
      y: mm(rect.y + rect.h / 2 + TEXT_MM.label / 3),
      size: TEXT_MM.label,
      anchor: "middle",
      value: fp.wallId.toUpperCase(),
      ...(vertical ? { rotate: -90 } : {}),
    });
  }

  function emitLengthDim(fp: Footprint): void {
    // Walls face inward, so a back line is always on the outside of the
    // room: its dimension lands in the reserved ring, never on the drawing.
    const outward = paperDir(negate(fp.inward));
    const runEnd = add(fp.runStart, scaleVec(fp.dir, fp.length));
    const a: Vec = [X(fp.runStart[0]), Y(fp.runStart[1])];
    const b: Vec = [X(runEnd[0]), Y(runEnd[1])];
    const shift = scaleVec(outward, DIM_OFFSET_MM);
    const a2 = add(a, shift);
    const b2 = add(b, shift);

    lines.push({ id: `${fp.wallId}#dw1`, kind: "witness", x1: a[0], y1: a[1], x2: a2[0], y2: a2[1], stroke: STROKE.thin });
    lines.push({ id: `${fp.wallId}#dw2`, kind: "witness", x1: b[0], y1: b[1], x2: b2[0], y2: b2[1], stroke: STROKE.thin });
    lines.push({ id: `${fp.wallId}#dim`, kind: "dimension", x1: a2[0], y1: a2[1], x2: b2[0], y2: b2[1], stroke: STROKE.thin });

    const vertical = Math.abs(fp.dir[0]) < 0.5;
    texts.push({
      id: `${fp.wallId}#dim-text`,
      x: mm((a2[0] + b2[0]) / 2 + (vertical ? -1.5 : 0)),
      y: mm((a2[1] + b2[1]) / 2 + (vertical ? 0 : -1.5)),
      size: TEXT_MM.dimension,
      anchor: "middle",
      value: fmtCm(fp.length),
      ...(vertical ? { rotate: -90 } : {}),
    });
  }

  return {
    view: "plan",
    title: spec.name || "Plan",
    scale,
    sheet: { w: cfg.w, h: cfg.h },
    drawing,
    area,
    content,
    boxes,
    lines,
    texts,
    hits,
  };
}
