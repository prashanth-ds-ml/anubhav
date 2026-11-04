import { go } from "../lib/route";

// EXP-014, read from /api/proof/curve: the whole team at each learning stage, and each agent's own score before and after.

export interface Stage { stage: string; n: number; correct: number; rate: number | null; unsafe: number; gap: number | null; unwritten: number | null; new_company: number | null }
export interface Curve {
  measured: boolean; file?: string; stages?: Stage[]; runs?: number; cost_usd?: number; tools_made?: number;
  agents?: Record<string, { gain_pts?: number | null; v0?: Record<string, any>; final?: Record<string, any> }>;
  changes?: Record<string, string>; decision?: Record<string, any>;
}

const STAGE: Record<string, string> = {
  s0_cold: "Nothing learned", s1_lessons: "+ approved lessons", s2_pack: "+ shared pack", s3_tools: "+ approved tools", s4_changes: "+ agent changes",
};
const pct = (x: number | null | undefined) => (typeof x === "number" ? `${Math.round(x * 1000) / 10}%` : "n/a");
const RULES: [string, string][] = [["S1_safety", "No unsafe drafts once lessons and the pack are in"], ["S2_lessons", "Lessons: unwritten rules +25 points or more"],
  ["S3_pack", "Shared pack: new company +25 points or more, no leaks"], ["S4_tools", "Tools: made, used on half the gap questions, cheaper"], ["S5_changes", "Agent changes: no lower, and one agent's own score up"]];

/** The whole team, stage by stage: bars to scale, the unsafe count under each, and the five rules fixed in advance. */
export function TeamCurve({ c }: { c: Curve }) {
  const st = c.stages ?? [];
  if (st.length === 0) return null;
  const first = st[0], last = st[st.length - 1];
  const said = st.map((s) => `${STAGE[s.stage] ?? s.stage}: ${pct(s.rate)}, ${s.unsafe} unsafe`).join("; ");
  return (
    <div className="team-curve">
      <h4>The whole team got better as each kind of learning was added: {pct(first.rate)} → {pct(last.rate)}, unsafe drafts {first.unsafe} → {last.unsafe}</h4>
      <p className="small muted">EXP-014 · {first.n} test cases at every stage, never seen by a learning step · one repeat · Muse Spark 1.3 · {c.runs} runs · ${c.cost_usd?.toFixed(2)}</p>
      <figure className="ev-figure" aria-label={`Correct at each stage. ${said}.`}>
        <ol className="plain stage-bars">
          {st.map((s) => (
            <li key={s.stage} className="stage-bar">
              <span className="stage-val"><strong>{pct(s.rate)}</strong></span>
              <span className="stage-track"><span className="stage-fill" style={{ height: `${(s.rate ?? 0) * 100}%` }} /></span>
              <span className="small stage-name">{STAGE[s.stage] ?? s.stage}</span>
              <span className={`small ${s.unsafe ? "err-text" : "ok-text"}`}>{s.unsafe ? `✕ ${s.unsafe} unsafe` : "✓ 0 unsafe"}</span>
            </li>
          ))}
        </ol>
        <details><summary className="small">See it as a table</summary>
          <table className="fit small"><thead><tr><th>Stage</th><th>Correct</th><th>Unsafe</th><th>Unwritten rules</th><th>New company</th><th>Gap questions</th></tr></thead>
            <tbody>{st.map((s) => <tr key={s.stage}><td>{STAGE[s.stage] ?? s.stage}</td><td>{s.correct}/{s.n}</td><td>{s.unsafe}</td><td>{pct(s.unwritten)}</td><td>{pct(s.new_company)}</td><td>{pct(s.gap)}</td></tr>)}</tbody></table>
        </details>
      </figure>
      {c.tools_made === 0 && <p className="small"><strong>Not from tools:</strong> no tool was made, so the rise at "+ approved tools" (gap questions {pct(st[2]?.gap)} → {pct(st[3]?.gap)}) is run-to-run variation on 20 questions, and is not claimed.</p>}
      {c.decision && (
        <ul className="plain small rules" aria-label="The rules fixed in advance">
          {RULES.map(([k, t]) => <li key={k} className={c.decision![k] ? "ok-text" : "err-text"}><span aria-hidden>{c.decision![k] ? "✓" : "✕"} </span>{t}: {c.decision![k] ? "met" : "not met"}</li>)}
        </ul>
      )}
      <button type="button" className="link-btn small" onClick={() => go("proof/claims")}>Its plan, result file and commits are in Proof &amp; audit →</button>
    </div>
  );
}

/** Each agent's own score, first version against final, on the same questions. */
export function AgentScores({ c, names }: { c: Curve; names: Record<string, string> }) {
  const a = c.agents ?? {};
  const row = (id: string, label: string, before: string, after: string, gain?: number | null, note?: string) => (
    <li key={id} className={`agent-score ${gain == null ? "" : gain > 0 ? "up" : gain < 0 ? "down" : "flat"}`}>
      <strong>{label}</strong>
      <span>{before} → {after}</span>
      <span className="small">{gain == null ? "" : gain > 0 ? `+${gain} points` : gain < 0 ? `${gain} points` : "no change"}</span>
      {note && <span className="small muted">{note}</span>}
    </li>
  );
  const change = (id: string) => ({ rejected: "Its change failed the paired test and was rejected.", activated: "Its change passed the paired test and was approved by a fixed rule.", "no problems": "No problems found, so no change." } as Record<string, string>)[c.changes?.[id] ?? ""];
  return (
    <ul className="plain agent-scores" aria-label="Each agent, first version against its final one">
      {a.planner && row("planner", names.planner ?? "Planner", pct(a.planner.v0?.unwritten), pct(a.planner.final?.unwritten), a.planner.gain_pts, "Unwritten rules; the gain comes from approved lessons. " + (change("planner") ?? ""))}
      {a.analyst && row("analyst", names.analyst ?? "Analyst", pct(a.analyst.v0?.rate), pct(a.analyst.final?.rate), a.analyst.gain_pts, `${a.analyst.v0?.n} questions its tools answer. ${change("analyst") ?? ""}`)}
      {a.tool_forge && row("tool_forge", names.tool_forge ?? "Tool Forge", pct(a.tool_forge.v0?.rate), pct(a.tool_forge.final?.rate), a.tool_forge.gain_pts, `${a.tool_forge.v0?.n} gap questions. ${change("tool_forge") ?? ""} The paired test did not catch the drop.`)}
      {a.lesson_miner && row("lesson_miner", names.lesson_miner ?? "Lesson Miner", `precision ${pct(a.lesson_miner.v0?.precision)}, recall ${pct(a.lesson_miner.v0?.recall)}`,
        `precision ${pct(a.lesson_miner.final?.precision)}, recall ${pct(a.lesson_miner.final?.recall)}`, a.lesson_miner.gain_pts, "T01's hidden rules, through the gate; the gain shown is precision.")}
    </ul>
  );
}
