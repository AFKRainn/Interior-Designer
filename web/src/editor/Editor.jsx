import { useEffect, useState } from "react";
import { api } from "../api";
import { ElevationSvg } from "../views/ElevationSvg";
import { PlanSvg } from "../views/PlanSvg";
import { Gallery } from "./Gallery";

export function Editor({ session, busy, setBusy, onSession, onError }) {
  const drawings = session.drawings || {};
  const [wallId, setWallId] = useState(
    drawings.elevations?.[0]?.wall_id || "wall-a"
  );
  const [selected, setSelected] = useState(null);
  const [widthInput, setWidthInput] = useState("");
  const [patch, setPatch] = useState("");
  const locked = session.locked;
  const elevation =
    (drawings.elevations || []).find((item) => item.wall_id === wallId) ||
    drawings.elevations?.[0];

  useEffect(() => {
    if (!selected) return;
    const elev =
      (session.drawings?.elevations || []).find((item) => item.wall_id === wallId) ||
      session.drawings?.elevations?.[0];
    const bay = elev?.bays?.find((item) => item.id === selected.id);
    if (bay) {
      setSelected(bay);
      setWidthInput(String(bay.width));
    }
  }, [session, wallId]);

  async function run(fn) {
    setBusy(true);
    onError("");
    try {
      onSession(await fn());
    } catch (err) {
      onError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function applyWidth(event) {
    event.preventDefault();
    if (!selected) return;
    await run(() =>
      api.bayWidth(session.id, wallId, selected.id, Number(widthInput))
    );
  }

  async function onDividerDragEnd(leftBayId, deltaCm) {
    await run(() => api.divider(session.id, wallId, leftBayId, deltaCm));
  }

  async function applyPatch(event) {
    event.preventDefault();
    if (!patch.trim()) return;
    await run(async () => {
      const next = await api.patchSpec(session.id, patch);
      setPatch("");
      return next;
    });
  }

  return (
    <div className="editor">
      <section className="drawings">
        <h2>Plan</h2>
        <PlanSvg svg={drawings.plan_svg} />
        <div className="elev-tabs">
          {(drawings.elevations || []).map((item) => (
            <button
              key={item.wall_id}
              type="button"
              className={item.wall_id === elevation?.wall_id ? "active" : ""}
              onClick={() => {
                setWallId(item.wall_id);
                setSelected(null);
              }}
            >
              {item.label}
            </button>
          ))}
        </div>
        {elevation && (
          <ElevationSvg
            elevation={elevation}
            selectedBayId={selected?.id}
            locked={locked}
            onSelectBay={(bay) => {
              setSelected(bay);
              setWidthInput(String(bay.width));
            }}
            onDividerDragEnd={onDividerDragEnd}
          />
        )}
        {locked && (
          <>
            <h2>Photoreal</h2>
            {session.render_error && (
              <p className="hint">{session.render_error}</p>
            )}
            <Gallery
              session={session}
              busy={busy}
              onGenerate={() => run(() => api.renderAll(session.id))}
              onRegenerate={(shotId) =>
                run(() => api.renderShot(session.id, shotId))
              }
            />
          </>
        )}
      </section>
      <aside className="side">
        <h2>{locked ? "Locked" : "Edit"}</h2>
        {session.spec?.version != null && (
          <p className="hint">
            Spec v{session.spec.version}
            {session.spec_versions?.length > 1
              ? ` (${session.spec_versions.length} saved)`
              : ""}
          </p>
        )}
        {selected ? (
          <form onSubmit={applyWidth} className="tweak">
            <label>
              {selected.label} width (cm)
              <input
                type="number"
                min="10"
                step="1"
                value={widthInput}
                disabled={locked || busy}
                onChange={(e) => setWidthInput(e.target.value)}
              />
            </label>
            <button type="submit" disabled={locked || busy}>
              Apply width
            </button>
            <p className="hint">Drag a bay divider on the elevation to resize.</p>
          </form>
        ) : (
          <p className="hint">Click a bay on the elevation.</p>
        )}
        <form onSubmit={applyPatch} className="patch">
          <label>
            Tell the AI to change something
            <textarea
              rows={3}
              value={patch}
              disabled={locked || busy}
              onChange={(e) => setPatch(e.target.value)}
              placeholder="Open shelves in bay 3, 4 shelves."
            />
          </label>
          <button type="submit" disabled={locked || busy}>
            Patch spec
          </button>
        </form>
        {!locked && (
          <button
            type="button"
            className="primary"
            disabled={busy}
            onClick={() => run(() => api.lock(session.id))}
          >
            Lock drawings
          </button>
        )}
        {locked && (
          <p className="hint">Locked. Generate photoreal from the sealed camera packets.</p>
        )}
      </aside>
    </div>
  );
}
