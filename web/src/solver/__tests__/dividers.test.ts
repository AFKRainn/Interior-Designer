import { describe, expect, it } from "vitest";

import { dividers, mmToCm } from "../dividers";
import { solveElevation } from "../elevation";
import { loadSpec } from "./fixtures";

describe("dividers", () => {
  const sheet = solveElevation(loadSpec("straight"), "wall-a");
  const found = dividers(sheet);

  it("sits between every pair of siblings", () => {
    const ids = found.map((d) => `${d.beforePath}->${d.afterPath}`).sort();
    expect(ids).toEqual([
      "wall-a/bay-1->wall-a/bay-2",
      "wall-a/bay-1/row-1->wall-a/bay-1/row-2",
      "wall-a/bay-2->wall-a/bay-3",
    ]);
  });

  it("knows which axis it moves along", () => {
    const bays = found.find((d) => d.beforePath === "wall-a/bay-1")!;
    const rows = found.find((d) => d.beforePath === "wall-a/bay-1/row-1")!;
    expect(bays.axis).toBe("cols");
    expect(rows.axis).toBe("rows");
  });

  it("reports the before-node's real size, so a drag starts from the truth", () => {
    expect(found.find((d) => d.beforePath === "wall-a/bay-1")!.beforeCm).toBe(100);
    expect(found.find((d) => d.beforePath === "wall-a/bay-1/row-1")!.beforeCm).toBe(60);
  });

  it("lands exactly on the drawn boundary", () => {
    const bay1 = sheet.boxes.find((b) => b.path === "wall-a/bay-1" && b.kind === "bay")!;
    const divider = found.find((d) => d.beforePath === "wall-a/bay-1")!;
    expect(divider.x + divider.w / 2).toBeCloseTo(bay1.x + bay1.w, 3);
  });

  it("converts paper millimetres back to model centimetres", () => {
    expect(mmToCm(10, 20)).toBe(20);
    expect(mmToCm(sheet.content.w, sheet.scale)).toBeCloseTo(300, 3);
  });

  it("a leaf has no dividers", () => {
    const leafOnly = solveElevation(loadSpec("galley"), "wall-b");
    expect(dividers(leafOnly)).toHaveLength(0);
  });
});
