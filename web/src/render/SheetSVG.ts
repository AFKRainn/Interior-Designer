/**
 * Sheet -> SVG. The export backend (plan 8C).
 *
 * Contains no arithmetic: it translates a solved Sheet and nothing else. The
 * editing surface (ElevationDOM, Phase 3) consumes the SAME Sheet, which is
 * why the reference image handed to the image model cannot disagree with what
 * the user approved on screen.
 *
 * Units are millimetres throughout, so the viewBox is the physical sheet and
 * printing at 100% gives a true-scale drawing.
 */

import type { Sheet } from "../solver/sheet";

export interface SvgOptions {
  /** Light fill behind fronts so they read as panels, not wireframe. */
  shadeFronts?: boolean;
  background?: string;
}

const FRONT_FILL: Record<string, string> = {
  door: "#f4f4f2",
  drawer: "#efefec",
  glass: "#e8f0f4",
  appliance: "#e6e6e6",
  panel: "#f0efec",
  false_front: "#f4f4f2",
};

function esc(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

export function sheetToSvg(sheet: Sheet, options: SvgOptions = {}): string {
  const { shadeFronts = true, background = "#ffffff" } = options;
  const parts: string[] = [];

  parts.push(
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${sheet.sheet.w} ${sheet.sheet.h}" ` +
      `width="${sheet.sheet.w}mm" height="${sheet.sheet.h}mm" ` +
      `font-family="Helvetica, Arial, sans-serif">`,
  );
  parts.push(`<title>${esc(sheet.title)} - 1:${sheet.scale}</title>`);
  parts.push(
    `<rect x="0" y="0" width="${sheet.sheet.w}" height="${sheet.sheet.h}" fill="${background}"/>`,
  );
  // Line weights are real millimetres, so they must not scale with zoom.
  parts.push(`<g stroke="#000" fill="none" vector-effect="non-scaling-stroke">`);

  for (const box of sheet.boxes) {
    let fill = "none";
    if (shadeFronts && box.kind === "front" && box.front) {
      fill = FRONT_FILL[box.front] ?? "none";
    } else if (box.kind === "in-shot") {
      // The camera packet ships this plan; the shaded runs are the ones the
      // photograph is allowed to show.
      fill = "#dbe7f0";
    } else if (box.kind === "footprint") {
      fill = "#f5f5f4";
    }
    const dashed = box.kind === "corner" ? ' stroke-dasharray="2 1.5"' : "";
    parts.push(
      `<rect x="${box.x}" y="${box.y}" width="${box.w}" height="${box.h}" ` +
        `stroke-width="${box.stroke}" fill="${fill}"${dashed}/>`,
    );
  }

  for (const line of sheet.lines) {
    parts.push(
      `<line x1="${line.x1}" y1="${line.y1}" x2="${line.x2}" y2="${line.y2}" ` +
        `stroke-width="${line.stroke}"/>`,
    );
  }

  parts.push(`</g>`);
  parts.push(`<g fill="#000" stroke="none">`);
  for (const text of sheet.texts) {
    const transform = text.rotate ? ` transform="rotate(${text.rotate} ${text.x} ${text.y})"` : "";
    parts.push(
      `<text x="${text.x}" y="${text.y}" font-size="${text.size}" ` +
        `text-anchor="${text.anchor}"${transform}>${esc(text.value)}</text>`,
    );
  }
  parts.push(`</g>`);
  parts.push(`</svg>`);
  return parts.join("\n");
}
