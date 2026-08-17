import { useEffect, useState } from "react";

import { api } from "./api";
import type { Session } from "./api";
import { BriefChat } from "./editor/BriefChat";
import { Editor } from "./editor/Editor";
import "./App.css";
import "./render/sheet.css";

export default function App() {
  const [session, setSession] = useState<Session | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function run(work: () => Promise<Session>) {
    setBusy(true);
    setError("");
    try {
      setSession(await work());
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    run(() => api.create());
  }, []);

  if (!session) return <div className="boot">{error || "Starting…"}</div>;

  const editing = Boolean(session.spec);

  return (
    <div className="app">
      <header>
        <div>
          <h1>Interior Designer</h1>
          {session.cost && (
            <p className="cost">
              ${Number(session.cost.total_cost ?? 0).toFixed(4)} ·{" "}
              {session.cost.total_calls ?? 0} calls
            </p>
          )}
        </div>
        <div className="row">
          <button type="button" disabled={busy} onClick={() => run(() => api.demo())}>
            Demo L-kitchen
          </button>
          <button type="button" disabled={busy} onClick={() => run(() => api.create())}>
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
