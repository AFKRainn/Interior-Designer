/**
 * The selected node, and the ops that act on it (plan 9.2).
 *
 * Everything here emits the same operations the chat agent emits. There is
 * one way to change a spec and both hands use it.
 */
import { useEffect, useState } from "react";

import type { Op } from "../api";
import { round1 } from "../solver/dividers";
import type { Sheet } from "../solver/sheet";
import type { FrontType, Opening, Spec } from "../solver/spec";

const FRONTS: FrontType[] = [
  "door",
  "drawer",
  "open",
  "glass",
  "appliance",
  "panel",
  "false_front",
];

function findNode(spec: Spec, path: string): Opening | null {
  const parts = path.split("/").filter(Boolean);
  const wall = spec.walls.find((w) => w.id === parts[0]);
  if (!wall) return null;
  let group = wall.bays;
  let node: Opening | null = null;
  for (const segment of parts.slice(1)) {
    node = group.find((child) => child.id === segment) ?? null;
    if (!node) return null;
    group = node.children;
  }
  return node;
}

export function Inspector({
  spec,
  sheet,
  path,
  busy,
  onOps,
}: {
  spec: Spec;
  sheet: Sheet;
  path: string | null;
  busy: boolean;
  onOps: (ops: Op[], note: string) => void;
}) {
  const node = path ? findNode(spec, path) : null;
  const box = path ? sheet.boxes.find((b) => b.path === path && b.kind !== "front") : undefined;
  const [size, setSize] = useState("");

  const widthCm = box ? round1((box.w * sheet.scale) / 10) : 0;
  const heightCm = box ? round1((box.h * sheet.scale) / 10) : 0;
  const alongCols = node?.size_cm != null || node?.flex != null;

  useEffect(() => {
    if (!node) return;
    setSize(node.size_cm != null ? String(node.size_cm) : "");
  }, [path, node?.size_cm]);

  if (!path || !node) {
    return (
      <div className="inspector empty">
        <p>Click a bay or an opening on the drawing.</p>
        <p className="hint">
          Every part is labelled. You can say those names in the chat too — "bay 2",
          "the top row" — and the assistant answers in the same words.
        </p>
      </div>
    );
  }

  const isLeaf = node.split === null;

  return (
    <div className="inspector">
      <h3>{node.label || node.id}</h3>
      <code className="path">{path}</code>
      <p className="hint">
        {widthCm} × {heightCm} cm{node.flex != null ? " · flexible" : " · fixed"}
      </p>

      <form
        onSubmit={(event) => {
          event.preventDefault();
          const value = Number(size);
          if (!Number.isFinite(value) || value <= 0) return;
          onOps([{ kind: "set_size", path, size_cm: value }], `${node.id} → ${value} cm`);
        }}
      >
        <label>
          Size along its axis (cm)
          <input
            type="number"
            min="1"
            step="0.5"
            value={size}
            disabled={busy || !alongCols}
            placeholder={node.flex != null ? "flexible" : ""}
            onChange={(event) => setSize(event.target.value)}
          />
        </label>
        <div className="row">
          <button type="submit" disabled={busy || !size}>
            Set size
          </button>
          <button
            type="button"
            disabled={busy || node.flex != null}
            onClick={() => onOps([{ kind: "set_flex", path, flex: 1 }], `${node.id} → flexible`)}
          >
            Make flexible
          </button>
        </div>
      </form>

      <h4>Divide</h4>
      <div className="row">
        <button
          type="button"
          disabled={busy || !isLeaf}
          onClick={() =>
            onOps(
              [{ kind: "split", path, axis: "cols", count: 2 }],
              `${node.id} → two side by side`,
            )
          }
        >
          Two side by side
        </button>
        <button
          type="button"
          disabled={busy || !isLeaf}
          onClick={() =>
            onOps([{ kind: "split", path, axis: "rows", count: 2 }], `${node.id} → two stacked`)
          }
        >
          Two stacked
        </button>
      </div>
      <div className="row">
        <button
          type="button"
          disabled={busy || isLeaf}
          onClick={() => onOps([{ kind: "add_child", path }], `${node.id} → one more part`)}
        >
          Add a part
        </button>
        <button
          type="button"
          disabled={busy || isLeaf}
          onClick={() => onOps([{ kind: "merge", path }], `${node.id} → merged`)}
        >
          Merge back
        </button>
      </div>

      {isLeaf && (
        <>
          <h4>Front</h4>
          <select
            value={node.front?.type ?? "open"}
            disabled={busy}
            onChange={(event) =>
              onOps(
                [{ kind: "set_front", path, type: event.target.value }],
                `${node.id} → ${event.target.value}`,
              )
            }
          >
            {FRONTS.map((front) => (
              <option key={front} value={front}>
                {front.replace("_", " ")}
              </option>
            ))}
          </select>
          <div className="row">
            <button
              type="button"
              disabled={busy}
              onClick={() =>
                onOps(
                  [{ kind: "set_front", path, type: node.front?.type ?? "drawer", count: 3 }],
                  `${node.id} → three drawers`,
                )
              }
            >
              Make it a stack of 3
            </button>
          </div>
        </>
      )}

      <h4>Remove</h4>
      <button
        type="button"
        className="danger"
        disabled={busy}
        onClick={() => onOps([{ kind: "delete", path }], `deleted ${node.id}`)}
      >
        Delete {node.label || node.id}
      </button>
    </div>
  );
}
