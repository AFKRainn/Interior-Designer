/**
 * Properties that must hold for ANY spec (plan 7.3).
 *
 * Golden files catch regressions in known cases; these catch whole classes of
 * bug. Every one of them corresponds to something build 1 got wrong.
 */
import { describe, expect, it } from "vitest";

import { solveElevation } from "../elevation";
import { solvePlan } from "../plan";
import { SCALE_LADDER } from "../scale";
import type { Box, Sheet } from "../sheet";
import type { FrontType, Opening, Spec } from "../spec";
import { ALL_FIXTURES, loadSpec } from "./fixtures";

const EPS = 0.02; // mm

/** Deterministic PRNG so a failure is always reproducible from its seed. */
function makeRng(seed: number): () => number {
  let state = seed >>> 0;
  return () => {
    state = (Math.imul(state, 1664525) + 1013904223) >>> 0;
    return state / 4294967296;
  };
}

const FRONTS: FrontType[] = ["door", "drawer", "open", "glass", "appliance", "panel"];

function randomNode(rng: () => number, id: string, depth: number): Opening {
  const leaf = depth >= 3 || rng() < 0.45;
  if (leaf) {
    return {
      id,
      label: "",
      size_cm: null,
      flex: 1,
      split: null,
      children: [],
      front: {
        type: FRONTS[Math.floor(rng() * FRONTS.length)],
        hinge: rng() < 0.5 ? "left" : "right",
        handle: rng() < 0.3 ? "none" : "bar",
        count: 1,
      },
    };
  }
  const axis = rng() < 0.5 ? "rows" : "cols";
  const count = 2 + Math.floor(rng() * 3);
  const prefix = axis === "rows" ? "row" : "col";
  return {
    id,
    label: "",
    size_cm: null,
    flex: 1,
    split: axis,
    children: Array.from({ length: count }, (_, i) =>
      randomNode(rng, `${prefix}-${i + 1}`, depth + 1),
    ),
    front: null,
  };
}

/** All-flex specs, so every generated document is valid by construction. */
function randomSpec(seed: number): Spec {
  const rng = makeRng(seed);
  const length = 40 + Math.floor(rng() * 560);
  const height = 40 + Math.floor(rng() * 220);
  const cornice = Math.floor(rng() * 11);
  const plinth = Math.floor(rng() * 16);
  const bayCount = 1 + Math.floor(rng() * 4);
  const side = rng() < 0.4 ? Math.floor(rng() * 9) : 0;

  return {
    project_id: `rand-${seed}`,
    version: 1,
    units: "cm",
    name: `Random ${seed}`,
    layout: {
      type: "straight",
      walls: [
        {
          id: "wall-a",
          label: "Wall A",
          length,
          adjacent_to: [],
          faces: [],
          sequence: 0,
          corner: { start: null, end: null },
        },
      ],
    },
    walls: [
      {
        id: "wall-a",
        height,
        depth: 30 + Math.floor(rng() * 40),
        reveal_mm: 3,
        cornice: { type: "straight", height: cornice },
        plinth: { type: "recessed", height: plinth },
        side_columns: { left_cm: side, right_cm: side, detail: "plain" },
        bays: Array.from({ length: bayCount }, (_, i) => randomNode(rng, `bay-${i + 1}`, 0)),
      },
    ],
    materials: { carcass: "", doors: "", finish: "" },
    hardware: { style: "", placement: "" },
    brief: "",
    assumptions: [],
    render_notes: "",
  };
}

const TREE_KINDS = new Set(["carcass", "bay", "opening"]);

function treeBoxes(sheet: Sheet): Map<string, Box> {
  const map = new Map<string, Box>();
  for (const box of sheet.boxes) {
    if (box.path && TREE_KINDS.has(box.kind)) map.set(box.path, box);
  }
  return map;
}

function parentPath(path: string): string | null {
  const cut = path.lastIndexOf("/");
  return cut < 0 ? null : path.slice(0, cut);
}

function checkSheet(sheet: Sheet, label: string): void {
  // scale is always on the ladder
  expect(SCALE_LADDER, `${label}: off-ladder scale`).toContain(sheet.scale as never);

  // content stays inside the area reserved for it, which is inside the sheet
  expect(sheet.content.x, label).toBeGreaterThanOrEqual(sheet.area.x - EPS);
  expect(sheet.content.y, label).toBeGreaterThanOrEqual(sheet.area.y - EPS);
  expect(sheet.content.x + sheet.content.w, label).toBeLessThanOrEqual(
    sheet.area.x + sheet.area.w + EPS,
  );
  expect(sheet.content.y + sheet.content.h, label).toBeLessThanOrEqual(
    sheet.area.y + sheet.area.h + EPS,
  );

  const boxes = treeBoxes(sheet);

  // every child sits inside its parent
  for (const [path, box] of boxes) {
    const parentKey = parentPath(path);
    if (!parentKey) continue;
    const parent = boxes.get(parentKey);
    if (!parent) continue;
    expect(box.x, `${label}: ${path} escapes ${parentKey} on the left`).toBeGreaterThanOrEqual(parent.x - EPS);
    expect(box.y, `${label}: ${path} escapes ${parentKey} on top`).toBeGreaterThanOrEqual(parent.y - EPS);
    expect(box.x + box.w, `${label}: ${path} escapes ${parentKey} on the right`).toBeLessThanOrEqual(parent.x + parent.w + EPS);
    expect(box.y + box.h, `${label}: ${path} escapes ${parentKey} below`).toBeLessThanOrEqual(parent.y + parent.h + EPS);
  }

  // children exactly tile their parent: contained + equal total area means no
  // overlap and no gap, whichever axis the split used
  const groups = new Map<string, Box[]>();
  for (const [path, box] of boxes) {
    const parentKey = parentPath(path);
    if (!parentKey) continue;
    const parent = boxes.get(parentKey);
    if (!parent || parent.kind === "carcass") continue; // bays do not tile the trim
    groups.set(parentKey, [...(groups.get(parentKey) ?? []), box]);
  }
  for (const [parentKey, children] of groups) {
    const parent = boxes.get(parentKey)!;
    const area = parent.w * parent.h;
    const childArea = children.reduce((sum, child) => sum + child.w * child.h, 0);
    expect(
      Math.abs(childArea - area) / Math.max(area, 1),
      `${label}: children of ${parentKey} do not tile it`,
    ).toBeLessThan(1e-3);
  }

  // fronts stay inside their own opening
  for (const box of sheet.boxes) {
    if (box.kind !== "front" || !box.path) continue;
    const opening = boxes.get(box.path);
    if (!opening) continue;
    expect(box.x, `${label}: front escapes ${box.path}`).toBeGreaterThanOrEqual(opening.x - EPS);
    expect(box.x + box.w, label).toBeLessThanOrEqual(opening.x + opening.w + EPS);
    expect(box.y, label).toBeGreaterThanOrEqual(opening.y - EPS);
    expect(box.y + box.h, label).toBeLessThanOrEqual(opening.y + opening.h + EPS);
  }

  // every hit matches a drawn box exactly (build-1 bug 3.5)
  for (const hit of sheet.hits) {
    const box = sheet.boxes.find((b) => b.path === hit.path && TREE_KINDS.has(b.kind) || (b.kind === "footprint" && b.path === hit.path));
    expect(box, `${label}: hit ${hit.path} has no box`).toBeDefined();
    expect(hit.x, `${label}: hit ${hit.path} x`).toBeCloseTo(box!.x, 3);
    expect(hit.y, `${label}: hit ${hit.path} y`).toBeCloseTo(box!.y, 3);
    expect(hit.w, `${label}: hit ${hit.path} w`).toBeCloseTo(box!.w, 3);
    expect(hit.h, `${label}: hit ${hit.path} h`).toBeCloseTo(box!.h, 3);
  }
}

describe("elevation properties hold for the fixtures", () => {
  for (const name of ALL_FIXTURES) {
    it(name, () => {
      const spec = loadSpec(name);
      for (const wall of spec.layout.walls) {
        checkSheet(solveElevation(spec, wall.id), `${name}/${wall.id}`);
      }
    });
  }
});

describe("plan properties hold for the fixtures", () => {
  for (const name of ALL_FIXTURES) {
    it(name, () => {
      checkSheet(solvePlan(loadSpec(name)), `plan/${name}`);
    });
  }
});

describe("elevation properties hold for 200 random specs", () => {
  it("no overflow, no gaps, no orphan hit targets", () => {
    for (let seed = 1; seed <= 200; seed += 1) {
      const spec = randomSpec(seed);
      checkSheet(solveElevation(spec, "wall-a"), `seed ${seed}`);
    }
  });
});
