import { AlertOctagon, RefreshCw, ArrowRightLeft, BookMarked, FileText, Wrench, Sparkles, Play, Flag, Loader2, HelpCircle } from "lucide-react";
import type { RunEvent } from "../types";
import { AgentTag, Verdict } from "./Badges";
import { AGENT_STYLE, label } from "../agents";
import { modelName } from "../lib/api";
import { errorText, resultText } from "../lib/text";

interface Body { Icon: typeof Play; title: string; text?: string; mono?: boolean; cls?: string; role?: string; }

const argsText = (a: Record<string, unknown>) =>
  Object.entries(a ?? {}).map(([k, v]) => `${k}: ${typeof v === "string" ? v : JSON.stringify(v)}`).join(" · ");

/** Plain description of a single event (used for the key moments, which get a full card). */
export function describe(e: RunEvent): Body {
  const p = e.payload;
  switch (e.type) {
    case "agent_start":
      return { Icon: Play, title: `Started on ${modelName(p.model)}`, text: `${p.lessons_in_prompt ?? 0} approved lessons in its instructions` };
    case "tool_call": return { Icon: Wrench, title: `Calls ${p.tool}`, text: argsText(p.arguments), mono: true };
    case "tool_result": return { Icon: Wrench, title: `${p.tool}: ${p.ok ? "ok" : "failed"}`, text: p.ok ? resultText(p.result) : errorText(p.error), cls: p.ok ? "" : "err" };
    case "retry": return { Icon: RefreshCw, title: `Retry ${p.tool}, attempt ${p.attempt} of ${p.of}`, cls: "warn" };
    case "tool_missing": return { Icon: AlertOctagon, title: "No tool for this", text: `${p.need}. ${p.next_step}`, cls: "err", role: "alert" };
    case "handoff": return { Icon: ArrowRightLeft, title: `${label(p.from)} hands off to ${label(p.to)}`, text: p.brief, cls: "handoff" };
    case "lesson_used":
      return { Icon: BookMarked, title: `Used ${p.lessons.length === 1 ? "a lesson" : `${p.lessons.length} lessons`}`, text: p.lessons.map((l: any) => typeof l === "string" ? l : `${l.rule ?? l.text ?? ""}${l.evidence ? ` (${l.evidence})` : ""}`).join("; ") };
    case "validator_check": return checkBody(p);
    case "draft_created": return { Icon: FileText, title: `Draft ${p.draft_id} on ${p.vehicle_id}`, text: (p.orders ?? []).join(", ") };
    case "agent_done": return { Icon: Flag, title: `Done (${p.stop})`, text: `${p.tool_calls ?? 0} tool call${p.tool_calls === 1 ? "" : "s"}${p.cost_usd != null ? ` · $${p.cost_usd.toFixed(3)}` : ""}${(p.drafts ?? []).length ? ` · ${(p.drafts as unknown[]).length} draft` : ""}` };
    case "learning_event": return { Icon: Sparkles, title: `Learning: ${p.kind} ${String(p.decision).replace("_", " ")}`, text: p.note, cls: "ok" };
    case "needs_person": return { Icon: HelpCircle, title: "Needs a person", text: p.question, cls: "warn", role: "alert" };
  }
}

function checkBody(p: Record<string, any>): Body {
  const what = p.tool === "final_recheck" ? "Final re-check" : p.tool === "reply_check" ? "Reply check" : "Code check";
  const detail = p.pass ? (p.draft_id ? `Draft ${p.draft_id} is valid.` : "") : errorText(p.error ?? p.errors?.[0] ?? (p.claims ? "the reply claimed something unsupported" : ""));
  return { Icon: Flag, title: `${what}: ${p.pass ? "passed" : "failed"}`, text: detail, cls: p.pass ? "ok" : "warn" };
}

type Item =
  | { kind: "event"; e: RunEvent }
  | { kind: "step"; call: RunEvent; result?: RunEvent }
  | { kind: "draft"; e: RunEvent; check?: RunEvent };
interface Lane { agent: string; caller: string | null; depth: number; items: Item[]; }

/**
 * Turn the flat event list into lanes (one per agent turn). A tool call is merged with its result even when a teammate's
 * whole run sits between them (as with a hand-off), and a draft with the check that cleared it.
 */
export function buildLanes(events: RunEvent[]): Lane[] {
  const lanes: Lane[] = [];
  const push = (e: RunEvent, item: Item) => {
    const last = lanes[lanes.length - 1];
    if (last && last.agent === e.agent_id && last.depth === e.depth) last.items.push(item);
    else lanes.push({ agent: e.agent_id, caller: e.depth > 0 ? e.caller : null, depth: e.depth, items: [item] });
  };
  const used = new Set<number>();
  const resultFor = (i: number): number => {
    const c = events[i];
    for (let j = i + 1; j < events.length; j++) {
      const r = events[j];
      if (r.agent_run_id !== c.agent_run_id) continue;
      if (r.type === "tool_call") return -1; // the same agent called something else first: no result for this one
      if (r.type === "tool_result" && r.payload.tool === c.payload.tool && !used.has(j)) return j;
    }
    return -1;
  };
  for (let i = 0; i < events.length; i++) {
    if (used.has(i)) continue;
    const e = events[i];
    const next = events[i + 1];
    if (e.type === "agent_start" && e.depth > 0) continue; // the lane header and the hand-off card already say this
    if (e.type === "tool_call") {
      const j = resultFor(i);
      if (j >= 0) used.add(j);
      push(e, { kind: "step", call: e, result: j >= 0 ? events[j] : undefined });
    } else if (e.type === "validator_check" && e.payload.draft_id && next?.type === "draft_created" && next.payload.draft_id === e.payload.draft_id) {
      push(next, { kind: "draft", e: next, check: e });
      i++;
    } else if (e.type === "draft_created") {
      push(e, { kind: "draft", e });
    } else {
      push(e, { kind: "event", e });
    }
  }
  return lanes;
}

function Step({ call, result, finished }: { call: RunEvent; result?: RunEvent; finished: boolean }) {
  const failed = result && !result.payload.ok;
  return (
    <li className={`card step ${failed ? "err" : ""}`}>
      <div className="card-head">
        {result || finished ? <Wrench size={14} aria-hidden /> : <Loader2 size={14} className="spin" aria-hidden />}
        <strong className="mono">{call.payload.tool}</strong>
        {result ? <span className={`pill ${failed ? "err" : "ok"}`}>{failed ? "failed" : "ok"}</span> : !finished && <span className="small muted">running…</span>}
      </div>
      <div className="mono muted">{argsText(call.payload.arguments)}</div>
      {result && <div className={failed ? "" : "muted"}>{failed ? errorText(result.payload.error) : resultText(result.payload.result)}</div>}
      {result && !failed && typeof result.payload.result === "string" && /^\s*[[{]/.test(result.payload.result) && (
        <details className="raw"><summary>Details</summary><pre>{result.payload.result}</pre></details>
      )}
    </li>
  );
}

function Draft({ e, check }: { e: RunEvent; check?: RunEvent }) {
  const p = e.payload;
  return (
    <li className="card draft">
      <div className="card-head">
        <FileText size={16} aria-hidden />
        <strong>Draft {p.draft_id} on {p.vehicle_id}</strong>
        {check && <Verdict v={check.payload.pass ? "pass" : "fail"} />}
      </div>
      <p className="small">Order{(p.orders ?? []).length === 1 ? "" : "s"}: <span className="mono">{(p.orders ?? []).join(", ")}</span>{p.load ? ` · ${Math.round(p.load.kg).toLocaleString("en-IN")} kg` : ""}</p>
      {check && <p className="small muted">Checked by code before it was saved.</p>}
      <p className="small">Draft only. Nothing is dispatched until a person confirms.</p>
      <button type="button" className="linklike" onClick={() => { window.location.hash = "plans"; }}>See it under Route plans</button>
    </li>
  );
}

export function Timeline({ events }: { events: RunEvent[] }) {
  const finished = events.some((e) => e.type === "agent_done" && e.depth === 0);
  return (
    <ol className="timeline" aria-label="Run events">
      {buildLanes(events).map((lane, i) => {
        const color = (AGENT_STYLE[lane.agent] ?? AGENT_STYLE.code).color;
        return (
          <li key={i} className="lane" style={{ marginLeft: lane.depth * 16, borderLeftColor: color }}>
            <div className="lane-head">
              <AgentTag id={lane.agent} />
              {lane.caller && <span className="small muted">asked by {label(lane.caller)}</span>}
            </div>
            <ol className="lane-items">
              {lane.items.map((it, j) => {
                if (it.kind === "step") return <Step key={j} call={it.call} result={it.result} finished={finished} />;
                if (it.kind === "draft") return <Draft key={j} e={it.e} check={it.check} />;
                const b = describe(it.e);
                return (
                  <li key={j} className={`card ${b.cls ?? ""}`} role={b.role}>
                    <div className="card-head"><b.Icon size={16} aria-hidden /><strong>{b.title}</strong></div>
                    {b.text && <div className={b.mono ? "mono" : "muted"}>{b.text}</div>}
                  </li>
                );
              })}
            </ol>
          </li>
        );
      })}
    </ol>
  );
}
