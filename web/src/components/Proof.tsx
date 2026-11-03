import { useState } from "react";
import { api, modelName, type ProofEntry, type RegistryRow } from "../lib/api";
import { useApi } from "../lib/useApi";
import { useFocusTarget } from "../lib/focus";
import { go } from "../lib/route";

// Proof & audit. Every figure here is read from /api/proof (the committed result files) or /api/proof/registry (the
// pre-registered experiments with their plan and result commits); nothing is typed into the page.

const GH = "https://github.com/prashanth-ds-ml/anubhav";
const blob = (path: string, at = "main") => `${GH}/blob/${at}/${path}`;
const commit = (h: string) => `${GH}/commit/${h}`;
const pct = (x: number) => `${Math.round(x * 100)}%`;
const frac = (s: string) => { const [a, b] = s.split("/").map(Number); return { a, b, v: b ? a / b : 0 }; };
const MARK: Record<string, [string, string, string]> = {
  met: ["✓", "bar met", "met"], not_met: ["✕", "bar not met", "not-met"], finding: ["●", "finding, set direction", "finding"], not_run: ["○", "not run", "not-run"],
};
const num = (id: string) => id.replace(/^EXP-/, "");
const day = (d?: string) => (d ? new Date(d.replace(" ", "T")).toLocaleString("en-IN", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", hour12: false }) : "");

/** EXP-011R per company: without lessons (raw-note search) against with approved lessons, unsafe drafts beside. */
function Dumbbell({ e }: { e: ProofEntry }) {
  const ref = useFocusTarget<HTMLElement>("proof:companies", true);
  const s = e.summary ?? {};
  const rows = ([["T01", "T01", "B", "C"], ["T02", "T02", "B", "C"], ["New company, day 1", "TNEW", "B", "E"]] as const)
    .filter(([, c, x, y]) => s[`${c}:${x}`] && s[`${c}:${y}`])
    .map(([name, c, x, y]) => ({ name, before: s[`${c}:${x}`], after: s[`${c}:${y}`] }));
  if (rows.length === 0) return null;
  // What did not improve: a family whose score with lessons is below the score without them, or zero.
  const worse: string[] = [];
  for (const c of ["T01", "T02"]) {
    const B = s[`${c}:B`]?.by_family ?? {}, C = s[`${c}:C`]?.by_family ?? {};
    for (const [fam, v] of Object.entries(C)) { const a = frac(v), b = frac(B[fam] ?? "0/0"); if (a.b && (a.a === 0 || a.v < b.v)) worse.push(`${fam.replace(/_/g, " ")}, ${a.a} of ${a.b} with lessons at ${c}`); }
  }
  const X0 = 150, X1 = 560, x = (v: number) => X0 + v * (X1 - X0), RH = 54, H = 40 + rows.length * RH;
  const said = rows.map((r) => `${r.name}: ${r.before.ok} to ${r.after.ok}, unsafe ${r.before.unsafe} to ${r.after.unsafe}`).join("; ");
  return (
    <section ref={ref} className="panel" aria-labelledby="dumb-title">
      <h3 id="dumb-title">On a world it had never seen, learning made every company's plans correct more often, with no unsafe drafts</h3>
      <p className="small muted">{e.id} · <strong>{modelName(e.model)}</strong> · {e.world?.replace("full_seed", "fresh seed ")} · {e.runs} runs · totals over the repeats · {e.measured_on}</p>
      <figure className="ev-figure" aria-label={`Correct plans per company, without and with approved lessons. ${said}.`}>
        <div className="ev-scroll" tabIndex={0} role="region" aria-label="Chart, scrolls sideways on small screens">
          <svg viewBox={`0 0 700 ${H}`} role="img" aria-label={said} className="chart">
            {[0, 0.5, 1].map((t) => (
              <g key={t}><line x1={x(t)} x2={x(t)} y1={22} y2={H - 6} className="grid" /><text x={x(t)} y={14} className="axis" textAnchor="middle">{pct(t)}</text></g>
            ))}
            <text x={640} y={14} className="axis" textAnchor="middle">unsafe drafts</text>
            {rows.map((r, i) => {
              const y = 44 + i * RH, b = frac(r.before.ok), a = frac(r.after.ok);
              return (
                <g key={r.name}>
                  <title>{`${r.name}: ${r.before.ok} without lessons, ${r.after.ok} with; unsafe ${r.before.unsafe} to ${r.after.unsafe}`}</title>
                  <text x={0} y={y + 5} className="row-label">{r.name}</text>
                  <line x1={x(b.v)} x2={x(a.v)} y1={y} y2={y} className="dumb-line" />
                  <circle cx={x(b.v)} cy={y} r={6} className="dot-before" />
                  <circle cx={x(a.v)} cy={y} r={8} className="dot-after" />
                  <text x={x(b.v) - 12} y={y + 5} className="val" textAnchor="end">{r.before.ok}</text>
                  <text x={x(a.v)} y={y - 14} className="val strong" textAnchor="middle">{r.after.ok}</text>
                  <text x={640} y={y + 5} className="val" textAnchor="middle">{r.before.unsafe} → {r.after.unsafe}</text>
                </g>
              );
            })}
          </svg>
        </div>
        <ul className="plain legend small" aria-label="Legend">
          <li><svg width="14" height="14" aria-hidden><circle cx="7" cy="7" r="5" className="dot-before" /></svg> without lessons, with raw-note search</li>
          <li><svg width="14" height="14" aria-hidden><circle cx="7" cy="7" r="6" className="dot-after" /></svg> with approved lessons (new company: the shared regional pack)</li>
        </ul>
        <details><summary className="small">See it as a table</summary>
          <table className="fit small"><thead><tr><th>Company</th><th>Without lessons</th><th>With lessons</th><th>Unsafe drafts</th></tr></thead>
            <tbody>{rows.map((r) => <tr key={r.name}><td>{r.name}</td><td>{r.before.ok}</td><td>{r.after.ok}</td><td>{r.before.unsafe} → {r.after.unsafe}</td></tr>)}</tbody></table>
        </details>
      </figure>
      {worse.length > 0 && <p className="small"><strong>Not improved:</strong> {worse.join("; ")}. The agent refuses an overload but does not finish a safe plan.</p>}
      {e.file && <p className="small"><a href={blob(`artifacts/benchmark/${e.file}`)} target="_blank" rel="noreferrer">Result file</a></p>}
    </section>
  );
}

/** Lesson mining precision against the bar fixed in advance (EXP-008 on its pre-registered measure, repeat 0). */
function Mining({ proof, reg }: { proof: Record<string, ProofEntry>; reg: Record<string, RegistryRow> }) {
  const rows = ([["EXP-008", "demo world, repeat 0"], ["EXP-009", "unseen world"], ["EXP-009b", "second unseen world"]] as const)
    .map(([id, where]) => {
      const e = proof[id];
      const m = id === "EXP-008" ? e?.repeats?.[0] : e?.pooled;
      return m ? { id, where, precision: m.precision as number, recall: m.recall as number, traps: Array.isArray(m.traps_admitted) ? m.traps_admitted.length : m.traps_admitted, bar: reg[id]?.bar?.precision } : null;
    }).filter((r): r is NonNullable<typeof r> => !!r);
  if (rows.length === 0) return null;
  const last = rows[rows.length - 1];
  const bar = rows.find((r) => r.bar)?.bar;
  return (
    <section className="panel" aria-labelledby="mine-title">
      <h3 id="mine-title">It learns the right things: {Math.round(last.precision * 10)} in 10 lessons that pass are real</h3>
      <p className="small muted">Scored against rules the data generator hid, which the system never sees. Lessons mined by Muse Spark 1.3.</p>
      <ul className="plain mine-rows" aria-label="Precision by experiment">
        {rows.map((r) => {
          const ok = r.bar === undefined ? null : r.precision >= r.bar;
          return (
            <li key={r.id} className="mine-row">
              <span className="small">{r.id} · {r.where}</span>
              <span className="mbar-track mine-track">
                <span className={`mbar-fill ${ok ? "now" : "base"}`} style={{ width: pct(r.precision) }} />
                {bar && <span className="mine-bar" style={{ left: pct(bar) }} aria-hidden />}
              </span>
              <span className={`small ${ok === null ? "" : ok ? "ok-text" : "err-text"}`}>
                <strong>{pct(r.precision)}</strong> {ok === null ? "" : ok ? "✓" : "✕"} precision · {pct(r.recall)} recall
              </span>
            </li>
          );
        })}
      </ul>
      <p className="small muted">{bar ? `Dashed line: the precision bar of ${pct(bar)}, set in advance. ` : ""}Trap rules admitted: {rows.map((r) => r.traps).join(", ")}. Tuning stopped once the bar was met.</p>
    </section>
  );
}

/** EXP-004: the open-weights model against Spark 1.3 on tool-calling tasks. */
function OpenWeights({ e }: { e?: ProofEntry }) {
  const arms = (e?.arms ?? []) as { tools: number; spark_open: { mean_success: number; mean_latency_s: number; runs: number }; spark_1_3: { mean_success: number; mean_latency_s: number } }[];
  if (arms.length === 0) return null;
  const close = arms.every((a) => Math.abs(a.spark_open.mean_success - a.spark_1_3.mean_success) <= 0.015);
  return (
    <section className="panel" aria-labelledby="ow-title">
      <h3 id="ow-title">{close ? "Open weights match: Muse Spark Open did as well as Spark 1.3" : "Muse Spark Open against Spark 1.3"}</h3>
      <p className="small muted">EXP-004 · {e!.measured_on}</p>
      <table className="fit small">
        <thead><tr><th>Task</th><th>Spark Open</th><th>Spark 1.3</th></tr></thead>
        <tbody>{arms.map((a) => (
          <tr key={a.tools}><td>{a.tools} tools</td><td>{(a.spark_open.mean_success * 100).toFixed(1)}% · {a.spark_open.mean_latency_s.toFixed(0)} s</td><td>{(a.spark_1_3.mean_success * 100).toFixed(1)}% · {a.spark_1_3.mean_latency_s.toFixed(0)} s</td></tr>
        ))}</tbody>
      </table>
      <p className="small muted">That is why the agents and every benchmark run on the open-weights model. Success is the share of tasks done right; seconds are the average per task.</p>
    </section>
  );
}

/** Every pre-registered experiment, the failed ones included, with its plan, result file and verdict. */
function Scoreboard({ rows }: { rows: RegistryRow[] }) {
  return (
    <section className="panel" aria-labelledby="score-title">
      <div className="score-head">
        <h3 id="score-title">Every experiment we pre-registered, including the ones that failed</h3>
        <ul className="plain legend small" aria-label="Verdicts">
          {Object.entries(MARK).map(([k, [m, t, cls]]) => <li key={k} className={`v-${cls}`}><span aria-hidden>{m}</span> {t}</li>)}
        </ul>
      </div>
      <p className="small muted">Each plan was committed before its first model call. Open one for its bar, plan, result file and commits.</p>
      <ul className="plain score-grid" aria-label={`${rows.length} experiments`}>
        {rows.map((r) => {
          const [m, t, cls] = MARK[r.verdict] ?? ["", r.verdict, ""];
          return (
            <li key={r.id}>
              <details className={`score-card v-${cls}`}>
                <summary><span aria-hidden>{m}</span><span className="sr-only">{t}: </span> <strong>{num(r.id)}</strong> {r.summary ?? r.question}</summary>
                <p className="small"><strong>{r.id}</strong> · {r.question}</p>
                {r.bar && <p className="small">Bar fixed in advance: {r.bar.text}</p>}
                <p className="small">Plan: {day(r.plan?.date)} · <a href={commit(r.plan!.commit)} target="_blank" rel="noreferrer" className="mono">{r.plan?.commit}</a></p>
                {r.result ? (
                  <p className="small">Result: {day(r.result.date)} · <a href={commit(r.result.commit)} target="_blank" rel="noreferrer" className="mono">{r.result.commit}</a> · <a href={blob(r.result.file)} target="_blank" rel="noreferrer">result file</a></p>
                ) : <p className="small muted">Not run yet.</p>}
                {r.custody === "same_commit" && <p className="small muted">Plan and result landed in one commit, so git cannot show which came first.</p>}
                {r.note && r.custody !== "same_commit" && <p className="small muted">{r.note}</p>}
              </details>
            </li>
          );
        })}
        <li>
          <div className="score-card seed">
            <p><strong>Your seed</strong>: a world nobody has seen</p>
            <code className="small">uv run python -m anubhav.data.generate --full --seed 4242</code>
          </div>
        </li>
      </ul>
    </section>
  );
}

/** One line per repeat, from without to with. Equal repeats draw on top of each other, and the label says so. */
function Slope({ title, sub, pairs, left, right, side, focus }: {
  title: string; sub: string; pairs: [number, number][]; left: string; right: string; side: React.ReactNode; focus?: string;
}) {
  const ref = useFocusTarget<HTMLElement>(focus ?? null, true);
  const XL = 70, XR = 290, y = (v: number) => 210 - v * 170;
  const ends = [...new Set(pairs.map((p) => p[1]))];
  const starts = [...new Set(pairs.map((p) => p[0]))].sort((a, b) => b - a);
  // Start labels: keep them at least 14 px apart.
  const ys: number[] = [];
  starts.forEach((v) => ys.push(Math.max(y(v), (ys[ys.length - 1] ?? -99) + 14)));
  const said = pairs.map(([a, b], i) => `repeat ${i + 1}: ${pct(a)} to ${pct(b)}`).join("; ");
  return (
    <section ref={ref} className="panel" aria-labelledby={`${title.slice(0, 12)}-t`.replace(/\W/g, "")}>
      <h3 id={`${title.slice(0, 12)}-t`.replace(/\W/g, "")}>{title}</h3>
      <p className="small muted">{sub}</p>
      <div className="slope-wrap">
        <figure className="ev-figure" aria-label={`${title}. ${said}.`}>
          <svg viewBox="0 0 480 250" role="img" aria-label={said} className="chart slope">
            <line x1={XL} x2={XL} y1={30} y2={215} className="grid" /><line x1={XR} x2={XR} y1={30} y2={215} className="grid" />
            {pairs.map(([a, b], i) => <line key={i} x1={XL} y1={y(a)} x2={XR} y2={y(b)} className="slope-line"><title>{`Repeat ${i + 1}: ${pct(a)} to ${pct(b)}`}</title></line>)}
            {pairs.map(([a, b], i) => <g key={`d${i}`}><circle cx={XL} cy={y(a)} r={5} className="dot-before" /><circle cx={XR} cy={y(b)} r={7} className="dot-after" /></g>)}
            {starts.map((v, i) => <text key={v} x={XL - 12} y={ys[i] + 4} className="val" textAnchor="end">{pct(v)}</text>)}
            {ends.map((v) => <text key={v} x={XR + 14} y={y(v) + 5} className="val strong">{pct(v)}{ends.length === 1 ? ` · all ${pairs.length} repeats` : ""}</text>)}
            <text x={XL} y={240} className="axis" textAnchor="middle">{left}</text>
            <text x={XR} y={240} className="axis" textAnchor="middle">{right}</text>
          </svg>
          <details><summary className="small">See it as a table</summary>
            <table className="fit small"><thead><tr><th>Repeat</th><th>{left}</th><th>{right}</th></tr></thead>
              <tbody>{pairs.map(([a, b], i) => <tr key={i}><td>{i + 1}</td><td>{pct(a)}</td><td>{pct(b)}</td></tr>)}</tbody></table>
          </details>
        </figure>
        <div className="slope-side small">{side}</div>
      </div>
    </section>
  );
}

/** Plan → run → result → verdict for every experiment, with the commits and files to check it. */
function Custody({ rows }: { rows: RegistryRow[] }) {
  return (
    <section className="panel" aria-labelledby="cust-title">
      <h3 id="cust-title">Check our claims: each one was fixed in advance, then run, then committed</h3>
      <p className="small muted">The commit times show each plan came before its result, except where the table says they landed together.</p>
      <div className="tablewrap">
        <table className="custody small">
          <thead><tr><th>Claim</th><th>1 · Plan frozen</th><th>2 · Run</th><th>3 · Result committed</th><th>4 · Verdict</th><th>Check it</th></tr></thead>
          <tbody>{rows.map((r) => {
            const [m, , cls] = MARK[r.verdict] ?? ["", "", ""];
            return (
              <tr key={r.id}>
                <td><strong>{r.id}</strong> {r.question}</td>
                <td className="nowrap">{day(r.plan?.date)} · <a className="mono" href={commit(r.plan!.commit)} target="_blank" rel="noreferrer">{r.plan?.commit}</a></td>
                <td>{r.result ? [r.runs ? `${r.runs} runs` : "", r.cost_usd ? `$${r.cost_usd.toFixed(2)}` : ""].filter(Boolean).join(" · ") || "—" : "not run yet"}</td>
                <td className="nowrap">{r.result ? <>{day(r.result.date)} · <a className="mono" href={commit(r.result.commit)} target="_blank" rel="noreferrer">{r.result.commit}</a>{r.custody === "same_commit" ? " (same commit)" : ""}</> : "—"}</td>
                <td className={`v-${cls}`}><span aria-hidden>{m} </span>{r.summary}</td>
                <td className="nowrap">
                  {r.result && <><a href={blob(r.result.file)} target="_blank" rel="noreferrer">result file</a> · </>}
                  <a href={blob("docs/trackers/experiments.md", r.plan!.commit)} target="_blank" rel="noreferrer">plan</a>
                </td>
              </tr>
            );
          })}</tbody>
        </table>
      </div>
    </section>
  );
}

/** EXP-013: the team of agents against one Planner, with the learning round. */
function Team({ e, reg }: { e?: ProofEntry; reg?: RegistryRow }) {
  const d = e?.decision as Record<string, { n: number; ok: number; unsafe: number; mean_cost: number; routing: number; handoffs: number }> | undefined;
  if (!d?.S || !d.M0 || !d.M1) return null;
  const rows: [string, (typeof d)["S"], boolean][] = [["Single Planner", d.S, false], ["Team", d.M0, true], ["Team after one learning round", d.M1, true]];
  return (
    <section className="panel" aria-labelledby="team-title">
      <h3 id="team-title">The team of agents is safe, but not more accurate than one Planner</h3>
      <p className="small muted">EXP-013 · {d.S.n} cases · {e!.measured_on}</p>
      <div className="tablewrap">
        <table className="fit small">
          <thead><tr><th>Arm</th><th>Correct</th><th>Unsafe</th><th>Cost a case</th><th>Right agent chosen</th></tr></thead>
          <tbody>{rows.map(([n, r, team]) => (
            <tr key={n}><td>{n}</td><td>{r.ok}/{r.n}</td><td>{r.unsafe}</td><td>${r.mean_cost.toFixed(3)}</td><td>{team ? pct(r.routing) : "n/a"}</td></tr>
          ))}</tbody>
        </table>
      </div>
      {reg?.summary && <p className="small">{reg.summary}.</p>}
    </section>
  );
}

/** The same protocol on both models: Muse Spark Open (EXP-011R) and Muse Spark 1.3, the model judges use live (EXP-015). */
function BothModels({ proof, reg }: { proof: Record<string, ProofEntry>; reg: Record<string, RegistryRow> }) {
  const runs = (["EXP-011R", "EXP-015"] as const).map((id) => ({ id, e: proof[id] })).filter((x) => x.e?.pooled);
  if (runs.length < 2) return null;
  const row = (label: string, f: (p: Record<string, any>) => string) => (
    <tr><th scope="row">{label}</th>{runs.map(({ id, e }) => <td key={id}>{f(e!.pooled!)}</td>)}</tr>
  );
  return (
    <section className="panel" aria-labelledby="both-title">
      <h3 id="both-title">Measured on both models: the results hold on Muse Spark 1.3, the model you try live</h3>
      <p className="small muted">The same 38 cases, arms, lessons, packs and judge, 3 repeats each, on a world neither had seen.</p>
      <div className="tablewrap">
        <table className="fit small">
          <thead><tr><th>Totals over 3 repeats</th>{runs.map(({ id, e }) => <th key={id} scope="col">{modelName(e!.model)} ({id})</th>)}</tr></thead>
          <tbody>
            {row("Unwritten rules: raw notes → approved lessons", (p) => `${pct(p.raw_notes_B)} → ${pct(p.lessons_C)}`)}
            {row("New company on day 1: alone → shared pack", (p) => `${pct(p.cold_B)} → ${pct(p.pack_E)}`)}
            {row("Unsafe drafts with lessons", (p) => String(p.C_unsafe))}
            <tr><th scope="row">Both bars met in each repeat</th>{runs.map(({ id, e }) => <td key={id}>{(e!.repeats ?? []).filter((r: any) => r.lessons_bar_met && r.transfer_bar_met).length} of {e!.repeats?.length} {reg[id]?.verdict === "met" ? "✓" : ""}</td>)}</tr>
            <tr><th scope="row">Runs · cost</th>{runs.map(({ id, e }) => <td key={id}>{e!.runs} · ${e!.cost_usd?.toFixed(2)}</td>)}</tr>
          </tbody>
        </table>
      </div>
      <p className="small">{runs.map(({ id, e }) => <a key={id} href={blob(`artifacts/benchmark/${e!.file}`)} target="_blank" rel="noreferrer" style={{ marginRight: 12 }}>{id} result file</a>)}</p>
    </section>
  );
}

function Benchmarks({ proof, reg }: { proof: Record<string, ProofEntry>; reg: RegistryRow[] }) {
  const byId = Object.fromEntries(reg.map((r) => [r.id, r]));
  const [m, setM] = useState<"EXP-011R" | "EXP-015">("EXP-011R");
  const shown = proof[m]?.summary ? proof[m] : proof["EXP-011R"];
  const both = !!proof["EXP-015"]?.summary && !!proof["EXP-011R"]?.summary;
  return (
    <>
      <div className="proof-top">
        <div>
          {both && (
            <div className="model-switch" role="group" aria-label="Model for the per-company chart">
              <span className="small muted">Model:</span>
              {(["EXP-011R", "EXP-015"] as const).map((id) => (
                <button key={id} type="button" className={`subtab ${m === id ? "on" : ""}`} aria-pressed={m === id} onClick={() => setM(id)}>
                  {modelName(proof[id].model)} ({id}){id === "EXP-015" ? ", live model" : ""}
                </button>
              ))}
            </div>
          )}
          {shown?.summary && <Dumbbell key={shown.id} e={shown} />}
          <Team e={proof["EXP-013"]} reg={byId["EXP-013"]} />
        </div>
        <div>
          <Mining proof={proof} reg={byId} />
          <OpenWeights e={proof["EXP-004"]} />
        </div>
      </div>
      <Scoreboard rows={reg} />
    </>
  );
}

function Claims({ proof, reg }: { proof: Record<string, ProofEntry>; reg: RegistryRow[] }) {
  const e = proof["EXP-011R"], reps = e?.repeats ?? [], p = e?.pooled;
  const gain = reg.find((r) => r.id === "EXP-011R")?.bar?.gain_pts;
  const team = proof["EXP-013"]?.decision as Record<string, { ok: number; n: number }> | undefined;
  const cap = e?.summary?.["T01:C"]?.by_family?.real_capacity;
  const byId = Object.fromEntries(reg.map((r) => [r.id, r]));
  return (
    <>
      <BothModels proof={proof} reg={byId} />
      {p && reps.length > 0 && (
        <div className="proof-top even">
          <Slope title={`Approved lessons lifted unwritten-rule accuracy from ${pct(p.raw_notes_B)} to ${pct(p.lessons_C)}`}
            sub={`EXP-011R · ${reps[0].n_unwritten} cases a repeat, ${reps.length} repeats · each line is one repeat · single Planner`}
            pairs={reps.map((r) => [r.raw_notes_B, r.lessons_C])} left="without lessons" right="with lessons" focus="proof:rules"
            side={<><p>{reps.map((r) => `+${Math.round(r.lessons_gain_pts)}`).join(", ")} points</p>{gain && <p className="muted">bar set in advance: +{gain}</p>}</>} />
          <Slope title={`A new company went from ${pct(p.cold_B)} to ${pct(p.pack_E)} on day 1, with nothing private leaked`}
            sub={`EXP-011R · ${reps[0].n_transfer} cases a repeat, ${reps.length} repeats · gate limits and nicknames · shared regional lessons only`}
            pairs={reps.map((r) => [r.cold_B, r.pack_E])} left="without shared pack" right="with shared pack" focus="proof:transfer"
            side={<><p>{e?.pack_leaks ?? 0} private details leaked</p><p>{p.C_unsafe} unsafe drafts with lessons</p></>} />
        </div>
      )}
      <Custody rows={reg} />
      <section className="panel" aria-labelledby="open-title">
        <h3 id="open-title">Not measured yet</h3>
        <ul className="small">
          <li>A real company's records: every result here uses synthetic companies, scored against rules the data generator hid.</li>
          <li>A dispatcher's own review of the learned lessons (the review kit is ready; not run yet).</li>
          <li>Voice accuracy on real Telugu speech: the transcription is checked by hand, not measured.</li>
        </ul>
      </section>
      <div className="proof-notes">
        <div className="note-box small"><strong>Reproduce without keys</strong><br /><code>uv run pytest -q</code>: every test runs without a model call.</div>
        <div className="note-box small"><strong>Frozen files can't drift</strong><br />The EXP-013 to EXP-016 scripts refuse to run if a frozen file's hash has changed.</div>
        <div className="note-box small"><strong>Not improved, and said so</strong><br />
          {cap ? `Real truck capacity: ${cap.replace("/", " of ")} with lessons. ` : ""}
          {team?.S && team.M1 ? `Team accuracy: ${team.M1.ok} of ${team.M1.n}, not better than one Planner (${team.S.ok}). ` : ""}
          {byId["EXP-014"]?.verdict === "not_met" ? `EXP-014: ${byId["EXP-014"].summary}. ` : ""}
          {byId["EXP-016"]?.verdict === "not_met" ? `EXP-016: ${byId["EXP-016"].summary}.` : ""}
        </div>
      </div>
    </>
  );
}

export function Proof({ item }: { item?: string | null }) {
  const proofApi = useApi(api.proof);
  const regApi = useApi(api.registry);
  const tab = item === "claims" ? "claims" : "bench";
  if (proofApi.loading || regApi.loading) return <div className="skeleton" aria-busy="true" />;
  const proof = Object.fromEntries((proofApi.data ?? []).map((x) => [x.id, x]));
  const reg = regApi.data?.experiments ?? [];
  if (Object.keys(proof).length === 0 && reg.length === 0) return <p className="empty">No results to show. The server may be unreachable.</p>;
  const tabs: [string, string][] = [["bench", "Benchmarks"], ["claims", "Check our claims"]];
  return (
    <div className="proof-page">
      <div className="subtabs" role="tablist" aria-label="Proof and audit">
        {tabs.map(([k, label]) => (
          <button key={k} type="button" role="tab" id={`proof-tab-${k}`} aria-selected={tab === k} aria-controls="proof-panel"
            className={`subtab ${tab === k ? "on" : ""}`} onClick={() => go(`proof/${k}`)}>{label}</button>
        ))}
      </div>
      <p className="small muted">Measured evidence from the pre-registered experiments, on synthetic companies. It is the same in both workspaces: switching to "Fresh start" or resetting doesn't change it.</p>
      <div id="proof-panel" role="tabpanel" aria-labelledby={`proof-tab-${tab}`}>
        {tab === "bench" ? <Benchmarks proof={proof} reg={reg} /> : <Claims proof={proof} reg={reg} />}
      </div>
      <p className="small muted">Every case was generated by the project's own code on synthetic companies. Numbers come from the committed result files; the raw data is at <a href="/api/proof" target="_blank" rel="noreferrer">/api/proof</a> and <a href="/api/proof/registry" target="_blank" rel="noreferrer">/api/proof/registry</a>.</p>
    </div>
  );
}
