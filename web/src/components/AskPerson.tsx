import { useState } from "react";
import { useSettings } from "../lib/ctx";
import { Reply } from "../lib/text";

// When a run stops for a person (owner, Nov 3): say plainly what happened and what each choice does. Approve lets it go
// past a limit it hit (a new budget, or another try); Decline stops it with what it found; Other asks for instructions.
// A code safety check (load, gate, papers) is never something to approve past: the draft checks run again either way.

export type Ask = { rule: string; question: string; tool?: string; last_error?: { message?: string } | null; tool_calls?: number };

const APPROVE: Record<string, string> = {
  tool_refused: "Approved: try again, a different way if you can (another tool, or hand it to a teammate). You have a new budget.",
  reply_refused: "Approved: rewrite your answer using only ids and facts from the tools, and say what you could not check.",
  limit: "Approved: continue from where you stopped. You have a new budget; don't repeat calls you already made.",
};
const DECLINE = "Declined: stop here. Answer with what you found, what you could not check, and the next step you would take.";

function plain(a: Ask): { title: string; body: string; approve: string } {
  if (a.rule === "tool_refused")
    return { title: "It needs your decision to continue",
      body: `It tried ${a.tool ?? "a tool"} 3 times and the system refused each time${a.last_error?.message ? ` (last: ${a.last_error.message})` : ""}. Should it try again a different way?`,
      approve: "Approve: try again" };
  if (a.rule === "reply_refused")
    return { title: "Its answer was held back", body: a.question, approve: "Approve: let it rewrite" };
  if (a.rule === "limit")
    return { title: "It used its whole budget before finishing",
      body: `It made ${a.tool_calls ?? "all its"} tool calls, the most one request may make, and answered with what it had. Continue with a new budget?`,
      approve: "Approve: continue" };
  return { title: "It is asking you", body: a.question, approve: "" };     // a plain question: answer it in words
}

export function AskPerson({ ask, onReply }: { ask: Ask; onReply: (text: string) => void }) {
  const { live, modelLabel } = useSettings();
  const [other, setOther] = useState(ask.rule === "question");
  const [text, setText] = useState("");
  const [done, setDone] = useState<string | null>(null);
  const p = plain(ask);
  const send = (reply: string, label: string) => { setDone(label); if (reply) onReply(reply); };
  return (
    <div className="bubble agent answer ask-person" role="group" aria-label="Waiting for you">
      <strong>Waiting for you · {p.title}</strong>
      <Reply text={p.body} />
      {done ? <p className="small muted" role="status">You chose: {done}.</p> : (
        <>
          <div className="actions">
            {p.approve && <button type="button" className="send" disabled={!live.ok} onClick={() => send(APPROVE[ask.rule] ?? APPROVE.limit, "Approve")}>{p.approve}</button>}
            {p.approve && (
              <button type="button" className="chip" disabled={!live.ok && ask.rule !== "limit"}
                onClick={() => send(ask.rule === "limit" ? "" : DECLINE, "Decline")}>Decline</button>
            )}
            {!other && <button type="button" className="chip" disabled={!live.ok} onClick={() => setOther(true)}>Other…</button>}
          </div>
          {other && (
            <form className="ask-other" onSubmit={(e) => { e.preventDefault(); if (text.trim()) send(text.trim(), "your instructions"); }}>
              <label className="small" htmlFor="ask-other-text">{ask.rule === "question" ? "Your answer" : "What should it do next?"}</label>
              <textarea id="ask-other-text" rows={2} value={text} onChange={(e) => setText(e.target.value)} disabled={!live.ok} />
              <button type="submit" className="send" disabled={!live.ok || !text.trim()}>Send</button>
            </form>
          )}
          <p className="small muted">
            {live.ok ? `Replying continues the same run live on ${modelLabel} (one live run). Code safety checks still apply: they can't be approved past.`
              : `Replying needs a live run: ${live.reason ?? "live mode is off here"}.`}
          </p>
        </>
      )}
    </div>
  );
}
