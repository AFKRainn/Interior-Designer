/**
 * The editor (plan 9).
 *
 * Drawings are solved here, in the browser, from the spec the server holds.
 * Direct manipulation and chat both end up emitting the same operations, and
 * no change reaches the spec without being drawn first.
 */
import { useEffect, useMemo, useState } from "react";

import { api } from "../api";
import type { EditDecision, Op, Preview, Session } from "../api";
import { ElevationDOM } from "../render/ElevationDOM";
import type { GhostState } from "../render/ElevationDOM";
import { PlanSVG } from "../render/PlanSVG";
import { SheetFrame } from "../render/SheetFrame";
import { solveElevation } from "../solver/elevation";
import { solvePlan } from "../solver/plan";
import type { Spec } from "../solver/spec";
import { ChatPanel } from "./ChatPanel";
import { Gallery } from "./Gallery";
import { Inspector } from "./Inspector";
import { lockDrawings } from "./lock";

type View = { kind: "plan" } | { kind: "elevation"; wallId: string };

export function Editor({
  session,
  busy,
  setBusy,
  onSession,
  onError,
}: {
  session: Session;
  busy: boolean;
  setBusy: (value: boolean) => void;
  onSession: (session: Session) => void;
  onError: (message: string) => void;
}) {
  const spec = session.spec!;
  const wallIds = spec.layout.walls.map((wall) => wall.id);
  const [view, setView] = useState<View>({ kind: "elevation", wallId: wallIds[0] });
  const [selected, setSelected] = useState<string | null>(null);
  const [decision, setDecision] = useState<EditDecision | null>(null);
  const [progress, setProgress] = useState("");

  useEffect(() => {
    if (view.kind === "elevation" && !wallIds.includes(view.wallId)) {
      setView({ kind: "elevation", wallId: wallIds[0] });
    }
  }, [session.spec?.version]);

  const preview: Preview | undefined = decision?.preview;
  // While a proposal is open the canvas shows the RESULT, marked up. You are
  // approving a drawing, not a sentence.
  const shownSpec: Spec = (preview?.spec as Spec) ?? spec;

  const sheet = useMemo(() => {
    if (view.kind === "plan") return solvePlan(shownSpec);
    return solveElevation(shownSpec, view.wallId);
  }, [shownSpec, view]);

  const ghost: GhostState | undefined = useMemo(() => {
    if (!preview) return undefined;
    const marks: GhostState = {};
    for (const [path, kind] of Object.entries(preview.diff)) {
      if (kind !== "removed") marks[path] = kind;
    }
    return marks;
  }, [preview]);

  const removed = preview
    ? Object.entries(preview.diff).filter(([, kind]) => kind === "removed").map(([path]) => path)
    : [];

  async function run<T>(work: () => Promise<T>, after?: (result: T) => void) {
    setBusy(true);
    onError("");
    try {
      after?.(await work());
    } catch (error) {
      onError((error as Error).message);
    } finally {
      setBusy(false);
      setProgress("");
    }
  }

  const applyOps = (ops: Op[]) =>
    run(() => api.ops(session.id, ops), (next) => {
      onSession(next);
      setDecision(null);
    });

  const sendChat = (text: string) =>
    run(
      () =>
        api.edit(
          session.id,
          text,
          view.kind === "elevation" ? view.wallId : null,
          selected,
        ),
      (result) => {
        onSession(result.session);
        setDecision(result.decision);
      },
    );

  return (
    <div className="editor">
      <section className="canvas">
        <div className="tabs">
          <button
            type="button"
            className={view.kind === "plan" ? "active" : ""}
            onClick={() => setView({ kind: "plan" })}
          >
            Plan
          </button>
          {spec.layout.walls.map((wall) => (
            <button
              key={wall.id}
              type="button"
              className={view.kind === "elevation" && view.wallId === wall.id ? "active" : ""}
              onClick={() => {
                setView({ kind: "elevation", wallId: wall.id });
                setSelected(null);
              }}
            >
              {wall.label || wall.id}
            </button>
          ))}
          <span className="spacer" />
          <span className="scale-badge">1:{sheet.scale}</span>
          <button type="button" onClick={() => window.print()}>
            Print
          </button>
        </div>

        {preview && (
          <div className="preview-banner">
            Previewing a change — {preview.summary}
            {removed.length > 0 && ` · removing ${removed.join(", ")}`}
          </div>
        )}

        <SheetFrame sheet={sheet}>
          {view.kind === "plan" ? (
            <PlanSVG
              sheet={sheet}
              selectedWallId={null}
              onSelectWall={(wallId) => setView({ kind: "elevation", wallId })}
            />
          ) : (
            <ElevationDOM
              sheet={sheet}
              selectedPath={selected}
              ghost={ghost}
              readOnly={session.locked || Boolean(preview)}
              onSelect={setSelected}
              onResize={(path, sizeCm) => applyOps([{ kind: "set_size", path, size_cm: sizeCm }])}
            />
          )}
        </SheetFrame>

        {session.locked && (
          <>
            <h2>Photographs</h2>
            {session.render_error && <p className="error">{session.render_error}</p>}
            <Gallery
              session={session}
              busy={busy}
              onGenerate={() => run(() => api.renderAll(session.id), onSession)}
              onRegenerate={(shotId) => run(() => api.renderShot(session.id, shotId), onSession)}
            />
          </>
        )}
      </section>

      <aside className="side">
        <div className="side-head">
          <span>
            v{spec.version}
            {session.versions.length > 1 ? ` · ${session.versions.length} saved` : ""}
          </span>
          <button
            type="button"
            disabled={busy || !session.can_undo}
            onClick={() => run(() => api.undo(session.id), onSession)}
          >
            Undo
          </button>
        </div>

        {!session.locked && view.kind === "elevation" && (
          <Inspector
            spec={spec}
            sheet={solveElevation(spec, view.wallId)}
            path={selected}
            busy={busy || Boolean(preview)}
            onOps={(ops) => applyOps(ops)}
          />
        )}

        <ChatPanel
          session={session}
          decision={decision}
          busy={busy}
          onSend={sendChat}
          onApply={() => decision && applyOps(decision.ops)}
          onDiscard={(reason) => {
            setDecision(null);
            if (reason === "wrong") {
              sendChat("That is not what I meant. Ask me what I want before changing anything.");
            }
          }}
        />

        {!session.locked && (
          <button
            type="button"
            className="primary lock"
            disabled={busy || Boolean(preview)}
            onClick={() =>
              run(
                () => lockDrawings(session.id, spec, setProgress),
                onSession,
              )
            }
          >
            {progress || "Lock drawings"}
          </button>
        )}
        {session.locked && <p className="hint">Locked at v{spec.version}. Undo to keep editing.</p>}
      </aside>
    </div>
  );
}
