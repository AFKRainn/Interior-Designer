/**
 * The annotation layer: dimension lines, witness lines and lettering.
 *
 * SVG rather than DOM, because rotated text and hairlines are exactly what
 * SVG is for and exactly what CSS is bad at. It sits on top of the
 * interactive geometry and never intercepts a click.
 *
 * Coordinates are the Sheet's own millimetres — the viewBox IS the sheet, so
 * nothing here recomputes anything.
 */
import type { Sheet } from "../solver/sheet";

export function Annotations({ sheet }: { sheet: Sheet }) {
  return (
    <svg
      className="sheet-annotations"
      viewBox={`0 0 ${sheet.sheet.w} ${sheet.sheet.h}`}
      preserveAspectRatio="xMidYMid meet"
      aria-hidden="true"
    >
      <g stroke="currentColor" fill="none" vectorEffect="non-scaling-stroke">
        {sheet.lines.map((line) => (
          <line
            key={line.id}
            x1={line.x1}
            y1={line.y1}
            x2={line.x2}
            y2={line.y2}
            strokeWidth={line.stroke}
          />
        ))}
      </g>
      <g fill="currentColor" stroke="none">
        {sheet.texts.map((text) => (
          <text
            key={text.id}
            x={text.x}
            y={text.y}
            fontSize={text.size}
            textAnchor={text.anchor}
            transform={text.rotate ? `rotate(${text.rotate} ${text.x} ${text.y})` : undefined}
          >
            {text.value}
          </text>
        ))}
      </g>
    </svg>
  );
}
