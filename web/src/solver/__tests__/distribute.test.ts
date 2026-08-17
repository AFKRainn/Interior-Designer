/**
 * The TypeScript half of the shared sizing contract.
 *
 * Python runs the identical vectors in tests/test_distribute_golden.py. If
 * these two ever disagree, the editor and the server disagree about what the
 * drawing means -- the class of bug that build 1 shipped (plan 3.5).
 */
import { describe, expect, it } from "vitest";

import { distribute } from "../distribute";
import { loadJson } from "./fixtures";

interface GoldenCase {
  name: string;
  extent: number;
  children: { size?: number; flex?: number }[];
  expect: number[];
}

const golden = loadJson<{ cases: GoldenCase[] }>("tests", "golden", "distribute.json");

function toSizeable(child: { size?: number; flex?: number }) {
  return {
    size_cm: child.size ?? null,
    flex: child.size === undefined ? (child.flex ?? null) : null,
  };
}

describe("distribute matches the shared golden vectors", () => {
  for (const testCase of golden.cases) {
    it(testCase.name, () => {
      const sizes = distribute(testCase.children.map(toSizeable), testCase.extent);
      expect(sizes).toHaveLength(testCase.expect.length);
      sizes.forEach((size, index) => {
        expect(size).toBeCloseTo(testCase.expect[index], 3);
      });
    });
  }

  it("covers every case in the golden file", () => {
    expect(golden.cases.length).toBeGreaterThanOrEqual(10);
  });
});

describe("conservation", () => {
  it("sizes sum to the extent unless the fixed children oversubscribed it", () => {
    for (const testCase of golden.cases) {
      if (testCase.children.length === 0) continue;
      const children = testCase.children.map(toSizeable);
      const sizes = distribute(children, testCase.extent);
      const fixedTotal = children.reduce((sum, c) => sum + (c.size_cm ?? 0), 0);
      const total = sizes.reduce((sum, size) => sum + size, 0);
      expect(total).toBeCloseTo(Math.max(fixedTotal, testCase.extent), 2);
    }
  });
});
