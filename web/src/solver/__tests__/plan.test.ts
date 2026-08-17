/** Plan solve and corner resolution (plan 7.2) — the fix for bug 3.4. */
import { describe, expect, it } from "vitest";

import { placeWalls, solvePlan } from "../plan";
import { SCALE_LADDER } from "../scale";
import { LAYOUTS, loadSpec } from "./fixtures";
import type { Footprint } from "../plan";

function overlapArea(a: Footprint, b: Footprint): number {
  const w = Math.min(a.maxX, b.maxX) - Math.max(a.minX, b.minX);
  const h = Math.min(a.maxY, b.maxY) - Math.max(a.minY, b.minY);
  return w > 0 && h > 0 ? w * h : 0;
}

describe("corners are counted once", () => {
  it("two 60 cm runs do not occupy the same square", () => {
    // Build 1 produced a 3600 cm2 overlap here and counted it in both walls.
    const footprints = placeWalls(loadSpec("l_kitchen"));
    expect(footprints).toHaveLength(2);
    expect(overlapArea(footprints[0], footprints[1])).toBe(0);
  });

  it("no two walls overlap in any layout", () => {
    for (const name of LAYOUTS) {
      const footprints = placeWalls(loadSpec(name));
      for (let i = 0; i < footprints.length; i += 1) {
        for (let j = i + 1; j < footprints.length; j += 1) {
          expect(
            overlapArea(footprints[i], footprints[j]),
            `${name}: ${footprints[i].wallId} overlaps ${footprints[j].wallId}`,
          ).toBe(0);
        }
      }
    }
  });

  it("the yielding wall starts after its neighbour's depth", () => {
    const [a, b] = placeWalls(loadSpec("l_kitchen"));
    expect(a.length).toBe(320); // takes the corner, keeps its full run
    expect(b.length).toBe(180); // yields 60 cm to wall-a
    // wall-b's run begins 60 cm along, leaving the corner square to wall-a
    expect(b.runStart[1] - b.origin[1]).toBeCloseTo(60, 6);
  });

  it("marks the corner square on the wall that owns it", () => {
    const sheet = solvePlan(loadSpec("l_kitchen"));
    const corner = sheet.boxes.find((box) => box.kind === "corner");
    expect(corner).toBeDefined();
    expect(corner!.id).toBe("wall-a#corner");
    expect(corner!.label).toBe("corner with wall-b");
  });

  it("resolves the wrap-around corner in a four-wall ring", () => {
    const footprints = placeWalls(loadSpec("four_walls"));
    expect(footprints.map((f) => f.length)).toEqual([340, 240, 340, 240]);
  });
});

describe("facing runs", () => {
  it("places a galley across an aisle, not adjacent", () => {
    const [a, b] = placeWalls(loadSpec("galley"));
    expect(overlapArea(a, b)).toBe(0);
    expect(a.length).toBe(320);
    expect(b.length).toBe(320);
    // fronts look at each other across the aisle
    expect(b.minY - a.maxY).toBeCloseTo(120, 6);
  });
});

describe("plan sheet", () => {
  const sheet = solvePlan(loadSpec("u_kitchen"));

  it("draws one footprint per wall, each addressable", () => {
    const footprints = sheet.boxes.filter((box) => box.kind === "footprint");
    expect(footprints.map((box) => box.path).sort()).toEqual([
      "wall-a",
      "wall-b",
      "wall-c",
    ]);
    expect(sheet.hits).toHaveLength(3);
  });

  it("dimensions every run", () => {
    for (const wallId of ["wall-a", "wall-b", "wall-c"]) {
      expect(sheet.lines.some((line) => line.id === `${wallId}#dim`)).toBe(true);
    }
  });

  it("marks internal bay dividers", () => {
    expect(sheet.lines.filter((line) => line.kind === "divider").length).toBeGreaterThan(0);
  });

  it("uses a ladder scale and stays inside the drawing area", () => {
    expect(SCALE_LADDER).toContain(sheet.scale as never);
    expect(sheet.content.x).toBeGreaterThanOrEqual(sheet.drawing.x);
    expect(sheet.content.y).toBeGreaterThanOrEqual(sheet.drawing.y);
    expect(sheet.content.x + sheet.content.w).toBeLessThanOrEqual(
      sheet.drawing.x + sheet.drawing.w,
    );
    expect(sheet.content.y + sheet.content.h).toBeLessThanOrEqual(
      sheet.drawing.y + sheet.drawing.h,
    );
  });
});
