import { useState } from "react";
import { api, ApiError, modelName, type Compare, type CompareSide, type NewTool, type ToolCandidate } from "../lib/api";
import { go } from "../lib/route";
import { useApi } from "../lib/useApi";
import { useSettings } from "../lib/ctx";
import { humanName, Reply } from "../lib/text";
import { useFocusTarget } from "../lib/focus";
import { ProofLine, useFreshMode } from "./AgentCards";

// A candidate's tool id ends with the first eight characters of its key, which is how the two lists are matched.
const isFor = (t: NewTool, c: ToolCandidate) => t.tool_id.endsWith(c.key.slice(0, 8));
const IN_USE = (t: NewTool) => t.status === "active";
/** A readable title: the kind of question it answers, from its description; else its name without underscores. */
const toolTitle = (t: NewTool) => {
  const eg = t.description.match(/e\.g\. "([^"]+)"/)?.[1];
  return eg ? `Answers questions like “${eg}”` : humanName(t.name);
};
const OUT = (t: NewTool) => t.status === "rejected" || t.status === "retired";

function Result({ title, s }: { title: string; s: CompareSide | null }) {
  if (!s) return null;
  return (
    <article className="panel">
      <h4>{title}</h4>
      <p className="small muted">{s.tool_calls} tool call{s.tool_calls === 1 ? "" : "s"} · ${s.cost_usd.toFixed(3)}</p>
      <Reply text={s.reply} />
    </article>
  );
}

function Checks({ t }: { t: NewTool }) {
  const same = t.checks.same_rows.filter((x) => x.same).length;
  const seen = t.checks.held_out.filter((x) => x.ok).length;
  return (
    <ul className="plain checks" aria-label="Check results">
      <li className={same === t.checks.same_rows.length ? "ok-text" : "err-text"}>
        Same answers as the {t.checks.same_rows.length} questions it came from: {same} of {t.checks.same_rows.length}
      </li>
      <li className={seen === t.checks.held_out.length ? "ok-text" : "err-text"}>
        Works on {t.checks.held_out.length} values it never saw ({t.checks.held_out.map((x) => Object.values(x.values).join(", ")).join("; ")}): {seen} of {t.checks.held_out.length}
      </li>
      {t.checks.reasons.map((r) => <li key={r} className="err-text">{r}</li>)}
    </ul>
  );
}

/** Tool Forge's repair, try by try: what it changed and what code found each time. */
function RepairTrail({ t }: { t: NewTool }) {
  const r = t.checks.repair;
  if (!r) return null;
  const last = r.attempts[r.attempts.length - 1];
  return (
    <details className="repair-trail" open>
      <summary className="small">
        Tool Forge's repair{r.model ? ` (${modelName(r.model)})` : ""}: {r.attempts.length} tr{r.attempts.length === 1 ? "y" : "ies"},{" "}
        {last?.pass ? <span className="ok-text">code checks passed: waiting for a person</span> : <span className="err-text">still failing</span>}
        {` · $${r.cost_usd.toFixed(3)}`}
      </summary>
      <ol className="small">
        {r.attempts.map((a) => (
          <li key={a.try}>
            {a.error ?? (a.pass ? "✓ passed every check" : `✕ ${(a.reasons ?? []).join("; ")}`)}
            {a.template && <pre className="mono small">{a.template}</pre>}
          </li>
        ))}
      </ol>
      {r.from_template && <details><summary className="small">The query before the repair</summary><pre className="mono small">{r.from_template}</pre></details>}
    </details>
  );
}

/** Bars for one measure, before and after: the longer value fills the track. */
function Pair({ title, before, after, fmt }: { title: string; before: number; after: number; fmt: (x: number) => string }) {
  const top = Math.max(before, after, 1e-9);
  return (
    <div className="ba">
      <p className="small muted">{title}</p>
      {([["Before", before, "base"], ["After", after, "now"]] as const).map(([k, v, tone]) => (
        <div key={k} className="ba-row">
          <span className="small">{k}</span>
          <span className="mbar-track"><span className={`mbar-fill ${tone}`} style={{ width: `${(100 * v) / top}%` }} /></span>
          <span className="small">{fmt(v)}</span>
        </div>
      ))}
    </div>
  );
}

/** What approving changed for the same question, from the two recorded runs (one example; the benchmark is beside it). */
function WhatChanges({ cmp }: { cmp: Compare }) {
  const a = cmp.cold, b = cmp.with_learned_tools;
  if (!a || !b) return null;
  return (
    <aside className="what-changes" aria-label="What approving changes, from recorded runs">
      <p><strong>What approving changes (recorded runs)</strong></p>
      <Pair title="Tool calls for the same question" before={a.tool_calls} after={b.tool_calls} fmt={(x) => String(x)} />
      <Pair title="Cost of the question" before={a.cost_usd} after={b.cost_usd} fmt={(x) => `$${x.toFixed(3)}`} />
      <p className="small muted">Both are recorded runs of Muse Spark Open; their replies are below once the tool is approved.</p>
    </aside>
  );
}

/** EXP-012b across its held-out questions, with the bar it set itself in advance and its verdict. */
function Benchmark() {
  const proof = useApi(() => api.proof(), []);
  const reg = useApi(() => api.registry(), []);
  const e = proof.data?.find((x) => x.id === "EXP-012b");
  const r = reg.data?.experiments.find((x) => x.id === "EXP-012b");
  if (proof.loading) return <div className="skeleton" aria-busy="true" />;
  if (!e?.arms) return <p className="small muted">The benchmark result file is not available here.</p>;
  const { Q, T } = e.arms as Record<string, { n: number; answer_ok: number; mean_tool_calls: number }>;
  const used = String(e.decision?.learned_tool_used_in ?? "");
  const [u, n] = used.split("/").map(Number);
  return (
    <section className="panel bench" aria-labelledby="bench-title">
      <h3 id="bench-title">Across the benchmark</h3>
      <p className="small muted">EXP-012b · {Q.n} held-out questions · {e.measured_on}</p>
      {n > 0 && (
        <div className="ba">
          <p className="small muted">Learned tool used</p>
          <div className="ba-row"><span className="mbar-track"><span className="mbar-fill now" style={{ width: `${(100 * u) / n}%` }} /></span><strong>{u} of {n}</strong></div>
        </div>
      )}
      <Pair title="Tool calls per question" before={Q.mean_tool_calls} after={T.mean_tool_calls} fmt={(x) => String(x)} />
      <p className="small">{Math.round(100 * (1 - T.mean_tool_calls / Q.mean_tool_calls))}% fewer calls.</p>
      {r && <p className={`small ${r.verdict === "met" ? "ok-text" : r.verdict === "not_met" ? "err-text" : ""}`}>{r.verdict === "met" ? "✓ Bar met" : r.verdict === "not_met" ? "✕ Bar not met" : r.verdict}{r.summary ? `: ${r.summary}.` : "."}</p>}
      <p className="small">Answers were {T.answer_ok >= Q.answer_ok ? "not worse" : "worse"} ({Math.round(100 * T.answer_ok)}% against {Math.round(100 * Q.answer_ok)}%).</p>
      <button type="button" className="link-btn small" onClick={() => go("proof")}>Its plan and result file are in Proof &amp; audit →</button>
    </section>
  );
}

/** Repeated questions, how one becomes a tool, and what changed once a person approved it. */
export function NewTools({ onAsk }: { onAsk: (label: string) => void }) {
  const { company, requests, bumpData, live, model, modelLabel, dataVersion } = useSettings();
  const fresh = useFreshMode();       // Fresh start: only this workspace's tools; the measured results stay under Proof
  const repair = (t: NewTool) => (
    <div className="actions">
      <button type="button" className="chip" disabled={busy !== null || !live.ok} title={live.ok ? undefined : live.reason ?? undefined}
        onClick={() => act(t.tool_id, () => api.repairTool(company, t.tool_id, model))}>
        {busy === t.tool_id ? "Tool Forge is repairing it…" : `Ask Tool Forge to repair it (live, ${modelLabel})`}
      </button>
      <span className="small muted">{live.ok ? "At most 2 tries; code re-checks each, and a person approves." : live.reason}</span>
    </div>
  );
  const [version, setVersion] = useState(0);
  const [busy, setBusy] = useState<string | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const cands = useApi(() => api.toolCandidates(company), [company, version, dataVersion], { keep: true });
  const tools = useApi(() => api.tools(company), [company, version, dataVersion], { keep: true });
  const story = requests.find((r) => r.label === "New tool");
  const cmp = useApi(() => (story && fresh === false ? api.compare(company, story.request) : Promise.resolve(null)), [company, story?.request, fresh]);
  const isStory = (t: NewTool) => !!story && t.checks.same_rows.some((r) => r.request === story.request);

  async function act(key: string, f: () => Promise<unknown>) {
    setBusy(key);
    setProblem(null);
    try { await f(); setVersion((v) => v + 1); bumpData(); } catch (e) { setProblem(e instanceof ApiError ? e.message : "That did not work. Try again."); } finally { setBusy(null); }
  }

  const all = tools.data ?? [];
  const open = (cands.data ?? []).filter((c) => !all.some((t) => isFor(t, c)));
  const waiting = all.filter((t) => !IN_USE(t) && !OUT(t));
  const active = all.filter(IN_USE);
  const out = all.filter(OUT);
  const loading = cands.loading || tools.loading;
  // The scenario points at the tool for its saved question: the candidate first, then the checked or approved tool.
  const asks = (c: ToolCandidate) => !!story && c.requests.includes(story.request);
  const storyCand = open.find((c) => asks(c) && c.reached_threshold) ?? open.find((c) => c.reached_threshold) ?? open.find(asks);
  const focusRef = useFocusTarget<HTMLDivElement>("tool:story", !loading);

  return (
    <div className="tools-page">
    <section className="panel" aria-labelledby="nt-title">
      <h3 id="nt-title">Repeated questions that could become tools</h3>
      <p className="small muted">
        When no tool fits, the agent writes one read-only query. If it needs the same query for other requests, code can check it on
        questions and values it never saw. Only a person turns it into a tool.
      </p>
      {problem && <p role="alert" className="err-text">{problem}</p>}
      {loading ? <div className="skeleton" aria-busy="true" /> : open.length + waiting.length + active.length + out.length === 0 ? <p className="empty">No repeated questions yet.</p> : (
        <div ref={focusRef}>
          {[...open].sort((a, b) => (a === storyCand ? -1 : b === storyCand ? 1 : 0)).map((c) => (
            <article key={c.key} className={`panel ${c === storyCand ? "story" : ""}`} aria-label={`Candidate ${c.suggested_name}`}>
              <p className="tool-title">A tool for questions like “{c.requests[0]}”</p>
              <p className="small muted">Proposed name <span className="mono">{c.suggested_name}</span>. {c.suggested_description.replace(/ Learned from .*$/, "")}</p>
              <p className="small muted">Asked {c.requests.length} time{c.requests.length === 1 ? "" : "s"}; it becomes a candidate tool at {c.threshold}. {c.reached_threshold ? "Threshold reached." : "Not yet."}</p>
              <details><summary>The questions it came from</summary><ul>{c.requests.map((r) => <li key={r}>{r}</li>)}</ul></details>
              <button type="button" className="send" disabled={busy !== null || !c.reached_threshold} onClick={() => act(c.key, () => api.checkTool(company, c.key))}>
                {busy === c.key ? "Checking…" : "Check this query"}
              </button>
              <span className="small muted"> Runs it on the original questions and on values it never saw.</span>
            </article>
          ))}

          {waiting.map((t) => (
            <article key={t.tool_id} className={`panel ${isStory(t) ? "story with-side" : ""}`} aria-label={`Checked ${t.name}`}>
              <div>
              <div className="card-head"><strong>{toolTitle(t)}</strong> <span className="mono small muted">{t.name}</span><span className={`pill ${t.checks.pass ? "ok" : "err"}`}>{t.checks.pass ? "Checks passed" : "Checks failed"}</span></div>
              <p>{t.description}</p>
              <Checks t={t} />
              <RepairTrail t={t} />
              {!t.checks.pass && <>
                <p className="small muted">A tool that failed its checks cannot be approved. Tool Forge can try to repair it.</p>
                {repair(t)}
              </>}
              <div className="actions">
                <button type="button" className="send" disabled={busy !== null || !t.checks.pass} onClick={() => act(t.tool_id, () => api.decideTool(company, t.tool_id, true, "Approved in the web app."))}>
                  {busy === t.tool_id ? "Working…" : "Approve as a tool"}
                </button>
                <button type="button" className="chip" disabled={busy !== null} onClick={() => act(t.tool_id, () => api.decideTool(company, t.tool_id, false, "Not approved in the web app."))}>Don't approve</button>
              </div>
              </div>
              {isStory(t) && fresh === false && cmp.data && <WhatChanges cmp={cmp.data} />}
            </article>
          ))}

          {active.length > 0 && (
            <>
              <h4>Approved tools ({active.length})</h4>
              <div className="actions">
                <button type="button" className="chip" disabled={busy !== null} onClick={() => act("health", () => api.toolsHealth(company))}>
                  {busy === "health" ? "Re-checking…" : "Re-check approved tools"}
                </button>
                <span className="small muted">Code runs each one again on its example and on new values, and counts its failures in real runs. Free.</span>
              </div>
              {active.map((t) => (
                <article key={t.tool_id} className="panel" aria-label={`Approved ${t.name}`}>
                  <div className="card-head"><strong>{toolTitle(t)}</strong> <span className="mono small muted">{t.name}</span><span className="pill ok">Active: the agent can call it</span></div>
                  <p>{t.description}</p>
                  {t.checks.health && (
                    <p className={`small ${t.checks.health.ok ? "ok-text" : "err-text"}`}>
                      {t.checks.health.ok ? "✓ Still works" : `✕ Needs repair: ${t.checks.health.reasons.join("; ")}`} (re-checked {t.checks.health.checked.replace("T", " ").slice(0, 16)})
                    </p>
                  )}
                  {t.checks.health && !t.checks.health.ok && repair(t)}
                  <div className="actions">
                    {story && <button type="button" className="send" onClick={() => onAsk("New tool")}>Ask the question again</button>}
                    <button type="button" className="chip" disabled={busy !== null} onClick={() => act(t.tool_id, () => api.retireTool(company, t.tool_id, "Retired in the web app."))}>Retire</button>
                  </div>
                </article>
              ))}
              {fresh === false && cmp.data && active.some(isStory) && (cmp.data.cold || cmp.data.with_learned_tools) && (
                <section className="panel" aria-label="Before and after the tool">
                  <h4>The same question, before and after the tool: recorded runs</h4>
                  <p className="small muted">Both are recorded runs of Muse Spark Open. One example; the benchmark is under Proof.</p>
                  <div className="agent-grid">
                    <Result title="Before: no tool" s={cmp.data.cold} />
                    <Result title="After: the approved tool" s={cmp.data.with_learned_tools} />
                  </div>
                </section>
              )}
            </>
          )}

          {out.length > 0 && (
            <details>
              <summary>Not in use ({out.length})</summary>
              <ul>{out.map((t) => <li key={t.tool_id}>{t.name}: {t.status}</li>)}</ul>
            </details>
          )}
        </div>
      )}
    </section>
    {fresh === false ? <Benchmark /> : fresh ? <ProofLine /> : null}
    </div>
  );
}
