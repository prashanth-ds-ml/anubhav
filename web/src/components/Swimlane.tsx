import type { AgentTurn, RunSteps } from "../lib/api";
import { modelName } from "../lib/api";
import { errorText, resultText } from "../lib/text";
import { AGENT_STYLE, label } from "../agents";
import type { RunEvent } from "../types";

export interface Block { col: number; turn: string; call: RunEvent; result?: RunEvent }

/** Each tool call with its result, in the order they happened. The column is the call's place in the whole run, so a
 * teammate's calls sit to the right of the hand-off that started them. */
export function blocksOf(events: RunEvent[]): Block[] {
  const used = new Set<number>();
  const out: Block[] = [];
  events.forEach((e, i) => {
    if (e.type !== "tool_call") return;
    const j = events.findIndex((r, k) => k > i && !used.has(k) && r.type === "tool_result" && r.agent_run_id === e.agent_run_id && r.payload.tool === e.payload.tool);
    if (j >= 0) used.add(j);
    out.push({ col: out.length, turn: e.agent_run_id, call: e, result: j >= 0 ? events[j] : undefined });
  });
  return out;
}

const short = (s: string, n = 34) => (s.length > n ? `${s.slice(0, n - 1)}…` : s);

/** A few words under the tool name: a hand-off, a failure, or what the call was for. */
function caption(b: Block): string {
  const a = (b.call.payload.arguments ?? {}) as Record<string, unknown>;
  if (b.call.payload.tool === "delegate" && typeof a.agent === "string") return `hands off to ${label(a.agent)}`;
  if (b.result && !b.result.payload.ok) return "✕ failed";
  if (typeof a.purpose === "string") return short(a.purpose);
  if (b.call.payload.tool === "find_capability" && b.result) {
    const r = String(b.result.payload.result ?? "");
    return /"matches":\s*\[\s*\]/.test(r) ? "no tool fits" : short(resultText(b.result.payload.result), 30);
  }
  const first = Object.values(a).find((v) => typeof v === "string") as string | undefined;
  return first ? short(first) : "";
}

/** Every step of a run, one lane per agent, in time order from left to right. Each step is a button: choosing it shows its
 * arguments and the answer it got. Failed steps are red and say so in words; a fixed one is green. */
export function Swimlane({ run, selected, onSelect, fixedSeqs }: { run: RunSteps; selected: number | null; onSelect: (seq: number) => void; fixedSeqs: Set<number> }) {
  const blocks = blocksOf(run.events);
  const cols = blocks.length + 2; // the person asks, every call, the answer
  const template = { gridTemplateColumns: `130px repeat(${cols}, minmax(104px, 1fr))` };
  const lane = (t: AgentTurn) => {
    const mine = blocks.filter((b) => b.turn === t.agent_run_id);
    const color = (AGENT_STYLE[t.agent] ?? AGENT_STYLE.code).color;
    return (
      <div key={t.agent_run_id} className="sl-lane" style={{ ...template, ["--lane" as string]: color }} role="group"
        aria-label={`${label(t.agent)}${t.caller ? `, asked by ${label(t.caller)}` : ""}: ${t.tool_calls} tool call${t.tool_calls === 1 ? "" : "s"}${t.tool_errors ? `, ${t.tool_errors} failed` : ""}`}>
        <div className="sl-head">
          <strong style={{ color }}>{label(t.agent)}</strong>
          <span className="small muted">{modelName(t.model ?? undefined)}</span>
        </div>
        {mine.map((b) => {
          const failed = !!b.result && !b.result.payload.ok;
          const fixed = !!b.result && fixedSeqs.has(b.result.seq);
          const on = selected === b.call.seq;
          return (
            <button key={b.call.seq} type="button" style={{ gridColumn: b.col + 3 }} aria-pressed={on}
              className={`sl-step ${failed ? "bad" : ""} ${fixed ? "fixed" : ""} ${b.call.payload.tool === "delegate" ? "handoff" : ""} ${on ? "on" : ""}`}
              onClick={() => onSelect(b.call.seq)}>
              <span className="sr-only">Step {b.col + 1}: </span>
              <span className="mono">{b.call.payload.tool}</span>
              <span className="small">{caption(b)}{fixed ? " ✓ fixed" : ""}</span>
            </button>
          );
        })}
      </div>
    );
  };
  return (
    <div className="sl-scroll" tabIndex={0} role="region" aria-label="Every step, one lane per agent, in time order">
      <div className="sl" style={{ minWidth: 130 + cols * 110 }}>
        <div className="sl-lane person" style={template} role="group" aria-label="The person">
          <div className="sl-head"><strong>Person</strong></div>
          <span className="sl-say" style={{ gridColumn: 2 }}>asks</span>
          {run.reply && <span className="sl-say answer" style={{ gridColumn: cols + 1 }}>gets the answer</span>}
        </div>
        {run.agents.map(lane)}
      </div>
    </div>
  );
}

/** The chosen step: who called what, with which arguments, and the answer it got (the raw record behind a toggle). */
export function StepDetail({ b }: { b?: Block }) {
  if (!b) return null;
  const a = (b.call.payload.arguments ?? {}) as Record<string, unknown>;
  const ok = b.result?.payload.ok;
  const answer = !b.result ? "No answer recorded." : ok ? resultText(b.result.payload.result) : errorText(b.result.payload.error);
  const shown = Object.entries(a).filter(([k]) => k !== "purpose");
  return (
    <section className="sl-detail" aria-label="The chosen step">
      <dl className="facts-list">
        <div><dt>Step {b.col + 1}</dt><dd><strong>{label(b.call.agent_id)} · <span className="mono">{b.call.payload.tool}</span></strong>{typeof a.purpose === "string" ? <> · purpose: “{a.purpose}”</> : null}</dd></div>
        {shown.length > 0 && <div><dt>What it sent</dt><dd><pre className="sl-args" tabIndex={0} aria-label="What it sent">{shown.map(([k, v]) => `${k}: ${typeof v === "string" ? v : JSON.stringify(v)}`).join("\n")}</pre></dd></div>}
        <div><dt>Answer it got</dt><dd className={ok === false ? "err-text" : ""}>{ok === false ? "✕ " : ""}{answer}</dd></div>
      </dl>
      <details className="raw"><summary>Raw call and answer (JSON)</summary><pre>{JSON.stringify({ call: b.call.payload, result: b.result?.payload ?? null }, null, 2)}</pre></details>
    </section>
  );
}
