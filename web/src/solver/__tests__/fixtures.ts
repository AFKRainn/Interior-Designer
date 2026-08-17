/**
 * Specs produced by Python, read by the TypeScript solver.
 *
 * These are the drift guard for the hand-written TS spec types. Regenerate
 * with `python -m tests.export_fixtures`; the Python suite fails if they are
 * stale.
 */
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import type { Spec } from "../spec";

const here = dirname(fileURLToPath(import.meta.url));
export const REPO_ROOT = join(here, "..", "..", "..", "..");
const SPEC_DIR = join(REPO_ROOT, "tests", "golden", "specs");

export type FixtureName =
  | "straight"
  | "l_kitchen"
  | "u_kitchen"
  | "galley"
  | "four_walls"
  | "nightstand"
  | "long_run"
  | "two_doors";

/** The five layout shapes the view planner has to cope with (plan 7.3). */
export const LAYOUTS: FixtureName[] = [
  "straight",
  "l_kitchen",
  "u_kitchen",
  "galley",
  "four_walls",
];

export const ALL_FIXTURES: FixtureName[] = [
  ...LAYOUTS,
  "nightstand",
  "long_run",
  "two_doors",
];

export function loadSpec(name: FixtureName): Spec {
  return JSON.parse(readFileSync(join(SPEC_DIR, `${name}.json`), "utf-8")) as Spec;
}

export function loadJson<T>(...parts: string[]): T {
  return JSON.parse(readFileSync(join(REPO_ROOT, ...parts), "utf-8")) as T;
}
