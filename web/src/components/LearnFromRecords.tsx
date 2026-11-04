import { useState } from "react";
import { api, ApiError, modelName, type FreshLearned, type FreshRecords } from "../lib/api";
import { useApi } from "../lib/useApi";
import { useSettings } from "../lib/ctx";
import { useFocusTarget } from "../lib/focus";
import { plainReason, usd } from "../lib/text";

const num = (x: unknown) => (typeof x === "number" ? x.toLocaleString("en-IN") : "—");

// Start from nothing (final demo plan): the visitor sees what this workspace knows, lets Muse Spark 1.3 read the
// company's records, and sees each proposed rule with the evidence gate's verdict. Approving happens in the list below.

const VERDICT: Record<string, [string, string]> = {
  CANDIDATE: ["✓ evidence holds · waiting for a person", "ok"],
  NEEDS_EVIDENCE: ["… needs more evidence", "warn"],
  CHALLENGED: ["? challenged", "warn"],
  REJECTED: ["✕ rejected by the gate", "err"],
  EXPIRED: ["⌛ already over: stored as expired", "expired"],
};

/** "4 lessons · 0 tools · agents at version 1": what this visitor's workspace knows right now. */
export function KnowsNow() {
  const { company, dataVersion } = useSettings();
  const s = useApi(() => api.freshStatus(company), [company, dataVersion], { keep: true });
  if (!s.data) return null;
  const v = Object.values(s.data.agent_versions ?? {});
  const same = v.length && v.every((x) => x === v[0]);
  return (
    <p className="knows-now" role="status" aria-label="What this workspace knows">
      <strong>{s.data.lessons}</strong> lesson{s.data.lessons === 1 ? "" : "s"}
      {s.data.waiting_lessons ? <> ({s.data.waiting_lessons} waiting for a person)</> : null} · <strong>{s.data.tools}</strong> tool{s.data.tools === 1 ? "" : "s"} ·
      agents at {same ? `version ${v[0]}` : "their own versions"}{s.data.fresh ? <span className="pill warn">Fresh start</span> : null}
    </p>
  );
}

export function LearnFromRecords() {
  const { company, live, bumpData, refreshSession, dataVersion, model, modelLabel } = useSettings();
  const ref = useFocusTarget<HTMLElement>("learn", true);
  const st = useApi(() => api.freshStatus(company), [company, dataVersion], { keep: true });
  const [stage, setStage] = useState<"idle" | "reading" | "mining" | "done">("idle");
  const [records, setRecords] = useState<FreshRecords | null>(null);
  const [out, setOut] = useState<FreshLearned | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const left = st.data?.mines_left;
  const blocked = !live.ok ? plainReason(live.reason) : left === 0 ? "This visit has used all its learning runs." : null;

  async function go() {
    setProblem(null);
    setOut(null);
    setStage("reading");
    setRecords(await api.freshRecords(company));
    setStage("mining");
    try {
      setOut(await api.freshLearn(company, model));
      setStage("done");
      bumpData();
      refreshSession();
    } catch (e) {
      setProblem(e instanceof ApiError ? e.message : "That did not work. Try again.");
      setStage("idle");
    }
  }

  return (
    <section ref={ref} className="panel learn-panel" aria-labelledby="learn-title">
      <div className="learn-head">
        <h3 id="learn-title">Learn from the records</h3>
        <KnowsNow />
      </div>
      <p className="small muted">
        {modelLabel} reads 90 days of this company's trips, drivers' notes and messages, and proposes rules nobody wrote down.
        Code then checks each one against the full records. A person approves what passes; nothing changes a plan before that.
      </p>
      <div className="actions">
        <button type="button" className="send" disabled={stage === "reading" || stage === "mining" || !!blocked} onClick={go}>
          {stage === "reading" ? "Reading the records…" : stage === "mining" ? `${modelLabel} is proposing rules…` : "Learn from the records (live)"}
        </button>
        {left != null && <span className="small muted">{left} learning {left === 1 ? "run" : "runs"} left in this visit · each counts as one live run</span>}
      </div>
      {blocked && stage === "idle" && <p className="small muted">{blocked}</p>}
      {problem && <p role="alert" className="err-text">{problem}</p>}

      {records && (
        <ol className="plain learn-stages" aria-label="Learning, step by step">
          <li className="ok-text">✓ Read the records: {num(records.stops)} delivery stops on {num(records.trips)} trips,
            {" "}{records.drivers_notes} drivers' notes ({Object.entries(records.notes_by_language ?? {}).map(([k, v]) => `${v} ${({ te: "Telugu", en: "English", rt: "Roman Telugu" } as Record<string, string>)[k] ?? k}`).join(", ")}),
            {" "}{records.planner_messages} planner messages, {records.from ?? "—"} to {records.to ?? "—"}.</li>
          <li className={stage === "mining" ? "" : "ok-text"}>{stage === "mining" ? `… ${modelLabel} is reading a digest of them and proposing rules (about a minute).` : `✓ ${modelName(out?.model) || modelLabel} proposed rules.`}</li>
          {out && <li className="ok-text">✓ Code checked each rule against the full records: {out.counts?.CANDIDATE ?? 0} hold, {out.counts?.REJECTED ?? 0} rejected, {out.counts?.EXPIRED ?? 0} already over. ({out.latency_s ?? "—"} s · {usd(out.cost_usd)})</li>}
        </ol>
      )}

      {out && (
        <ul className="plain learned-list" aria-label="What it proposed, with the gate's verdict">
          {(out.lessons ?? []).map((l) => {
            const [label, cls] = VERDICT[l.state] ?? [l.state, ""];
            return (
              <li key={l.lesson_id} className={`learned-row v-${cls}`}>
                <span className={`pill ${cls === "expired" ? "" : cls}`}>{label}</span>
                <span className="learned-what">{l.display}</span>
                <span className="small muted">Evidence: {l.reason}</span>
              </li>
            );
          })}
        </ul>
      )}
      {out && <p className="small">Approve the ones you trust in the list below. These are your lessons, mined just now; the recorded runs used lessons mined earlier (EXP-008), and the benchmarks EXP-009b's.</p>}
    </section>
  );
}
