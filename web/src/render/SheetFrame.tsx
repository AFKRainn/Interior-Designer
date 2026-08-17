/**
 * Fits a physical sheet into whatever space the browser gives it.
 *
 * The sheet is laid out in REAL millimetres; this only zooms the finished
 * thing. Nothing inside recalculates, so what you see is the drawing scaled,
 * never a different drawing. Printing skips the zoom entirely and comes out
 * at true scale.
 */
import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";

import type { Sheet } from "../solver/sheet";

/** CSS reference pixels per millimetre. */
export const PX_PER_MM = 96 / 25.4;

export function SheetFrame({
  sheet,
  children,
  maxZoom = 2,
}: {
  sheet: Sheet;
  children: ReactNode;
  maxZoom?: number;
}) {
  const outer = useRef<HTMLDivElement>(null);
  const [zoom, setZoom] = useState(1);

  useEffect(() => {
    const element = outer.current;
    if (!element) return;
    const sheetPx = sheet.sheet.w * PX_PER_MM;
    const fit = () => {
      const available = element.clientWidth;
      if (available > 0) setZoom(Math.min(maxZoom, available / sheetPx));
    };
    fit();
    const observer = new ResizeObserver(fit);
    observer.observe(element);
    return () => observer.disconnect();
  }, [sheet.sheet.w, maxZoom]);

  return (
    <div className="sheet-outer" ref={outer}>
      <div
        className="sheet-zoom"
        style={{
          width: `${sheet.sheet.w * PX_PER_MM * zoom}px`,
          height: `${sheet.sheet.h * PX_PER_MM * zoom}px`,
        }}
      >
        <div
          className="sheet"
          style={{
            width: `${sheet.sheet.w}mm`,
            height: `${sheet.sheet.h}mm`,
            transform: `scale(${zoom})`,
          }}
        >
          {children}
        </div>
      </div>
    </div>
  );
}
