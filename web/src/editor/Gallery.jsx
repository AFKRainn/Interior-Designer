export function Gallery({ session, busy, onGenerate, onRegenerate }) {
  const renders = session.renders || [];

  if (!renders.length) {
    return (
      <div className="gallery-empty">
        <button
          type="button"
          className="primary"
          disabled={busy}
          onClick={onGenerate}
        >
          Generate photoreal
        </button>
        <p className="hint">One photograph per camera job. References stay sealed to that shot.</p>
      </div>
    );
  }

  return (
    <div className="gallery">
      {renders.map((shot) => (
        <figure key={shot.shot_id}>
          {shot.data ? (
            <img
              src={`data:${shot.mime_type || "image/png"};base64,${shot.data}`}
              alt={shot.shot_id}
            />
          ) : (
            <div className="gallery-missing">No image</div>
          )}
          <figcaption>
            <span>
              {shot.shot_id} · {shot.camera} · {(shot.walls || []).join(" + ")}
            </span>
            <button
              type="button"
              disabled={busy}
              onClick={() => onRegenerate(shot.shot_id)}
            >
              Regenerate
            </button>
          </figcaption>
        </figure>
      ))}
    </div>
  );
}
