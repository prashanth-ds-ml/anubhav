import { useEffect, useState } from "react";
import { api, modelName, type FixPair, type RunRow, type RunSteps, withVisitor } from "../lib/api";
import { useApi } from "../lib/useApi";
import { useSettings } from "../lib/ctx";
import { errorText, Reply, resultText, shortTime } from "../lib/text";
import { AGENT_STYLE, label } from "../agents";
import { go } from "../lib/route";
import { blocksOf, StepDetail, Swimlane } from "./Swimlane";

// Names for the demo's recorded runs, so a visitor can find the ones the scenarios talk about. This is the demo's script,
// read by people only; every other run is listed by its request.
const PICKED: Record<string, string> = {
  "demo:team:new-tool": "Busiest weekday, as a team",
  "demo:new-tool-before": "Busiest weekday, before the tool",
  "live:c5-learned-tool": "Busiest weekday, with the tool",
  "exp008:T01:cold:rt": "Jangaon truck, no lessons",
  "exp008:T01:lessons:rt": "Jangaon truck, with lessons",
  "demo:team:data": "Damaged cases: three agents",
  "demo:team:miner": "The Lesson Miner reads the records",
  "golden_path:ambiguous": "It asks when unsure (Warangal)",
};
const ORDER = Object.keys(PICKED);
const ALL_AGENTS = Object.keys(AGENT_STYLE).filter((a) => a !== "code");

const andList = (xs: string[]) => (xs.length < 2 ? xs.join("") : `${xs.slice(0, -1).join(", ")} and ${xs[xs.length - 1]}`);
const title = (r: { label?: string | null; request: string }) => (r.label && PICKED[r.label]) || r.request;

function RunItem({ r, on }: { r: RunRow; on: boolean }) {
  return (
    <li>
      <button type="button" className={`run-row ${on ? "on" : ""}`} aria-current={on ? "true" : undefined} onClick={() => go(`runs/${r.run_id}`)}>
        <strong className="run-title">{title(r)}</strong>
        <span className="small muted">
          {r.agents.map(label).join(" → ")} · {r.tool_calls} call{r.tool_calls === 1 ? "" : "s"}{r.model ? <> · {modelName(r.model)}</> : null}
          {r.mistakes ? <> · <span className="err-text">{r.mistakes} mistake{r.mistakes === 1 ? "" : "s"}</span></> : null}
          {r.fixed ? <> · <span className="ok-text">{r.fixed === r.mistakes ? "fixed" : `${r.fixed} fixed`}</span></> : null}
        </span>
      </button>
    </li>
  );
}

/** The line of a SQL query (or other argument) where the failed and the fixed call differ: what the agent changed. */
function changed(fix: FixPair): [string, string] | null {
  const text = (a: Record<string, unknown>) => Object.values(a ?? {}).filter((v) => typeof v === "string").join("\n");
  const x = text(fix.failed.arguments).split("\n");
  const y = text(fix.fixed.arguments).split("\n");
  for (let i = 0; i < Math.max(x.length, y.length); i++) if ((x[i] ?? "").trim() !== (y[i] ?? "").trim()) return [(x[i] ?? "").trim(), (y[i] ?? "").trim()];
  return null;
}

function FixCard({ fix, from }: { fix: FixPair; from?: string }) {
  const d = changed(fix);
  return (
    <section className="panel fix" aria-labelledby="fix-title">
      <h3 id="fix-title">A real mistake, fixed by the agent itself</h3>
      {from && <p className="small muted">From “{from}” · {label(fix.agent)}</p>}
      <div className="fix-step bad">
        <p><strong>Step {fix.failed.step} · <span className="mono">{fix.tool}</span> ✕ failed</strong></p>
        {d && <pre className="sl-args" tabIndex={0} aria-label="The line it sent">… {d[0]} …</pre>}
        <p className="small">{errorText(fix.failed.error)}</p>
      </div>
      <p className="fix-arrow" aria-hidden>↓</p>
      <div className="fix-step good">
        <p><strong>Step {fix.fixed.step} · <span className="mono">{fix.tool}</span> ✓ corrected</strong></p>
        {d && <pre className="sl-args" tabIndex={0} aria-label="The line it corrected">… {d[1]} …</pre>}
        <p className="small">{resultText(fix.fixed.result)}</p>
      </div>
      <p className="small muted">The tool refused the call and said why; the agent read the error and fixed it on a later call. No person stepped in.</p>
    </section>
  );
}

function WorkBars({ run }: { run: RunSteps }) {
  const top = Math.max(1, ...run.agents.map((a) => a.tool_calls));
  const idle = ALL_AGENTS.filter((a) => !run.agents.some((t) => t.agent === a));
  return (
    <section className="work" aria-labelledby="work-title">
      <h3 id="work-title">Work per agent in this run</h3>
      <ul className="plain">
        {run.agents.map((t) => {
          const color = (AGENT_STYLE[t.agent] ?? AGENT_STYLE.code).color;
          return (
            <li key={t.agent_run_id} className="work-row">
              <span className="work-name" style={{ color }}>{label(t.agent)}</span>
              <span className="work-track"><span className="work-bar" style={{ width: `${(100 * t.tool_calls) / top}%`, background: color }} /></span>
              <span className="small">
                {t.tool_calls} call{t.tool_calls === 1 ? "" : "s"}{t.tool_errors ? <> · <span className="err-text">{t.tool_errors} failed</span></> : ""} · ${t.own_cost_usd.toFixed(3)}
              </span>
            </li>
          );
        })}
      </ul>
      {idle.length > 0 && <p className="small muted">{andList(idle.map(label))} {idle.length === 1 ? "was" : "were"} not needed.</p>}
      {run.agents.length > 1 && <p className="small muted">Cost is each agent's own share; a teammate's cost is not counted twice.</p>}
    </section>
  );
}

function Detail({ id, example }: { id: string; example?: { fix: FixPair; from: string } }) {
  const s = useApi(() => api.steps(id), [id]);
  const [sel, setSel] = useState<number | null>(null);
  useEffect(() => setSel(null), [id]);
  if (s.loading) return <div className="skeleton" aria-busy="true" />;
  const run = s.data;
  if (!run) return <p className="empty">This run's record could not be read.</p>;
  const blocks = blocksOf(run.events);
  const fixedSeqs = new Set(run.fixes.map((f) => f.fixed.seq));
  const firstBad = run.fixes[0] ? blocks.find((b) => b.result?.seq === run.fixes[0].failed.seq) : undefined;
  const chosen = blocks.find((b) => b.call.seq === sel) ?? firstBad ?? blocks[blocks.length - 1];
  const live = /^ui:/.test(run.label ?? ""); // a visitor's own live run; the demo's recordings are replays
  return (
    <>
      <section className="panel run-main" aria-labelledby="run-title">
        <header className="run-head">
          <h2 id="run-title">“{run.request}”</h2>
          <p className="small muted">
            {title(run) !== run.request ? <><strong>{title(run)}</strong> · </> : null}
            {live ? "Live run" : "Recorded"} · {modelName(run.model ?? undefined)}{run.saved_at ? ` · ${shortTime(run.saved_at)}` : ""}
            {run.latency_s ? ` · ${run.latency_s.toFixed(1)} s` : ""}{run.cost_usd != null ? ` · $${run.cost_usd.toFixed(3)}` : ""}
          </p>
          <a className="small" href={withVisitor(`/api/runs/${encodeURIComponent(run.run_id)}`)} target="_blank" rel="noreferrer">Raw record (JSON)</a>
        </header>
        <Swimlane run={run} selected={chosen?.call.seq ?? null} onSelect={setSel} fixedSeqs={fixedSeqs} />
        <div className="run-body">
          <StepDetail b={chosen} />
          <WorkBars run={run} />
        </div>
      </section>
      <div className="run-below">
        {run.fixes[0] ? <FixCard fix={run.fixes[0]} /> : example ? <FixCard fix={example.fix} from={example.from} /> : (
          <section className="panel"><h3>Mistakes</h3><p className="small muted">No tool call failed in this run.</p></section>
        )}
        <section className="panel" aria-labelledby="ans-title">
          <h3 id="ans-title">Final answer</h3>
          {run.reply ? <div className="answer-box"><Reply text={run.reply} /></div> : <p className="small muted">This run ended without an answer.</p>}
        </section>
      </div>
    </>
  );
}

/** Runs: every recorded run and the visitor's own live runs, each opened as a timeline by agent with its full record. */
export function Runs({ item }: { item?: string | null }) {
  const { company } = useSettings();
  const list = useApi(() => api.runs(company), [company]);
  const rows = list.data ?? [];
  const picked = rows.filter((r) => r.label && PICKED[r.label]).sort((a, b) => ORDER.indexOf(a.label) - ORDER.indexOf(b.label));
  const rest = rows.filter((r) => !picked.includes(r));
  const current = rows.find((r) => r.run_id === item) ?? picked[0] ?? rows[0];
  // A run with a fixed mistake, shown as the example when the open run has none.
  const withFix = rows.find((r) => (r.fixed ?? 0) > 0 && r.run_id !== current?.run_id);
  const ex = useApi(() => (withFix ? api.steps(withFix.run_id) : Promise.resolve(null)), [withFix?.run_id]);
  const example = ex.data?.fixes[0] && withFix ? { fix: ex.data.fixes[0], from: title(withFix) } : undefined;
  // On a narrow screen the run opens below the list: bring it into view when one is chosen.
  useEffect(() => {
    if (item && window.matchMedia("(max-width: 900px)").matches) document.querySelector(".runs-detail")?.scrollIntoView({ block: "start" });
  }, [item]);
  return (
    <div className="runs-page">
      <nav className="panel runs-list" aria-labelledby="runs-title">
        <h2 id="runs-title">Runs you can inspect</h2>
        {list.loading ? <div className="skeleton" aria-busy="true" /> : rows.length === 0 ? <p className="empty">No runs for this company yet.</p> : (
          <>
            {picked.length > 0 && <ul className="plain">{picked.map((r) => <RunItem key={r.run_id} r={r} on={r.run_id === current?.run_id} />)}</ul>}
            {rest.length > 0 && (
              <details open={!!item && rest.some((r) => r.run_id === item)}>
                <summary className="small">All other runs ({rest.length})</summary>
                <ul className="plain">{rest.map((r) => <RunItem key={r.run_id} r={r} on={r.run_id === current?.run_id} />)}</ul>
              </details>
            )}
            <p className="small muted">{rows.length} runs, recorded and your own live ones. Every one opens as its raw JSON record too.</p>
          </>
        )}
      </nav>
      <div className="runs-detail">{current ? <Detail key={current.run_id} id={current.run_id} example={example} /> : null}</div>
    </div>
  );
}
