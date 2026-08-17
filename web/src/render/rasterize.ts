/**
 * SVG -> PNG in the browser, for the photoreal reference images (plan 8).
 *
 * The browser rasterises what the user actually approved and posts it at
 * lock, so the image model's reference cannot disagree with the drawing on
 * screen. That is the whole reason there is no second server-side renderer.
 */

import { sheetToSvg } from "./SheetSVG";
import type { Sheet } from "../solver/sheet";

/** 8 px/mm gives roughly 200 dpi: plenty for an image-model reference. */
export const DEFAULT_PX_PER_MM = 8;

export async function svgToPngBase64(
  svg: string,
  widthPx: number,
  heightPx: number,
): Promise<string> {
  const blob = new Blob([svg], { type: "image/svg+xml;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  try {
    const image = await loadImage(url);
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(widthPx);
    canvas.height = Math.round(heightPx);
    const context = canvas.getContext("2d");
    if (!context) throw new Error("canvas 2d context unavailable");
    context.fillStyle = "#ffffff";
    context.fillRect(0, 0, canvas.width, canvas.height);
    context.drawImage(image, 0, 0, canvas.width, canvas.height);
    const dataUrl = canvas.toDataURL("image/png");
    return dataUrl.slice(dataUrl.indexOf(",") + 1);
  } finally {
    URL.revokeObjectURL(url);
  }
}

function loadImage(url: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () => resolve(image);
    image.onerror = () => reject(new Error("could not rasterise sheet"));
    image.src = url;
  });
}

export interface RasterSheet {
  name: string;
  wall_id: string | null;
  mime_type: "image/png";
  data: string;
}

export async function rasterizeSheet(
  sheet: Sheet,
  name: string,
  pxPerMm = DEFAULT_PX_PER_MM,
): Promise<RasterSheet> {
  const svg = sheetToSvg(sheet);
  const data = await svgToPngBase64(svg, sheet.sheet.w * pxPerMm, sheet.sheet.h * pxPerMm);
  return { name, wall_id: sheet.wallId ?? null, mime_type: "image/png", data };
}
