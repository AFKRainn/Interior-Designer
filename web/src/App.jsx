import { useEffect, useState } from "react";
import { api } from "./api";
import { BriefChat } from "./editor/BriefChat";
import { Editor } from "./editor/Editor";
import "./App.css";

export default function App() {
  const [session, setSession] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function wrap(fn) {
    setBusy(true);
    setError("");
    try {
      setSession(await fn());
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    wrap(() => api.createSession());
  }, []);

  if (!session) {
    return <div className="boot">{error || "Starting…"}</div>;
  }

  const editing = session.phase === "edit" || session.phase === "locked";

  return (
    <div className="app">
      <header>
        <div>
          <h1>Interior Designer</h1>
          {session.cost && (
            <p className="cost">
              ${Number(session.cost.total_cost || 0).toFixed(4)} · {session.cost.total_calls || 0} calls
            </p>
          )}
        </div>
        <div className="header-actions">
          <button type="button" disabled={busy} onClick={() => wrap(() => api.demo())}>
            Load demo L-kitchen
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={() => wrap(() => api.createSession())}
          >
            New
          </button>
        </div>
      </header>
      {error && <div className="error">{error}</div>}
      {busy && <div className="busy">Working…</div>}
      {editing ? (
        <Editor
          session={session}
          busy={busy}
          setBusy={setBusy}
          onSession={setSession}
          onError={setError}
        />
      ) : (
        <BriefChat
          session={session}
          busy={busy}
          setBusy={setBusy}
          onSession={setSession}
          onError={setError}
        />
      )}
    </div>
  );
}
