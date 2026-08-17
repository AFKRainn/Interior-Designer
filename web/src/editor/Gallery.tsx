/** Photoreal shots, one per camera job (plan, stage 3). */
import { useState } from "react";

import type { Session } from "../api";

export function Gallery({
  session,
  busy,
  onGenerate,
  onRegenerate,
}: {
  session: Session;
  busy: boolean;
  onGenerate: () => void;
  onRegenerate: (shotId: string) => void;
}) {
  const [showPrompt, setShowPrompt] = useState<string | null>(null);

  if (session.renders.length === 0) {
    return (
      <div className="gallery-empty">
        <button type="button" className="primary" disabled={busy} onClick={onGenerate}>
          Generate photographs
        </button>
        <p className="hint">
          One image per camera. Each gets only its own walls' elevations and a plan with
          those walls shaded — so no shot can invent a run it was not shown.
        </p>
      </div>
    );
  }

  return (
    <div className="gallery">
      {session.renders.map((shot) => (
        <figure key={shot.shot_id}>
          {shot.data ? (
            <img src={`data:${shot.mime_type};base64,${shot.data}`} alt={shot.shot_id} />
          ) : (
            <div className="missing">no image</div>
          )}
          <figcaption>
            <span>
              {shot.shot_id} · {shot.camera.replace("_", " ")} · {shot.walls.join(" + ")}
            </span>
            <div className="row">
              <button type="button" disabled={busy} onClick={() => onRegenerate(shot.shot_id)}>
                Regenerate
              </button>
              <button
                type="button"
                onClick={() => setShowPrompt(showPrompt === shot.shot_id ? null : shot.shot_id)}
              >
                {showPrompt === shot.shot_id ? "Hide" : "Show"} packet
              </button>
            </div>
            {showPrompt === shot.shot_id && <pre className="packet">{shot.prompt}</pre>}
          </figcaption>
        </figure>
      ))}
    </div>
  );
}
