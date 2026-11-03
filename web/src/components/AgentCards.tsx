import type { ReactNode } from "react";
import { api, modelName, type AgentTotal, type ProofEntry, type RegistryRow } from "../lib/api";
import { useApi } from "../lib/useApi";
import { useSettings } from "../lib/ctx";
import { AGENT_STYLE } from "../agents";
import { go } from "../lib/route";
import { AgentScores, TeamCurve, type Curve } from "./TeamCurve";

// How each agent learns: a description of the design, for people. The numbers beside it come from the result files.
const HOW: Record<string, string> = {
  planner: "Approved lessons about the company, and changes to its own instructions that pass a paired test.",
  analyst: "Approved tools, and changes to its own instructions that pass a paired test.",
  tool_forge: "Queries it keeps writing become tools, after code checks them and a person approves.",
  lesson_miner: "Changes to its own instructions that pass a paired test; the code's evidence gate decides which lessons count.",
};

const pct = (x: number) => `${Math.round(x * 100)}%`;
const mean = (xs: number[]) => xs.reduce((a, b) => a + b, 0) / Math.max(xs.length, 1);
const VERDICT: Record<string, [string, string]> = { met: ["✓ bar met", "ok-text"], not_met: ["✕ bar not met", "err-text"], finding: ["a finding, no bar", "muted"], not_run: ["not run yet", "muted"] };

function Verdict({ r }: { r?: RegistryRow }) {
  if (!r) return null;
  const [t, cls] = VERDICT[r.verdict] ?? [r.verdict, ""];
  return <p className={`small ${cls}`}>{t}{r.summary ? `: ${r.summary}` : ""}</p>;
}

function Bar({ label, value, tone }: { label: string; value: number; tone: "base" | "now" }) {
  return (
    <div className="mbar">
      <span className="mbar-track"><span className={`mbar-fill ${tone}`} style={{ width: pct(value) }} /></span>
      <span className="small">{pct(value)} {label}</span>
    </div>
  );
}

/** What has been measured for one agent, read from /api/proof, with the experiment's own verdict. */
/** One line from EXP-014 for an agent: its own score, first version against final. */
function fromCurve(agent: string, c?: Curve): ReactNode {
  const a = c?.measured ? c.agents?.[agent] : undefined;
  if (!a) return null;
  const g = a.gain_pts;
  const mark = g == null ? "" : g > 0 ? "▲" : g < 0 ? "▼" : "=";
  const text = agent === "lesson_miner" ? `precision ${pct(a.v0?.precision ?? 0)} → ${pct(a.final?.precision ?? 0)}, recall ${pct(a.v0?.recall ?? 0)} → ${pct(a.final?.recall ?? 0)}`
    : agent === "planner" ? `unwritten rules ${pct(a.v0?.unwritten ?? 0)} → ${pct(a.final?.unwritten ?? 0)} as learning was added`
    : `${pct(a.v0?.rate ?? 0)} → ${pct(a.final?.rate ?? 0)} on its own ${a.v0?.n} questions`;
  const cls = g == null || g === 0 ? "" : g > 0 ? "ok-text" : "err-text";
  return <p className={`small ${cls}`}><span aria-hidden>{mark} </span>EXP-014 on Muse Spark 1.3: {text}{agent === "tool_forge" && g != null && g < 0 ? ", after its approved change" : ""}</p>;
}

function measured(agent: string, proof: Record<string, ProofEntry>, reg: Record<string, RegistryRow>, c?: Curve): ReactNode {
  const more = fromCurve(agent, c);
  if (agent === "planner" && proof["EXP-011R"]?.repeats?.length) {
    const r = proof["EXP-011R"].repeats!;
    return (
      <>
        <p className="small">Unwritten rules handled, single Planner:</p>
        <Bar label="given the raw notes" value={mean(r.map((x) => x.raw_notes_B))} tone="base" />
        <Bar label="with approved lessons" value={mean(r.map((x) => x.lessons_C))} tone="now" />
        <p className="small muted">EXP-011R · {r.length} repeats · Muse Spark Open</p>
        <Verdict r={reg["EXP-011R"]} />
        {proof["EXP-015"]?.pooled && (
          <p className="small">On Muse Spark 1.3, the live model (EXP-015): <strong>{pct(proof["EXP-015"].pooled.raw_notes_B)} → {pct(proof["EXP-015"].pooled.lessons_C)}</strong>, {reg["EXP-015"]?.verdict === "met" ? "✓ replicated" : "not replicated"} in {proof["EXP-015"].repeats?.length} repeats</p>
        )}
        {more}
      </>
    );
  }
  if (agent === "tool_forge" && proof["EXP-012b"]?.arms) {
    const { Q, T } = proof["EXP-012b"].arms as Record<string, { mean_tool_calls: number; n: number; answer_ok: number }>;
    const used = proof["EXP-012b"].decision?.learned_tool_used_in as string | undefined;
    return (
      <>
        {used && <p className="small">Learned tool used: <strong>{used.replace("/", " of ")}</strong> questions</p>}
        <p className="small">Tool calls: {Q.mean_tool_calls} → {T.mean_tool_calls} a question ({Math.round(100 * (1 - T.mean_tool_calls / Q.mean_tool_calls))}% fewer)</p>
        <p className="small muted">EXP-012b · {Q.n} held-out questions · Muse Spark Open</p>
        <Verdict r={reg["EXP-012b"]} />
        {proof["EXP-016"] && <p className="small err-text"><span aria-hidden>✕ </span>On Muse Spark 1.3 (EXP-016): no tool was made, so learned tools were used on {String(proof["EXP-016"].decision?.learned_tool_used_in ?? "0").replace("/", " of ")} questions</p>}
        {more}
      </>
    );
  }
  if (agent === "lesson_miner" && proof["EXP-009b"]?.pooled) {
    const p = proof["EXP-009b"].pooled;
    return (
      <>
        <p className="small">Precision <strong>{pct(p.precision)}</strong> ({p.true_passed} of {p.passed} passed were real)</p>
        <p className="small">Recall <strong>{pct(p.recall)}</strong> ({p.found} of {p.learnable} findable)</p>
        <p className="small">Trap rules admitted: <strong>{Array.isArray(p.traps_admitted) ? p.traps_admitted.length : p.traps_admitted}</strong></p>
        <p className="small muted">EXP-009b · offline mining on an unseen world</p>
        <Verdict r={reg["EXP-009b"]} />
        {more}
      </>
    );
  }
  return more ?? <p className="not-measured small">Not measured yet. EXP-014 will score it before and after; no number until it has run.</p>;
}

function Totals({ t }: { t?: AgentTotal }) {
  if (!t || t.runs === 0) return <p className="small muted">No runs for this company yet.</p>;
  return (
    <p className="small muted">
      In this company's runs: {t.runs} run{t.runs === 1 ? "" : "s"} · {t.tool_calls} tool calls · {t.tool_errors} failed · ${t.cost_usd.toFixed(2)}
    </p>
  );
}

/** Agents: how each one learns, what has been measured, its work in this company's runs, and what is not measured yet. */
export function AgentCards() {
  const { company, modelLabel } = useSettings();
  const agents = useApi(() => api.agents(company), [company]);
  const totals = useApi(() => api.agentTotals(company), [company]);
  const proofApi = useApi(() => api.proof(), []);
  const regApi = useApi(() => api.registry(), []);
  const curve = useApi(() => api.curve(), []);
  if (agents.loading || proofApi.loading || regApi.loading) return <div className="skeleton" aria-busy="true" />;
  if ((agents.data ?? []).length === 0) return <p className="empty">No agent data. The server may be unreachable.</p>;
  const proof = Object.fromEntries((proofApi.data ?? []).map((p) => [p.id, p]));
  const reg = Object.fromEntries((regApi.data?.experiments ?? []).map((r) => [r.id, r]));
  const team = proof["EXP-013"]?.decision as Record<string, { n: number; ok: number; routing: number; unsafe: number }> | undefined;
  const exp014 = reg["EXP-014"];
  const c = curve.data as Curve | null;
  return (
    <div className="agents-page">
      <section className="panel agents-head" aria-labelledby="ag-title">
        <div>
          <h2 id="ag-title">Each agent has its own way to learn</h2>
          <p className="small muted">Agents propose changes; code checks them; a person approves. The numbers below are measured. Where nothing is measured yet, it says so.</p>
          <p className="small muted">Changes to an agent's own instructions follow Google Research's Harness² method (Propose–Probe–Compose), in a bounded form.</p>
        </div>
        {team?.M0 && team.M1 && (
          <div className="team-line" aria-label="The team, EXP-013">
            <p className="small muted">The team (EXP-013, {team.M1.n} cases)</p>
            <p><strong>Right agent chosen: {pct(team.M0.routing)} → {pct(team.M1.routing)}</strong> after one learning round</p>
            <p className="small">Correct answers: {team.M0.ok} → {team.M1.ok} of {team.M1.n}, not improved · {team.M1.unsafe} unsafe</p>
            {team.S && <p className="small muted">One Planner alone: {team.S.ok} of {team.S.n}. The team is not more accurate.</p>}
          </div>
        )}
      </section>

      <div className="agent-cards">
        {agents.data!.map((a) => {
          const color = (AGENT_STYLE[a.agent] ?? AGENT_STYLE.code).color;
          const v = Number(a.version.match(/(\d+)$/)?.[1] ?? 0) + 1;
          return (
            <article key={a.agent} className="panel agent-card" style={{ borderTopColor: color }} aria-labelledby={`ag-${a.agent}`}>
              <header className="card-head">
                <h3 id={`ag-${a.agent}`} style={{ color }}>{a.name}</h3>
                {a.agent === "planner" && <span className="pill">orchestrator</span>}
                <span className="pill" title={`Saved as ${a.version}`}>Version {v}</span>
              </header>
              <p className="small">{a.purpose}</p>
              {a.tools && (
                <p className="small muted" title="Enforced in code: a call outside this list is refused">
                  <strong>May use:</strong> {[...(a.tools.categories ?? []).map((c) => c.replace(/_/g, " ")), ...(a.tools.names ?? [])].join(", ")}
                  {" "}· {(a.tools.actions ?? ["read"]).join(", ")} only
                </p>
              )}
              {!!a.skills?.length && (
                <details className="skills">
                  <summary className="small"><strong>Skills ({a.skills.length})</strong>: loaded when it needs one</summary>
                  <ul className="small">{a.skills.map((s) => <li key={s.name}><span className="mono">{s.name}</span>: {s.description}</li>)}</ul>
                </details>
              )}
              <h4 className="eyebrow">How it learns</h4>
              <p className="small">{HOW[a.agent] ?? "Not described."}</p>
              <p className="small muted">{a.versions_tried === 0 ? "No instruction changes tried yet." : `${a.versions_tried} instruction change${a.versions_tried === 1 ? "" : "s"} tried.`} Knows {a.knowledge_items} thing{a.knowledge_items === 1 ? "" : "s"} about this company. Live runs use the model chosen at the top (now {modelLabel}).</p>
              <h4 className="eyebrow">Measured</h4>
              {measured(a.agent, proof, reg, c ?? undefined)}
              <Totals t={totals.data?.find((t) => t.agent === a.agent)} />
            </article>
          );
        })}
      </div>

      <section className="panel" aria-labelledby="curve-title">
        <h3 id="curve-title">Does the whole team improve as it learns, and does each agent?</h3>
        {c?.measured ? (
          <>
            <TeamCurve c={c} />
            <h4>Each agent, first version against its final one, on the same questions</h4>
            <AgentScores c={c} names={Object.fromEntries(agents.data!.map((a) => [a.agent, a.name]))} />
          </>
        ) : (
          <>
            <p className="small muted">
              EXP-014{exp014?.plan ? ` · pre-registered ${exp014.plan.date.slice(0, 10)} (commit ${exp014.plan.commit})` : ""} · not run yet ·{" "}
              <button type="button" className="link-btn" onClick={() => go("proof")}>its plan is in Proof &amp; audit</button>
            </p>
            <div className="not-measured-grid">
              <p className="not-measured">The whole team, stage by stage: not measured yet. No numbers until the run is done.</p>
              {agents.data!.filter((a) => a.agent !== "planner").map((a) => (
                <p key={a.agent} className="not-measured small"><strong>{a.name}</strong>: first version against its final one, not measured yet.</p>
              ))}
            </div>
          </>
        )}
      </section>
    </div>
  );
}
