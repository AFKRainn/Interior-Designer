/**
 * The editing surface: an elevation as real DOM nodes (plan 8A).
 *
 * Every opening is an element carrying data-path, so selection, hover,
 * keyboard focus and ghost previews are browser behaviour rather than
 * geometry code. Build 1 kept a parallel hit-map in Python and it drifted
 * off the drawing (bug 3.5); here a hit target IS the drawn box.
 *
 * IMPORTANT: CSS does not lay this out. The solver already produced absolute
 * millimetre rectangles, and these divs are positioned at those numbers. Two
 * layout engines disagreeing is the bug this whole build exists to kill, so
 * the browser is a renderer here, not a calculator (progress D17).
 */
import { useRef, useState } from "react";
import type { KeyboardEvent, PointerEvent as ReactPointerEvent } from "react";

import { dividers, mmToCm, round1 } from "../solver/dividers";
import type { Box, Sheet } from "../solver/sheet";
import { Annotations } from "./Annotations";

export type GhostState = Record<string, "added" | "removed" | "changed">;

export interface ElevationDOMProps {
  sheet: Sheet;
  selectedPath?: string | null;
  /** Paths marked by a pending edit, for the before/after preview. */
  ghost?: GhostState;
  onSelect?: (path: string) => void;
  /** Dragging a divider pins the size of the node before it. */
  onResize?: (path: string, sizeCm: number) => void;
  readOnly?: boolean;
}

/** Kinds the user can actually click. */
const INTERACTIVE = new Set(["bay", "opening"]);
/** Drawn behind the interactive layer. */
const BACKDROP = new Set(["frame", "title-block", "carcass", "cornice", "plinth", "side-column"]);

function style(box: Box): React.CSSProperties {
  return {
    left: `${box.x}mm`,
    top: `${box.y}mm`,
    width: `${box.w}mm`,
    height: `${box.h}mm`,
    borderWidth: `${box.stroke}mm`,
  };
}

export function ElevationDOM({
  sheet,
  selectedPath,
  ghost,
  onSelect,
  onResize,
  readOnly = false,
}: ElevationDOMProps) {
  const root = useRef<HTMLDivElement>(null);
  const [drag, setDrag] = useState<{ path: string; startCm: number; live: number } | null>(null);

  const backdrop = sheet.boxes.filter((box) => BACKDROP.has(box.kind));
  const openings = sheet.boxes.filter((box) => INTERACTIVE.has(box.kind));
  const fronts = sheet.boxes.filter((box) => box.kind === "front" || box.kind === "handle");
  const handles = readOnly || !onResize ? [] : dividers(sheet);

  function activate(path: string) {
    onSelect?.(path);
  }

  /** Screen pixels per paper millimetre, measured rather than assumed. */
  function pxPerMm(): number {
    const rect = root.current?.getBoundingClientRect();
    return rect && rect.width > 0 ? rect.width / sheet.sheet.w : 1;
  }

  function startDrag(
    event: ReactPointerEvent<HTMLDivElement>,
    divider: { beforePath: string; beforeCm: number; axis: "rows" | "cols" },
  ) {
    event.preventDefault();
    event.currentTarget.setPointerCapture(event.pointerId);
    const origin = divider.axis === "cols" ? event.clientX : event.clientY;
    const ratio = pxPerMm();

    const move = (moveEvent: PointerEvent) => {
      const now = divider.axis === "cols" ? moveEvent.clientX : moveEvent.clientY;
      const deltaCm = mmToCm((now - origin) / ratio, sheet.scale);
      setDrag({
        path: divider.beforePath,
        startCm: divider.beforeCm,
        live: Math.max(1, round1(divider.beforeCm + deltaCm)),
      });
    };
    const finish = (upEvent: PointerEvent) => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", finish);
      const now = divider.axis === "cols" ? upEvent.clientX : upEvent.clientY;
      const deltaCm = mmToCm((now - origin) / ratio, sheet.scale);
      const next = Math.max(1, round1(divider.beforeCm + deltaCm));
      setDrag(null);
      if (Math.abs(next - divider.beforeCm) >= 0.5) onResize?.(divider.beforePath, next);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", finish);
  }

  function onKey(event: KeyboardEvent<HTMLDivElement>, path: string) {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      activate(path);
    }
  }

  return (
    <div className="elevation" ref={root}>
      {backdrop.map((box) => (
        <div key={box.id} className={`sheet-box kind-${box.kind}`} style={style(box)} />
      ))}

      {fronts.map((box) => (
        <div
          key={box.id}
          className={`sheet-box kind-${box.kind}${box.front ? ` front-${box.front}` : ""}`}
          style={style(box)}
        />
      ))}

      {openings.map((box) => {
        const path = box.path!;
        const mark = ghost?.[path];
        const classes = [
          "sheet-node",
          `kind-${box.kind}`,
          selectedPath === path ? "is-selected" : "",
          mark ? `ghost-${mark}` : "",
        ]
          .filter(Boolean)
          .join(" ");
        return (
          <div
            key={box.id}
            className={classes}
            style={style(box)}
            data-path={path}
            data-kind={box.kind}
            role="button"
            tabIndex={0}
            aria-label={`${box.label ?? path} (${path})`}
            aria-pressed={selectedPath === path}
            onClick={(event) => {
              // innermost opening wins, so clicking a drawer does not select its bay
              event.stopPropagation();
              activate(path);
            }}
            onKeyDown={(event) => onKey(event, path)}
          />
        );
      })}

      {handles.map((divider) => (
        <div
          key={divider.id}
          className={`sheet-divider axis-${divider.axis}`}
          style={{
            left: `${divider.x}mm`,
            top: `${divider.y}mm`,
            width: `${divider.w}mm`,
            height: `${divider.h}mm`,
          }}
          role="separator"
          aria-label={`Resize ${divider.beforePath}`}
          aria-orientation={divider.axis === "cols" ? "vertical" : "horizontal"}
          onPointerDown={(event) => startDrag(event, divider)}
        />
      ))}

      {drag && (
        <div className="drag-readout">
          {drag.path.split("/").pop()} · {drag.live} cm
        </div>
      )}

      <Annotations sheet={sheet} />
    </div>
  );
}
