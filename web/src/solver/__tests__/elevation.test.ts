/** Elevation solve (plan 7.1). */
import { describe, expect, it } from "vitest";

import { solveElevation } from "../elevation";
import { SCALE_LADDER } from "../scale";
import { A3_LANDSCAPE, TEXT_MM } from "../sheet";
import type { Box, Sheet } from "../sheet";
import { LAYOUTS, loadSpec } from "./fixtures";

const byId = (sheet: Sheet, id: string): Box | undefined =>
  sheet.boxes.find((box) => box.id === id);

const byPath = (sheet: Sheet, path: string): Box | undefined =>
  sheet.boxes.find((box) => box.path === path && box.kind !== "front");

describe("the two-doors case, drawn", () => {
  /**
   * Build 1 could not represent this at all (plan 3.1). Phase 1 made it one
   * op; this checks it actually reaches the paper as two fronts side by side.
   */
  const sheet = solveElevation(loadSpec("two_doors"), "wall-a");

  it("draws two door fronts at the same height, splitting the width", () => {
    const left = sheet.boxes.find((b) => b.id === "wall-a/bay-1/row-1/col-1#front");
    const right = sheet.boxes.find((b) => b.id === "wall-a/bay-1/row-1/col-2#front");
    expect(left).toBeDefined();
    expect(right).toBeDefined();
    expect(left!.front).toBe("door");
    expect(right!.front).toBe("door");

    expect(left!.y).toBeCloseTo(right!.y, 3);
    expect(left!.h).toBeCloseTo(right!.h, 3);
    expect(left!.w).toBeCloseTo(right!.w, 3);
    expect(right!.x).toBeGreaterThan(left!.x);
  });

  it("separates the pair by one reveal", () => {
    const left = sheet.boxes.find((b) => b.id === "wall-a/bay-1/row-1/col-1#front")!;
    const right = sheet.boxes.find((b) => b.id === "wall-a/bay-1/row-1/col-2#front")!;
    // 3 mm reveal at 1:20 is 0.15 mm of paper between the two fronts
    const gap = right.x - (left.x + left.w);
    expect(gap).toBeCloseTo((3 / 10) * (10 / sheet.scale), 3);
  });

  it("hinges the pair outward, so both handles meet in the middle", () => {
    const handles = sheet.boxes.filter(
      (b) => b.kind === "handle" && b.id.startsWith("wall-a/bay-1/row-1/col-"),
    );
    expect(handles).toHaveLength(2);

    const left = sheet.boxes.find((b) => b.id === "wall-a/bay-1/row-1/col-1#front")!;
    const right = sheet.boxes.find((b) => b.id === "wall-a/bay-1/row-1/col-2#front")!;
    const middle = (left.x + right.x + right.w) / 2;
    const span = right.x + right.w - left.x;

    // a left-hinged door carries its handle on the right and vice versa, so
    // both land within the middle fifth of the pair
    for (const handle of handles) {
      expect(Math.abs(handle.x + handle.w / 2 - middle)).toBeLessThan(span / 10);
    }
  });
});

describe("carcass and trim", () => {
  const spec = loadSpec("straight");
  const sheet = solveElevation(spec, "wall-a");

  it("draws the carcass at the usable run by the wall height", () => {
    const carcass = byId(sheet, "wall-a")!;
    expect(carcass.kind).toBe("carcass");
    expect(carcass.w).toBeCloseTo((300 * 10) / sheet.scale, 3);
    expect(carcass.h).toBeCloseTo((220 * 10) / sheet.scale, 3);
  });

  it("puts the cornice at the top and the plinth at the bottom", () => {
    const carcass = byId(sheet, "wall-a")!;
    const cornice = byId(sheet, "wall-a#cornice")!;
    const plinth = byId(sheet, "wall-a#plinth")!;
    expect(cornice.y).toBeCloseTo(carcass.y, 3);
    expect(plinth.y + plinth.h).toBeCloseTo(carcass.y + carcass.h, 3);
  });

  it("lays the bays out between the trim bands, left to right", () => {
    const bays = ["bay-1", "bay-2", "bay-3"].map((id) => byPath(sheet, `wall-a/${id}`)!);
    const cornice = byId(sheet, "wall-a#cornice")!;
    for (const bay of bays) {
      expect(bay.y).toBeCloseTo(cornice.y + cornice.h, 3);
    }
    expect(bays[1].x).toBeGreaterThan(bays[0].x);
    expect(bays[2].x).toBeGreaterThan(bays[1].x);
    // bay-3 is flex and takes the 100 cm the two fixed bays leave
    expect(bays[2].w).toBeCloseTo((100 * 10) / sheet.scale, 3);
  });

  it("uses the ISO line weight ladder", () => {
    expect(byId(sheet, "wall-a")!.stroke).toBe(0.7);
    expect(byPath(sheet, "wall-a/bay-1")!.stroke).toBe(0.35);
    expect(sheet.boxes.find((b) => b.kind === "front")!.stroke).toBe(0.25);
    expect(sheet.lines.every((line) => line.stroke === 0.18)).toBe(true);
  });
});

describe("side columns", () => {
  it("occupy real width instead of overlapping the bays (progress D9)", () => {
    const sheet = solveElevation(loadSpec("long_run"), "wall-a");
    const left = byId(sheet, "wall-a#side-left")!;
    const firstBay = byPath(sheet, "wall-a/bay-1")!;
    expect(left.x + left.w).toBeCloseTo(firstBay.x, 3);
  });
});

describe("annotation", () => {
  const sheet = solveElevation(loadSpec("straight"), "wall-a");

  it("dimensions every bay plus the overall width", () => {
    const values = sheet.texts.filter((t) => t.id.endsWith("#t")).map((t) => t.value);
    expect(values).toContain("300"); // overall
    expect(values).toContain("100"); // each bay
    expect(values).toContain("220"); // height
  });

  it("puts detail dimensions nearer the object than the overall", () => {
    const detail = sheet.lines.find((l) => l.id === "dim-bay-1#d")!;
    const overall = sheet.lines.find((l) => l.id === "dim-overall#d")!;
    expect(detail.y1).toBeLessThan(overall.y1);
  });

  it("dimensions the cornice and plinth when they exist", () => {
    expect(sheet.lines.some((l) => l.id === "dim-cornice#d")).toBe(true);
    expect(sheet.lines.some((l) => l.id === "dim-plinth#d")).toBe(true);
  });

  it("keeps annotation at fixed ISO 3098 heights", () => {
    const sizes = new Set(sheet.texts.map((t) => t.size));
    for (const size of sizes) {
      expect([TEXT_MM.dimension, TEXT_MM.label, TEXT_MM.title]).toContain(size);
    }
  });

  it("carries a title block naming the scale", () => {
    const scaleText = sheet.texts.find((t) => t.id === "title-scale")!;
    expect(scaleText.value).toBe(`SCALE 1:${sheet.scale}`);
  });
});

describe("every layout solves", () => {
  for (const name of LAYOUTS) {
    it(`${name} produces a sheet per wall`, () => {
      const spec = loadSpec(name);
      for (const wall of spec.layout.walls) {
        const sheet = solveElevation(spec, wall.id);
        expect(SCALE_LADDER).toContain(sheet.scale as never);
        expect(sheet.boxes.length).toBeGreaterThan(3);
        expect(sheet.hits.length).toBeGreaterThan(0);
        expect(sheet.sheet).toEqual({ w: A3_LANDSCAPE.w, h: A3_LANDSCAPE.h });
      }
    });
  }
});
