import { useState } from "react";
import { api, ApiError, type Lesson, type LessonDecision } from "../lib/api";
import { useSettings } from "../lib/ctx";

const WAITING = new Set(["CANDIDATE", "NEEDS_EVIDENCE", "CHALLENGED"]);
type Mode = null | "rule" | "reject" | "retire";

/**
 * What a person can do with one lesson. The rules are the server's, repeated here only so a button is not offered that would be refused:
 * a waiting lesson can be approved (as advice, or as a rule if it is the enforceable kind and was seen repeatedly) or rejected;
 * an active one can be undone or retired; a rule needs a written note of what was verified; reject and retire need a reason.
 */
export function LessonActions({ lesson: x, onChanged }: { lesson: Lesson; onChanged: () => void }) {
  const { company } = useSettings();
  const [mode, setMode] = useState<Mode>(null);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);

  const waiting = WAITING.has(x.state);
  const active = String(x.state ?? "").startsWith("ACTIVE");
  // "Undo" needs a state to go back to: a lesson that was only ever proposed (for example one that expired on arrival) has none.
  const canUndo = (x.events ?? []).filter((e) => e.action !== "rollback").length >= 2;
  const canRule = waiting && x.state === "CANDIDATE" && x.gate?.enforceable === true;

  async function send(body: LessonDecision) {
    setBusy(true);
    setProblem(null);
    try {
      await api.decideLesson(company, x.lesson_id, body);
      setMode(null);
      setText("");
      onChanged();
    } catch (e) {
      setProblem(e instanceof ApiError ? e.message : "That did not work. Try again.");
    } finally {
      setBusy(false);
    }
  }

  const open = (m: Mode) => { setMode(m); setText(""); setProblem(null); };
  const id = x.lesson_id;
  if (!waiting && !active && !canUndo) return null;

  return (
    <div className="lesson-actions">
      {mode === null && (
        <div className="actions">
          {waiting && <button type="button" className="send" disabled={busy} aria-label={`Approve as advice, ${id}`} onClick={() => send({ decision: "approve", effect: "advisory" })}>Approve as advice</button>}
          {canRule && <button type="button" className="chip" disabled={busy} aria-label={`Approve as a rule…, ${id}`} onClick={() => open("rule")}>Approve as a rule…</button>}
          {waiting && <button type="button" className="chip" disabled={busy} aria-label={`Reject…, ${id}`} onClick={() => open("reject")}>Reject…</button>}
          {active && <button type="button" className="chip" disabled={busy} aria-label={`Retire…, ${id}`} onClick={() => open("retire")}>Retire…</button>}
          {canUndo && (active || !waiting) && <button type="button" className="chip" disabled={busy} aria-label={`${active ? "Undo approval" : "Undo"}, ${id}`} onClick={() => send({ decision: "rollback" })}>{active ? "Undo approval" : "Undo"}</button>}
        </div>
      )}
      {mode !== null && (
        <form className="reason" onSubmit={(e) => {
          e.preventDefault();
          const t = text.trim();
          if (!t) return;
          send(mode === "rule" ? { decision: "approve", effect: "policy", verified: t } : { decision: mode, why: t });
        }}>
          <label htmlFor={`why-${id}`} className="small">
            {mode === "rule" ? "What did you verify? A rule is enforced by code, so say how you know (a site visit, the operator, repeated failures)."
              : mode === "reject" ? "Why reject it?" : "Why retire it?"}
          </label>
          <input id={`why-${id}`} type="text" maxLength={300} value={text} onChange={(e) => setText(e.target.value)} autoFocus />
          <div className="actions">
            <button type="submit" className="send" disabled={busy || !text.trim()}>
              {busy ? "Working…" : mode === "rule" ? "Approve as a rule" : mode === "reject" ? "Reject it" : "Retire it"}
            </button>
            <button type="button" className="chip" disabled={busy} onClick={() => open(null)}>Cancel</button>
          </div>
        </form>
      )}
      {problem && <p role="alert" className="err-text">{problem}</p>}
    </div>
  );
}
