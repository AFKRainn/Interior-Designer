/**
 * The plan view (plan 8B).
 *
 * SVG rather than DOM because wall runs rotate, and CSS cannot express a
 * rotated footprint without a transform per element that would then fight
 * the solver's coordinates.
 */
import type { Sheet } from "../solver/sheet";

const FILL: Record<string, string> = {
  footprint: "var(--sheet-fill-footprint)",
  corner: "var(--sheet-fill-corner)",
};

export function PlanSVG({
  sheet,
  selectedWallId,
  onSelectWall,
}: {
  sheet: Sheet;
  selectedWallId?: string | null;
  onSelectWall?: (wallId: string) => void;
}) {
  return (
    <svg
      className="plan-svg"
      viewBox={`0 0 ${sheet.sheet.w} ${sheet.sheet.h}`}
      preserveAspectRatio="xMidYMid meet"
      role="img"
      aria-label={`Plan, scale 1:${sheet.scale}`}
    >
      <g stroke="currentColor" fill="none" vectorEffect="non-scaling-stroke">
        {sheet.boxes.map((box) => {
          const clickable = box.kind === "footprint" && box.path;
          return (
            <rect
              key={box.id}
              x={box.x}
              y={box.y}
              width={box.w}
              height={box.h}
              strokeWidth={box.stroke}
              fill={FILL[box.kind] ?? "none"}
              strokeDasharray={box.kind === "corner" ? "2 1.5" : undefined}
              className={[
                `kind-${box.kind}`,
                clickable ? "is-clickable" : "",
                selectedWallId && box.path === selectedWallId ? "is-selected" : "",
              ]
                .filter(Boolean)
                .join(" ")}
              onClick={clickable ? () => onSelectWall?.(box.path!) : undefined}
            />
          );
        })}
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
