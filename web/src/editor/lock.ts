/**
 * Locking: rasterise exactly what the user approved, then upload it.
 *
 * The planner decides which sheets exist; the browser only renders them. So
 * the reference images the image model receives are pixel-for-pixel the
 * drawings that were on screen when the user pressed Lock.
 */

import { api } from "../api";
import type { Session } from "../api";
import { rasterizeSheet } from "../render/rasterize";
import type { RasterSheet } from "../render/rasterize";
import { solveElevation } from "../solver/elevation";
import { solvePlan } from "../solver/plan";
import type { Spec } from "../solver/spec";

export async function lockDrawings(
  sessionId: string,
  spec: Spec,
  onProgress?: (message: string) => void,
): Promise<Session> {
  const plan = await api.shots(sessionId);
  const sheets: RasterSheet[] = [];

  for (const job of plan.elevations) {
    onProgress?.(`Rendering ${job.wall_id}…`);
    sheets.push(
      await rasterizeSheet(solveElevation(spec, job.wall_id), `elev-${job.wall_id}.png`),
    );
  }

  for (const shot of plan.cameras) {
    onProgress?.(`Rendering plan for ${shot.shot_id}…`);
    const sheet = solvePlan(spec, undefined, {
      highlight: shot.walls,
      label: `${shot.shot_id} (${shot.walls.join(" + ")})`,
    });
    sheets.push(await rasterizeSheet(sheet, `plan-${shot.shot_id}.png`));
  }

  onProgress?.("Uploading…");
  return api.lock(sessionId, sheets);
}
