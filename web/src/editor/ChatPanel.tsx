/**
 * Chat editing, with a confirmation step (plan 10.3).
 *
 * The assistant never changes the drawing directly. It either asks — with
 * options — or it restates what it understood and shows the change ghosted on
 * the sheet, and you decide. Build 1's misunderstanding survived a whole
 * session because there was no moment like this.
 */
import { useState } from "react";

import type { EditDecision, Session } from "../api";

export function ChatPanel({
  session,
  decision,
  busy,
  onSend,
  onApply,
  onDiscard,
}: {
  session: Session;
  decision: EditDecision | null;
  busy: boolean;
  onSend: (text: string) => void;
  onApply: () => void;
  onDiscard: (reason: "cancel" | "wrong") => void;
}) {
  const [text, setText] = useState("");
  const pending = decision && decision.action === "propose" && decision.preview;

  return (
    <div className="chat">
      <div className="chat-log">
        {session.chat.map((entry, index) => (
          <div key={index} className={`bubble ${entry.role}`}>
            <p>{entry.text}</p>
            {Array.isArray(entry.open) && entry.open.length > 0 && (
              <ul className="options">
                {(entry.open as { field: string; options?: string[] }[]).map((item) => (
                  <li key={item.field}>
                    <strong>{item.field}</strong>
                    {item.options?.length ? ` — ${item.options.join(" / ")}` : ""}
                  </li>
                ))}
              </ul>
            )}
          </div>
        ))}
      </div>

      {decision && decision.action === "clarify" && (
        <div className="clarify">
          {decision.ambiguities.map((item, index) => (
            <div key={index}>
              <p>{item.question}</p>
              {item.options.length > 0 && (
                <div className="row wrap">
                  {item.options.map((option) => (
                    <button key={option} type="button" disabled={busy} onClick={() => onSend(option)}>
                      {option}
                    </button>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {pending && (
        <div className="proposal">
          <p className="understanding">{decision!.understanding}</p>
          <p className="hint">
            {decision!.preview!.summary} · shown on the drawing in green and red
          </p>
          <div className="row">
            <button type="button" className="primary" disabled={busy} onClick={onApply}>
              Apply
            </button>
            <button type="button" disabled={busy} onClick={() => onDiscard("cancel")}>
              Cancel
            </button>
            <button type="button" disabled={busy} onClick={() => onDiscard("wrong")}>
              Not what I meant
            </button>
          </div>
        </div>
      )}

      <form
        className="chat-form"
        onSubmit={(event) => {
          event.preventDefault();
          if (!text.trim()) return;
          onSend(text.trim());
          setText("");
        }}
      >
        <textarea
          rows={2}
          value={text}
          disabled={busy}
          placeholder='e.g. "two doors next to each other in the top of bay 2"'
          onChange={(event) => setText(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              if (text.trim()) {
                onSend(text.trim());
                setText("");
              }
            }
          }}
        />
        <button type="submit" disabled={busy || !text.trim()}>
          Send
        </button>
      </form>
    </div>
  );
}
