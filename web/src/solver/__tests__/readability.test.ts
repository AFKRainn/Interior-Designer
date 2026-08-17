/**
 * THE PHASE 2 GATE (plan.txt, Phase 2).
 *
 * "A 40 cm nightstand and a 6 m run produce equally readable sheets."
 *
 * This is the test that build 1 would have failed. It declared 1 unit = 1 cm
 * and then annotated in the same units, so a 320 cm wall came out passable
 * and a 60 cm cabinet came out with lettering 14% of its own height and more
 * padding than object. Here annotation is a fixed number of millimetres and
 * only the geometry scales.
 */
import { describe, expect, it } from "vitest";

import { solveElevation } from "../elevation";
import { SCALE_LADDER } from "../scale";
import type { Sheet } from "../sheet";
import { ALL_FIXTURES, loadSpec } from "./fixtures";

/**
 * How much of the available paper the drawing occupies on its binding axis.
 *
 * The ladder's widest step is 2.5x (1:20 -> 1:50), so whenever an object was
 * too big for the previous scale it must fill at least 1/2.5 of this one.
 * The floor only fails to bind at 1:1, where nothing smaller is available --
 * that needs enlargement scales (2:1, 5:1) and is out of scope for furniture.
 */
function fill(sheet: Sheet): number {
  return Math.max(sheet.content.w / sheet.area.w, sheet.content.h / sheet.area.h);
}

const MIN_FILL = 0.39;

describe("a nightstand and a six metre run read the same", () => {
  const small = solveElevation(loadSpec("nightstand"), "wall-a");
  const large = solveElevation(loadSpec("long_run"), "wall-a");

  it("both pick a real drawing scale", () => {
    expect(SCALE_LADDER).toContain(small.scale as never);
    expect(SCALE_LADDER).toContain(large.scale as never);
    expect(small.scale).toBeLessThan(large.scale); // the small piece is drawn larger
  });

  it("both fill the sheet properly", () => {
    expect(fill(small)).toBeGreaterThan(MIN_FILL);
    expect(fill(large)).toBeGreaterThan(MIN_FILL);
  });

  it("annotation is the same physical size on both", () => {
    const sizes = (sheet: Sheet) => [...new Set(sheet.texts.map((t) => t.size))].sort();
    expect(sizes(small)).toEqual(sizes(large));
  });

  it("line weights are the same physical size on both", () => {
    const strokes = (sheet: Sheet) => [...new Set(sheet.boxes.map((b) => b.stroke))].sort();
    expect(strokes(small)).toEqual(strokes(large));
  });

  it("dimension text stays at 2.5 mm regardless of object size", () => {
    for (const sheet of [small, large]) {
      const dims = sheet.texts.filter((t) => t.id.endsWith("#t"));
      expect(dims.length).toBeGreaterThan(0);
      expect(dims.every((t) => t.size === 2.5)).toBe(true);
    }
  });

  it("reports the scale it used, so the drawing is measurable", () => {
    expect(small.texts.find((t) => t.id === "title-scale")!.value).toBe(
      `SCALE 1:${small.scale}`,
    );
    expect(large.texts.find((t) => t.id === "title-scale")!.value).toBe(
      `SCALE 1:${large.scale}`,
    );
  });
});

describe("every fixture produces a well-filled sheet", () => {
  for (const name of ALL_FIXTURES) {
    it(name, () => {
      const spec = loadSpec(name);
      for (const wall of spec.layout.walls) {
        const sheet = solveElevation(spec, wall.id);
        expect(fill(sheet), `${name}/${wall.id} fills only ${fill(sheet).toFixed(2)}`).toBeGreaterThan(MIN_FILL);
      }
    });
  }
});

describe("nothing spills off the page", () => {
  it("every drawn element stays inside the sheet", () => {
    for (const name of ALL_FIXTURES) {
      const spec = loadSpec(name);
      for (const wall of spec.layout.walls) {
        const sheet = solveElevation(spec, wall.id);
        for (const box of sheet.boxes) {
          expect(box.x, `${name}: ${box.id}`).toBeGreaterThanOrEqual(0);
          expect(box.y, `${name}: ${box.id}`).toBeGreaterThanOrEqual(0);
          expect(box.x + box.w, `${name}: ${box.id}`).toBeLessThanOrEqual(sheet.sheet.w);
          expect(box.y + box.h, `${name}: ${box.id}`).toBeLessThanOrEqual(sheet.sheet.h);
        }
        for (const text of sheet.texts) {
          expect(text.x, `${name}: ${text.id}`).toBeGreaterThanOrEqual(0);
          expect(text.y, `${name}: ${text.id}`).toBeLessThanOrEqual(sheet.sheet.h);
        }
        for (const line of sheet.lines) {
          for (const v of [line.x1, line.x2]) {
            expect(v, `${name}: ${line.id}`).toBeGreaterThanOrEqual(0);
            expect(v, `${name}: ${line.id}`).toBeLessThanOrEqual(sheet.sheet.w);
          }
          for (const v of [line.y1, line.y2]) {
            expect(v, `${name}: ${line.id}`).toBeGreaterThanOrEqual(0);
            expect(v, `${name}: ${line.id}`).toBeLessThanOrEqual(sheet.sheet.h);
          }
        }
      }
    }
  });
});
