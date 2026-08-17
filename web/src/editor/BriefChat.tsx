/**
 * Intake (plan 10.1).
 *
 * The assistant's open questions are shown as their own list, because they
 * are a required part of its output rather than something it might mention.
 * The "Build drawings" button only appears once the completeness gate has
 * actually passed on the server.
 */
import { useState } from "react";

import { api } from "../api";
import type { Session } from "../api";

export function BriefChat({
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
  const [text, setText] = useState("");
  const [files, setFiles] = useState<File[]>([]);

  async function run<T>(work: () => Promise<T>, after: (value: T) => void) {
    setBusy(true);
    onError("");
    try {
      after(await work());
    } catch (error) {
      onError((error as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function send(event: React.FormEvent) {
    event.preventDefault();
    if (!text.trim() && files.length === 0) return;
    const images = await Promise.all(files.map(toImage));
    await run(() => api.brief(session.id, text, images), (next) => {
      onSession(next);
      setText("");
      setFiles([]);
    });
  }

  const missing = session.intake?.missing ?? [];

  return (
    <div className="brief">
      <div className="chat-log">
        {session.chat.map((entry, index) => (
          <div key={index} className={`bubble ${entry.role}`}>
            <p>{entry.text}</p>
            {Array.isArray(entry.open) && entry.open.length > 0 && (
              <ul className="options">
                {(entry.open as { field: string; why: string; options?: string[] }[]).map((item) => (
                  <li key={item.field}>
                    <strong>{item.field}</strong> — {item.why}
                    {item.options?.length ? <em> ({item.options.join(" / ")})</em> : null}
                  </li>
                ))}
              </ul>
            )}
          </div>
        ))}
      </div>

      {missing.length > 0 && (
        <p className="hint">
          Still needed before drawings: {missing.join(", ")}
        </p>
      )}

      <form className="chat-form" onSubmit={send}>
        <textarea
          rows={3}
          value={text}
          disabled={busy}
          placeholder="Describe the piece. A tight crop is fine — say what is out of frame."
          onChange={(event) => setText(event.target.value)}
        />
        <div className="row">
          <input
            type="file"
            accept="image/*"
            multiple
            disabled={busy}
            onChange={(event) => setFiles(Array.from(event.target.files ?? []))}
          />
          {files.length > 0 && <span className="hint">{files.length} photo(s)</span>}
          <button type="submit" disabled={busy}>
            Send
          </button>
        </div>
      </form>

      {session.phase === "brief_ready" && (
        <button
          type="button"
          className="primary"
          disabled={busy}
          onClick={() => run(() => api.buildSpec(session.id), onSession)}
        >
          Build drawings
        </button>
      )}
    </div>
  );
}

function toImage(file: File): Promise<{ data: string; mime_type: string }> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const url = String(reader.result);
      resolve({ data: url.slice(url.indexOf(",") + 1), mime_type: file.type || "image/png" });
    };
    reader.onerror = () => reject(new Error("could not read that file"));
    reader.readAsDataURL(file);
  });
}
