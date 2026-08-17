/**
 * The server's surface.
 *
 * Note what is missing: there is no way to send a spec. Every change is an
 * op, which is why a misunderstanding can only ever be a rejected operation
 * and never a silently rewritten document.
 */

import type { Spec } from "./solver/spec";

export interface CameraJob {
  shot_id: string;
  camera: "inside_corner" | "frontal";
  walls: string[];
  frame: { left: string; right: string | null };
  exclude: string[];
  references: string[];
}

export interface Session {
  id: string;
  phase: "brief" | "brief_ready" | "edit" | "locked";
  locked: boolean;
  typology: string;
  brief: string | null;
  resolved: { field: string; value: string; source: string }[];
  intake: {
    response: string;
    status: string;
    open: { field: string; why: string; options: string[] }[];
    missing: string[];
    confidence: number;
  } | null;
  chat: { role: string; text: string; open?: unknown[]; ambiguities?: unknown[] }[];
  spec: Spec | null;
  can_undo: boolean;
  op_log: { op: Record<string, unknown>; version: number; note: string }[];
  sheets: string[];
  renders: {
    shot_id: string;
    camera: string;
    walls: string[];
    prompt: string;
    references: string[];
    data: string;
    mime_type: string;
  }[];
  render_error: string | null;
  versions: number[];
  cost: { total_cost?: number; total_calls?: number } | null;
}

export type Op = Record<string, unknown>;

export interface Preview {
  spec: Spec;
  diff: Record<string, "added" | "removed" | "changed">;
  summary: string;
}

export interface EditDecision {
  understanding: string;
  action: "clarify" | "propose";
  confidence: number;
  ambiguities: { question: string; options: string[] }[];
  targets: string[];
  ops: Op[];
  error: string;
  preview?: Preview;
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(path, options);
  const raw = await response.text();
  let body: unknown = null;
  if (raw) {
    try {
      body = JSON.parse(raw);
    } catch {
      body = null;
    }
  }
  if (!response.ok) {
    const detail = (body as { detail?: unknown } | null)?.detail;
    throw new Error(
      typeof detail === "string" ? detail : detail ? JSON.stringify(detail) : raw || response.statusText,
    );
  }
  return body as T;
}

const json = { "Content-Type": "application/json" };

function post<T>(path: string, body?: unknown): Promise<T> {
  return request<T>(path, {
    method: "POST",
    ...(body === undefined ? {} : { headers: json, body: JSON.stringify(body) }),
  });
}

export const api = {
  health: () => request<{ ok: boolean }>("/api/health"),
  create: () => post<Session>("/api/session"),
  demo: () => post<Session>("/api/session/demo"),
  get: (id: string) => request<Session>(`/api/session/${id}`),

  brief: (id: string, text: string, images: { data: string; mime_type: string }[] = []) =>
    post<Session>(`/api/session/${id}/brief`, { text, images }),
  buildSpec: (id: string) => post<Session>(`/api/session/${id}/spec/build`),

  ops: (id: string, ops: Op[]) => post<Session>(`/api/session/${id}/ops`, { ops }),
  preview: (id: string, ops: Op[]) => post<Preview>(`/api/session/${id}/ops/preview`, { ops }),
  edit: (id: string, utterance: string, wall_id: string | null, selection: string | null) =>
    post<{ session: Session; decision: EditDecision }>(`/api/session/${id}/edit`, {
      utterance,
      wall_id,
      selection,
    }),
  undo: (id: string) => post<Session>(`/api/session/${id}/undo`),

  shots: (id: string) =>
    request<{ elevations: { wall_id: string; label: string }[]; cameras: CameraJob[] }>(
      `/api/session/${id}/shots`,
    ),
  lock: (id: string, sheets: { name: string; data: string; wall_id: string | null }[]) =>
    post<Session>(`/api/session/${id}/lock`, { sheets }),
  renderAll: (id: string) => post<Session>(`/api/session/${id}/render`),
  renderShot: (id: string, shotId: string) => post<Session>(`/api/session/${id}/render/${shotId}`),
};
