/**
 * Renderer tests (plan 8).
 *
 * Rendered to static markup rather than a DOM, because the components carry
 * no state: everything they draw comes from a solved Sheet. What matters is
 * that they translate it faithfully and lose nothing addressable.
 */
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { solveElevation } from "../../solver/elevation";
import { solvePlan } from "../../solver/plan";
import { ALL_FIXTURES, loadSpec } from "../../solver/__tests__/fixtures";
import { ElevationDOM } from "../ElevationDOM";
import { PlanSVG } from "../PlanSVG";
import { sheetToSvg } from "../SheetSVG";

describe("ElevationDOM", () => {
  const sheet = solveElevation(loadSpec("two_doors"), "wall-a");
  const html = renderToStaticMarkup(<ElevationDOM sheet={sheet} />);

  it("gives every addressable node a real element", () => {
    for (const hit of sheet.hits) {
      expect(html, `missing element for ${hit.path}`).toContain(`data-path="${hit.path}"`);
    }
  });

  it("positions elements in real millimetres", () => {
    const carcass = sheet.boxes.find((box) => box.kind === "carcass")!;
    expect(html).toContain(`left:${carcass.x}mm`);
    expect(html).toContain(`width:${carcass.w}mm`);
    expect(html).toContain(`border-width:${carcass.stroke}mm`);
  });

  it("makes openings focusable and labelled for assistive tech", () => {
    expect(html).toContain('role="button"');
    expect(html).toContain('tabindex="0"');
    expect(html).toContain("wall-a/bay-1/row-1/col-1)");
  });

  it("marks the selected node", () => {
    const selected = renderToStaticMarkup(
      <ElevationDOM sheet={sheet} selectedPath="wall-a/bay-2" />,
    );
    expect(selected).toContain("is-selected");
    expect(selected).toContain('aria-pressed="true"');
  });

  it("marks a pending edit as a ghost preview", () => {
    const ghosted = renderToStaticMarkup(
      <ElevationDOM
        sheet={sheet}
        ghost={{
          "wall-a/bay-1/row-1/col-1": "added",
          "wall-a/bay-2": "removed",
          "wall-a/bay-3": "changed",
        }}
      />,
    );
    expect(ghosted).toContain("ghost-added");
    expect(ghosted).toContain("ghost-removed");
    expect(ghosted).toContain("ghost-changed");
  });

  it("draws every dimension line and every label", () => {
    for (const line of sheet.lines) {
      expect(html).toContain(`x1="${line.x1}"`);
    }
    expect(html).toContain(`SCALE 1:${sheet.scale}`);
  });
});

describe("PlanSVG", () => {
  const sheet = solvePlan(loadSpec("l_kitchen"));
  const html = renderToStaticMarkup(<PlanSVG sheet={sheet} />);

  it("uses the sheet itself as the viewBox", () => {
    expect(html).toContain(`viewBox="0 0 ${sheet.sheet.w} ${sheet.sheet.h}"`);
  });

  it("draws one footprint per wall and marks the corner", () => {
    expect(html).toContain("kind-footprint");
    expect(html).toContain("kind-corner");
    expect(html).toContain("stroke-dasharray");
  });

  it("announces the scale", () => {
    expect(html).toContain(`Plan, scale 1:${sheet.scale}`);
  });
});

describe("all three backends agree", () => {
  it("DOM, SVG export and hit list cover the same nodes", () => {
    for (const name of ALL_FIXTURES) {
      const spec = loadSpec(name);
      for (const wall of spec.layout.walls) {
        const sheet = solveElevation(spec, wall.id);
        const dom = renderToStaticMarkup(<ElevationDOM sheet={sheet} />);
        const svg = sheetToSvg(sheet);

        // one interactive element per hit, in both directions
        const domPaths = [...dom.matchAll(/data-path="([^"]+)"/g)].map((m) => m[1]);
        expect(new Set(domPaths)).toEqual(new Set(sheet.hits.map((h) => h.path)));

        // the export carries the same rectangles the editor shows
        for (const box of sheet.boxes) {
          expect(svg, `${name}: ${box.id} missing from export`).toContain(
            `x="${box.x}" y="${box.y}" width="${box.w}" height="${box.h}"`,
          );
        }
      }
    }
  });
});
