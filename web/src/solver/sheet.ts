/**
 * The Sheet contract, and the drafting constants everything is drawn with.
 *
 * TWO SPACES (plan.txt section 6). This is the rule build 1 broke.
 *   MODEL space = the real object, in cm. Never drawn directly.
 *   PAPER space = the sheet, in mm. Everything in a Sheet is mm.
 *   scale       = model -> paper, from a fixed ISO ladder.
 *
 * Build 1 declared "1 user unit = 1 cm" and then used 48 units of padding,
 * 7-unit text and 1.2-unit strokes -- i.e. 48 cm of padding, 7 cm lettering
 * and 12 mm lines. That is why a 320 cm wall looked passable and a 60 cm
 * cabinet looked broken. Annotation here is a constant number of MILLIMETRES
 * and never scales with the object.
 *
 * A Sheet is inert data. Renderers translate it; they never compute with it.
 */

export type Mm = number;
export type Cm = number;

export interface Rect {
  x: Mm;
  y: Mm;
  w: Mm;
  h: Mm;
}

export type BoxKind =
  | "carcass"
  | "cornice"
  | "plinth"
  | "side-column"
  | "bay"
  | "opening"
  | "front"
  | "handle"
  | "footprint"
  | "in-shot"
  | "corner"
  | "frame"
  | "title-block";

export type LineKind = "dimension" | "witness" | "tick" | "divider" | "shelf";

export interface Box {
  id: string;
  kind: BoxKind;
  /** Set on anything addressable, so a click maps straight to an op target. */
  path?: string;
  x: Mm;
  y: Mm;
  w: Mm;
  h: Mm;
  stroke: Mm;
  front?: string;
  label?: string;
}

export interface Line {
  id: string;
  kind: LineKind;
  x1: Mm;
  y1: Mm;
  x2: Mm;
  y2: Mm;
  stroke: Mm;
}

export interface Text {
  id: string;
  x: Mm;
  y: Mm;
  /** Cap height in mm, from the ISO 3098 range. Never scaled. */
  size: Mm;
  anchor: "start" | "middle" | "end";
  value: string;
  rotate?: number;
}

export interface Hit {
  id: string;
  path: string;
  x: Mm;
  y: Mm;
  w: Mm;
  h: Mm;
}

export interface Sheet {
  view: "elevation" | "plan";
  wallId?: string;
  title: string;
  /** Denominator of the drawing scale: 20 means 1:20. */
  scale: number;
  sheet: { w: Mm; h: Mm };
  /** The full drawing area of the sheet, inside the frame and title block. */
  drawing: Rect;
  /** The sub-area geometry was fitted into, once annotation room is reserved. */
  area: Rect;
  /** Where the geometry actually landed. Used to check the sheet reads well. */
  content: Rect;
  boxes: Box[];
  lines: Line[];
  texts: Text[];
  hits: Hit[];
}

/**
 * ISO 128-20 line width ladder. Thick:thin here is 0.7:0.18, comfortably
 * past the standard's 2:1 minimum.
 */
export const STROKE = {
  /** carcass outline, wall footprint */
  outline: 0.7,
  /** partitions, cornice and plinth bands, bay dividers */
  partition: 0.35,
  /** front outlines, shelf lines */
  front: 0.25,
  /** dimension lines, witness lines, hatching, centrelines */
  thin: 0.18,
} as const;

/** ISO 3098 nominal lettering heights. */
export const TEXT_MM = {
  dimension: 2.5,
  label: 3.5,
  title: 5.0,
} as const;

export interface SheetConfig {
  w: Mm;
  h: Mm;
  margin: Mm;
  titleBlockH: Mm;
}

/** A3 landscape. One sheet size keeps every drawing comparable. */
export const A3_LANDSCAPE: SheetConfig = {
  w: 420,
  h: 297,
  margin: 10,
  titleBlockH: 30,
};

/** Paper room reserved for annotation, in mm. Never scaled. */
export const GUTTER = {
  /** gap between the geometry and the first dimension line */
  dimGap: 6,
  /** height of one dimension band */
  dimBand: 11,
  /** room above the drawing for the view label */
  viewLabel: 8,
  pad: 4,
} as const;

export function frameRect(cfg: SheetConfig): Rect {
  return {
    x: cfg.margin,
    y: cfg.margin,
    w: cfg.w - cfg.margin * 2,
    h: cfg.h - cfg.margin * 2,
  };
}

export function drawingRect(cfg: SheetConfig): Rect {
  const frame = frameRect(cfg);
  return { x: frame.x, y: frame.y, w: frame.w, h: frame.h - cfg.titleBlockH };
}

export function titleBlockRect(cfg: SheetConfig): Rect {
  const frame = frameRect(cfg);
  return {
    x: frame.x,
    y: frame.y + frame.h - cfg.titleBlockH,
    w: frame.w,
    h: cfg.titleBlockH,
  };
}

/** Round to 0.001 mm so golden comparisons are not tripped by float noise. */
export function mm(value: number): Mm {
  return Math.round(value * 1000) / 1000;
}

export function emitFrame(cfg: SheetConfig, boxes: Box[]): void {
  const frame = frameRect(cfg);
  boxes.push({ id: "frame", kind: "frame", ...frame, stroke: STROKE.outline });
  const title = titleBlockRect(cfg);
  boxes.push({ id: "title-block", kind: "title-block", ...title, stroke: STROKE.partition });
}

export function emitTitleBlock(
  cfg: SheetConfig,
  texts: Text[],
  fields: { name: string; view: string; scale: number; units: string },
): void {
  const block = titleBlockRect(cfg);
  const left = block.x + 4;
  texts.push({
    id: "title-name",
    x: left,
    y: mm(block.y + 10),
    size: TEXT_MM.title,
    anchor: "start",
    value: fields.name || "Untitled",
  });
  texts.push({
    id: "title-view",
    x: left,
    y: mm(block.y + 20),
    size: TEXT_MM.label,
    anchor: "start",
    value: fields.view,
  });
  texts.push({
    id: "title-scale",
    x: mm(block.x + block.w - 4),
    y: mm(block.y + 10),
    size: TEXT_MM.label,
    anchor: "end",
    value: `SCALE 1:${fields.scale}`,
  });
  texts.push({
    id: "title-units",
    x: mm(block.x + block.w - 4),
    y: mm(block.y + 20),
    size: TEXT_MM.dimension,
    anchor: "end",
    value: `Dimensions in ${fields.units}`,
  });
}
