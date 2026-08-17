/** The scale ladder (plan 6.2) — the fix for build-1 bug 3.2. */
import { describe, expect, it } from "vitest";

import { SCALE_LADDER, chooseScale, fitInto, fmtCm, toPaper } from "../scale";

describe("scale ladder", () => {
  it("is the ISO 5455 preferred set", () => {
    expect([...SCALE_LADDER]).toEqual([1, 2, 5, 10, 20, 50, 100]);
  });

  it("converts model cm to paper mm", () => {
    expect(toPaper(300, 10)).toBe(300); // 3 m at 1:10 is 300 mm of paper
    expect(toPaper(300, 20)).toBe(150);
    expect(toPaper(40, 1)).toBe(400);
  });

  it("picks the largest scale that still fits", () => {
    // 300x200 cm is 300x200 mm at 1:10, which fits a 366x211 area
    expect(chooseScale(300, 200, 366, 211)).toBe(10);
    // 10 mm taller and the height no longer fits, so it drops a rung
    expect(chooseScale(300, 212, 366, 211)).toBe(20);
    expect(chooseScale(30, 20, 366, 211)).toBe(1);
    expect(chooseScale(600, 240, 366, 211)).toBe(20);
  });

  it("never invents an off-ladder scale", () => {
    for (let w = 20; w <= 900; w += 17) {
      for (let h = 20; h <= 300; h += 13) {
        expect(SCALE_LADDER).toContain(chooseScale(w, h, 366, 211) as never);
      }
    }
  });

  it("falls back to the smallest scale rather than overflowing silently", () => {
    expect(chooseScale(100000, 100000, 366, 211)).toBe(100);
  });
});

describe("fitInto", () => {
  const area = { x: 27, y: 18, w: 366, h: 211 };

  it("centres the scaled content in the available area", () => {
    const { scale, content } = fitInto(300, 200, area);
    expect(scale).toBe(10);
    expect(content.w).toBeCloseTo(300, 3);
    expect(content.h).toBeCloseTo(200, 3);
    expect(content.x).toBeCloseTo(area.x + (area.w - 300) / 2, 3);
    expect(content.y).toBeCloseTo(area.y + (area.h - 200) / 2, 3);
  });

  it("keeps content inside the area for a wide range of objects", () => {
    for (const [w, h] of [[40, 50], [300, 220], [600, 240], [120, 90], [900, 260]]) {
      const { content } = fitInto(w, h, area);
      expect(content.x).toBeGreaterThanOrEqual(area.x - 0.001);
      expect(content.y).toBeGreaterThanOrEqual(area.y - 0.001);
      expect(content.x + content.w).toBeLessThanOrEqual(area.x + area.w + 0.001);
      expect(content.y + content.h).toBeLessThanOrEqual(area.y + area.h + 0.001);
    }
  });
});

describe("dimension text", () => {
  it("prints whole centimetres unless the value really is fractional", () => {
    expect(fmtCm(80)).toBe("80");
    expect(fmtCm(80.02)).toBe("80");
    expect(fmtCm(66.6667)).toBe("66.7");
  });
});
