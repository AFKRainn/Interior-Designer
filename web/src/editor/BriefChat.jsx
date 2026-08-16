import { useState } from "react";
import { api } from "../api";

export function BriefChat({ session, busy, setBusy, onSession, onError }) {
  const [text, setText] = useState("");
  const [files, setFiles] = useState([]);

  async function send(event) {
    event.preventDefault();
    if (!text.trim() && !files.length) return;
    setBusy(true);
    onError("");
    try {
      const images = await Promise.all(files.map(fileToImage));
      const next = session.chat?.length
        ? await api.briefReply(session.id, text, images)
        : await api.briefStart(session.id, text, images);
      onSession(next);
      setText("");
      setFiles([]);
    } catch (err) {
      onError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="brief">
      <div className="chat-log">
        {(session.chat || []).map((msg, i) => (
          <div key={i} className={`bubble ${msg.role}`}>
            {msg.text}
          </div>
        ))}
      </div>
      <form className="chat-form" onSubmit={send}>
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Describe the piece. Tight crops are fine — attach more photos of what is out of frame."
          rows={3}
          disabled={busy}
        />
        <div className="chat-actions">
          <input
            type="file"
            accept="image/*"
            multiple
            onChange={(e) => setFiles(Array.from(e.target.files || []))}
            disabled={busy}
          />
          {files.length > 0 && (
            <span className="hint">{files.length} photo{files.length === 1 ? "" : "s"}</span>
          )}
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
          onClick={async () => {
            setBusy(true);
            onError("");
            try {
              onSession(await api.buildSpec(session.id));
            } catch (err) {
              onError(err.message);
            } finally {
              setBusy(false);
            }
          }}
        >
          Build drawings
        </button>
      )}
    </div>
  );
}

function fileToImage(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const url = reader.result;
      const base64 = String(url).split(",")[1] || "";
      resolve({ data: base64, mime_type: file.type || "image/png" });
    };
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}
