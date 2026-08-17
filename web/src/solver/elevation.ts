/**
 * Front elevation of one wall: spec -> Sheet (plan 7.1).
 *
 * Emits geometry, annotation AND hit regions in a single pass. Build 1 kept
 * a second copy of the layout maths in editor/drawings.py to place click
 * targets, which meant any renderer change silently desynced clicking from
 * drawing (bug 3.5). Here `hits` comes off the same numbers as `boxes`.
 */

import { childSizes, distribute } from "./distribute";
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
  innerHeight,
  isLeaf,
  layoutWall,
  usableLength,
} from "./spec";
import type { Front, Opening, Spec } from "./spec";

/** A box in MODEL space (cm), origin at the carcass top-left. */
interface ModelBox {
  x: Cm;
  y: Cm;
  w: Cm;
  h: Cm;
}

/** An opening only gets its name printed if the name will actually fit. */
const LABEL_MIN_W = 10;
const LABEL_MIN_H = 6;

/** Real hardware, in cm, so handles scale with the drawing like everything else. */
const HANDLE_LEN = 12;
const HANDLE_THICK = 1.6;

const NO_FRONT = new Set(["open"]);
const NO_HANDLE = new Set(["open", "panel", "false_front"]);

export function solveElevation(
  spec: Spec,
  wallId: string,
  cfg: SheetConfig = A3_LANDSCAPE,
): Sheet {
  const layout = layoutWall(spec, wallId);
  const wall = designWall(spec, wallId);

  const W = usableLength(spec, wallId);
  const H = wall.height;
  const cornice = Math.max(0, wall.cornice.height);
  const plinth = Math.max(0, wall.plinth.height);
  const inner = innerHeight(wall);
  const reveal = wall.reveal_mm / 10; // mm of hardware spec -> cm of model space

  // Paper room for annotation, reserved BEFORE choosing a scale so the
  // dimensions can never be squeezed off the sheet.
  const drawing = drawingRect(cfg);
  const padLeft = GUTTER.dimGap + GUTTER.dimBand;
  const padRight = GUTTER.dimGap + GUTTER.dimBand;
  const padTop = GUTTER.viewLabel;
  const padBottom = GUTTER.dimGap + GUTTER.dimBand * 2;

  const area: Rect = {
    x: drawing.x + padLeft,
    y: drawing.y + padTop,
    w: drawing.w - padLeft - padRight,
    h: drawing.h - padTop - padBottom,
  };
  const { scale, content } = fitInto(W, H, area);

  const boxes: Box[] = [];
  const lines: Line[] = [];
  const texts: Text[] = [];
  const hits: Hit[] = [];

  const px = (cm: Cm): Mm => toPaper(cm, scale);
  const X = (cm: Cm): Mm => mm(content.x + px(cm));
  const Y = (cm: Cm): Mm => mm(content.y + px(cm));

  emitFrame(cfg, boxes);
  emitTitleBlock(cfg, texts, {
    name: spec.name,
    view: `Elevation - ${layout.label || wallId}`,
    scale,
    units: spec.units,
  });
  texts.push({
    id: "view-label",
    x: drawing.x,
    y: mm(drawing.y + TEXT_MM.label),
    size: TEXT_MM.label,
    anchor: "start",
    value: (layout.label || wallId).toUpperCase(),
  });

  boxes.push({
    id: wallId,
    kind: "carcass",
    path: wallId,
    x: X(0),
    y: Y(0),
    w: mm(px(W)),
    h: mm(px(H)),
    stroke: STROKE.outline,
    label: layout.label || wallId,
  });

  if (cornice > 0) {
    boxes.push({
      id: `${wallId}#cornice`,
      kind: "cornice",
      x: X(0),
      y: Y(0),
      w: mm(px(W)),
      h: mm(px(cornice)),
      stroke: STROKE.partition,
    });
  }
  if (plinth > 0) {
    boxes.push({
      id: `${wallId}#plinth`,
      kind: "plinth",
      x: X(0),
      y: Y(H - plinth),
      w: mm(px(W)),
      h: mm(px(plinth)),
      stroke: STROKE.partition,
    });
  }

  // Side columns take real width; they are not drawn over the bays the way
  // build 1 drew them (progress D9).
  const cols = wall.side_columns;
  if (cols.left_cm > 0) {
    boxes.push({
      id: `${wallId}#side-left`,
      kind: "side-column",
      x: X(0),
      y: Y(cornice),
      w: mm(px(cols.left_cm)),
      h: mm(px(inner)),
      stroke: STROKE.partition,
    });
  }
  if (cols.right_cm > 0) {
    boxes.push({
      id: `${wallId}#side-right`,
      kind: "side-column",
      x: X(W - cols.right_cm),
      y: Y(cornice),
      w: mm(px(cols.right_cm)),
      h: mm(px(inner)),
      stroke: STROKE.partition,
    });
  }

  function emitHandle(front: Front, path: string, box: ModelBox): void {
    if (front.handle.trim().toLowerCase() === "none") return;
    if (NO_HANDLE.has(front.type)) return;

    let rect: ModelBox;
    if (front.type === "drawer") {
      const len = Math.min(HANDLE_LEN, box.w * 0.5);
      rect = {
        x: box.x + (box.w - len) / 2,
        y: box.y + box.h / 2 - HANDLE_THICK / 2,
        w: len,
        h: HANDLE_THICK,
      };
    } else {
      const len = Math.min(HANDLE_LEN, box.h * 0.4);
      // opposite the hinge, so a door pair reads correctly
      const nearLeft = front.hinge === "right";
      rect = {
        x: nearLeft ? box.x + 2 : box.x + box.w - 2 - HANDLE_THICK,
        y: box.y + (box.h - len) / 2,
        w: HANDLE_THICK,
        h: len,
      };
    }
    if (rect.w <= 0 || rect.h <= 0) return;
    boxes.push({
      id: `${path}#handle`,
      kind: "handle",
      x: X(rect.x),
      y: Y(rect.y),
      w: mm(px(rect.w)),
      h: mm(px(rect.h)),
      stroke: STROKE.thin,
    });
  }

  function emitNode(node: Opening, path: string, depth: number, box: ModelBox): void {
    boxes.push({
      id: path,
      kind: depth === 0 ? "bay" : "opening",
      path,
      x: X(box.x),
      y: Y(box.y),
      w: mm(px(box.w)),
      h: mm(px(box.h)),
      stroke: STROKE.partition,
      label: node.label || node.id,
    });
    hits.push({
      id: path,
      path,
      x: X(box.x),
      y: Y(box.y),
      w: mm(px(box.w)),
      h: mm(px(box.h)),
    });

    // The shared vocabulary only works if the name is legible (plan 9.1).
    const paperW = px(box.w);
    const paperH = px(box.h);
    if (paperW >= LABEL_MIN_W && paperH >= LABEL_MIN_H) {
      texts.push({
        id: `${path}#label`,
        x: mm(X(box.x) + paperW / 2),
        y: mm(Y(box.y) + TEXT_MM.label + 1),
        size: TEXT_MM.label,
        anchor: "middle",
        value: (node.label || node.id).toUpperCase(),
      });
    }

    if (isLeaf(node)) {
      const front = node.front;
      if (!front) return;
      if (!NO_FRONT.has(front.type)) {
        const inset = reveal / 2;
        const fw = box.w - inset * 2;
        const fh = box.h - inset * 2;
        if (fw > 0 && fh > 0) {
          boxes.push({
            id: `${path}#front`,
            kind: "front",
            path,
            x: X(box.x + inset),
            y: Y(box.y + inset),
            w: mm(px(fw)),
            h: mm(px(fh)),
            stroke: STROKE.front,
            front: front.type,
          });
          emitHandle(front, path, { x: box.x + inset, y: box.y + inset, w: fw, h: fh });
        }
      }
      return;
    }

    const sizes = childSizes(node, box.w, box.h);
    let cursor = node.split === "rows" ? box.y : box.x;
    node.children.forEach((child, index) => {
      const size = sizes[index];
      const childBox: ModelBox =
        node.split === "rows"
          ? { x: box.x, y: cursor, w: box.w, h: size }
          : { x: cursor, y: box.y, w: size, h: box.h };
      cursor += size;
      emitNode(child, `${path}/${child.id}`, depth + 1, childBox);
    });
  }

  // A wall's bays ARE a cols split of the usable run (progress D2), so the
  // same sizing rule applies here as at every other depth.
  const bayWidths = distribute(wall.bays, bayExtent(spec, wallId));
  let cursor = cols.left_cm;
  const bayStarts: Cm[] = [];
  wall.bays.forEach((bay, index) => {
    bayStarts.push(cursor);
    emitNode(bay, `${wallId}/${bay.id}`, 0, {
      x: cursor,
      y: cornice,
      w: bayWidths[index],
      h: inner,
    });
    cursor += bayWidths[index];
  });

  // -- dimensions -------------------------------------------------------
  // Detail nearest the object, overall outermost. Standard drafting order.
  const bottom = content.y + px(H);
  const bandDetail = mm(bottom + GUTTER.dimGap);
  const bandOverall = mm(bandDetail + GUTTER.dimBand);

  function hDim(id: string, x1: Cm, x2: Cm, y: Mm, value: Cm): void {
    if (x2 - x1 <= 0) return;
    lines.push({ id: `${id}#w1`, kind: "witness", x1: X(x1), y1: mm(bottom), x2: X(x1), y2: mm(y + 1.5), stroke: STROKE.thin });
    lines.push({ id: `${id}#w2`, kind: "witness", x1: X(x2), y1: mm(bottom), x2: X(x2), y2: mm(y + 1.5), stroke: STROKE.thin });
    lines.push({ id: `${id}#d`, kind: "dimension", x1: X(x1), y1: y, x2: X(x2), y2: y, stroke: STROKE.thin });
    texts.push({
      id: `${id}#t`,
      x: mm((X(x1) + X(x2)) / 2),
      y: mm(y - 1.2),
      size: TEXT_MM.dimension,
      anchor: "middle",
      value: fmtCm(value),
    });
  }

  wall.bays.forEach((bay, index) => {
    hDim(
      `dim-${bay.id}`,
      bayStarts[index],
      bayStarts[index] + bayWidths[index],
      bandDetail,
      bayWidths[index],
    );
  });
  hDim("dim-overall", 0, W, bandOverall, W);

  function vDim(id: string, y1: Cm, y2: Cm, x: Mm, value: Cm, side: "left" | "right"): void {
    if (y2 - y1 <= 0) return;
    const edge = side === "left" ? content.x : content.x + px(W);
    lines.push({ id: `${id}#w1`, kind: "witness", x1: mm(edge), y1: Y(y1), x2: x, y2: Y(y1), stroke: STROKE.thin });
    lines.push({ id: `${id}#w2`, kind: "witness", x1: mm(edge), y1: Y(y2), x2: x, y2: Y(y2), stroke: STROKE.thin });
    lines.push({ id: `${id}#d`, kind: "dimension", x1: x, y1: Y(y1), x2: x, y2: Y(y2), stroke: STROKE.thin });
    texts.push({
      id: `${id}#t`,
      x: mm(x - 1.2),
      y: mm((Y(y1) + Y(y2)) / 2),
      size: TEXT_MM.dimension,
      anchor: "middle",
      value: fmtCm(value),
      rotate: -90,
    });
  }

  vDim("dim-height", 0, H, mm(content.x - GUTTER.dimGap), H, "left");
  const rightDim = mm(content.x + px(W) + GUTTER.dimGap);
  if (cornice > 0) vDim("dim-cornice", 0, cornice, rightDim, cornice, "right");
  if (plinth > 0) vDim("dim-plinth", H - plinth, H, rightDim, plinth, "right");

  return {
    view: "elevation",
    wallId,
    title: layout.label || wallId,
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
