/**
 * Preview generator and SVG smoke test.
 *
 * The assertions always run. Writing the SVG files is opt-in, because a test
 * suite should not have side effects by default:
 *
 *   WRITE_PREVIEWS=1 npx vitest run preview
 *
 * Output lands in data/preview/ for eyeballing the sheets before the real
 * editing renderer exists.
 */
import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import { sheetToSvg } from "../../render/SheetSVG";
import { solveElevation } from "../elevation";
import { solvePlan } from "../plan";
import { ALL_FIXTURES, REPO_ROOT, loadSpec } from "./fixtures";

const WRITE = Boolean(process.env.WRITE_PREVIEWS);
const OUT = join(REPO_ROOT, "data", "preview");

describe("SheetSVG", () => {
  it("renders every fixture to well-formed SVG", () => {
    if (WRITE) mkdirSync(OUT, { recursive: true });
    const report: string[] = [];

    for (const name of ALL_FIXTURES) {
      const spec = loadSpec(name);
      for (const wall of spec.layout.walls) {
        const sheet = solveElevation(spec, wall.id);
        const svg = sheetToSvg(sheet);

        expect(svg.startsWith("<svg")).toBe(true);
        expect(svg.trimEnd().endsWith("</svg>")).toBe(true);
        expect(svg).toContain(`viewBox="0 0 ${sheet.sheet.w} ${sheet.sheet.h}"`);
        expect(svg).toContain(`SCALE 1:${sheet.scale}`);
        expect(svg).not.toContain("NaN");
        expect(svg).not.toContain("undefined");

        const fillPct =
          Math.max(sheet.content.w / sheet.area.w, sheet.content.h / sheet.area.h) * 100;
        report.push(
          `${`${name}/${wall.id}`.padEnd(22)}1:${String(sheet.scale).padEnd(4)}` +
            `${sheet.content.w.toFixed(0)}x${sheet.content.h.toFixed(0)}mm`.padEnd(14) +
            `fill ${fillPct.toFixed(0)}%`.padEnd(11) +
            `boxes ${String(sheet.boxes.length).padStart(3)}  hits ${String(sheet.hits.length).padStart(2)}`,
        );
        if (WRITE) writeFileSync(join(OUT, `elev-${name}-${wall.id}.svg`), svg);
      }

      const plan = solvePlan(spec);
      const planSvg = sheetToSvg(plan);
      expect(planSvg).not.toContain("NaN");
      if (WRITE) writeFileSync(join(OUT, `plan-${name}.svg`), planSvg);
    }

    if (WRITE) console.log("\n" + report.join("\n") + "\n");
  });
});
