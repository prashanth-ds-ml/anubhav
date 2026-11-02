import { useState } from "react";
import { api, type CompareSide, type Lesson } from "../lib/api";
import { LessonActions } from "./LessonActions";
import { useApi } from "../lib/useApi";
import { useSettings } from "../lib/ctx";
import { AgentTag } from "./Badges";
import { Reply } from "../lib/text";
import { useFocusTarget } from "../lib/focus";
import { shortTime } from "../lib/text";

const STATE: Record<string, { text: string; cls: string }> = {
  ACTIVE_POLICY: { text: "Active rule: code enforces it", cls: "ok" },
  ACTIVE_ADVISORY: { text: "Active advice: the agent is told", cls: "ok" },
  CANDIDATE: { text: "Waiting for a person", cls: "warn" },
  NEEDS_EVIDENCE: { text: "Needs more evidence", cls: "warn" },
  CHALLENGED: { text: "Challenged", cls: "warn" },
  REJECTED: { text: "Rejected", cls: "err" },
  RETIRED: { text: "Retired", cls: "err" },
  EXPIRED: { text: "Expired", cls: "err" },
};
const WAITING = new Set(["CANDIDATE", "NEEDS_EVIDENCE", "CHALLENGED"]);

function Side({ title, s, vehicle }: { title: string; s: CompareSide | null; vehicle: (id: string) => string }) {
  if (!s) return <article className="panel"><h4>{title}</h4><p className="empty">No saved run.</p></article>;
  const v = s.drafts[0]?.vehicle_id;
  return (
    <article className="panel">
      <h4>{title}</h4>
      <p><strong>{v ? `Vehicle ${v}${vehicle(v) ? `: ${vehicle(v)}` : ""}` : "No draft"}</strong></p>
      <p className="small muted">{s.lessons_in_prompt} lessons in its instructions · {s.tool_calls} tool calls · ${s.cost_usd.toFixed(3)}</p>
      <details><summary>Its reply</summary><Reply text={s.reply} /></details>
    </article>
  );
}

function LessonItem({ x, target, onChanged }: { x: Lesson; target: string | null; onChanged: () => void }) {
  const ref = useFocusTarget<HTMLLIElement>(target, true);
  const st = STATE[x.state] ?? { text: x.state, cls: "" };
  return (
    <li ref={ref} className="panel">
      <div className="card-head"><span className="mono">{x.lesson_id}</span><span className={`pill ${st.cls}`}>{st.text}</span></div>
      <p>{x.what || x.claim}</p>
      <p className="small muted">Evidence check: {x.gate.reason}</p>
      {x.miner?.evidence && x.miner.evidence.length > 0 && (
        <details><summary>Evidence the miner cited</summary><ul>{x.miner.evidence.map((e) => <li key={e}>{e}</li>)}</ul></details>
      )}
      <LessonActions lesson={x} onChanged={onChanged} />
    </li>
  );
}

export function Learning() {
  const { company, requests, dataVersion } = useSettings();
  const [version, setVersion] = useState(0); // a decision on a lesson reloads the lessons and the timeline
  const t = useApi(() => api.timeline(company), [company, version, dataVersion], { keep: true });
  const l = useApi(() => api.lessons(company), [company, version, dataVersion], { keep: true });
  const cmpRef = useFocusTarget<HTMLElement>("compare", true);
  const fleet = useApi(() => api.fleet(company), [company]);
  const request = requests.find((r) => r.label === "English")?.request;
  const cmp = useApi(() => (request ? api.compare(company, request) : Promise.resolve(null)), [company, request]);
  const vehicle = (id: string) => {
    const v = fleet.data?.vehicles.find((x) => x.vehicle_id === id);
    return v ? `${v.class}, ${v.length_ft} ft` : "";
  };
  const lessons = l.data ?? [];
  const groups: [string, typeof lessons][] = [
    ["Waiting for a person", lessons.filter((x) => WAITING.has(x.state))],
    ["Active", lessons.filter((x) => x.state.startsWith("ACTIVE"))],
    ["Rejected or retired", lessons.filter((x) => !WAITING.has(x.state) && !x.state.startsWith("ACTIVE"))],
  ];
  return (
    <div>
      <section ref={cmpRef} className="panel" aria-labelledby="ba-title">
        <h3 id="ba-title">Same request, with and without what it learned</h3>
        {cmp.loading ? <div className="skeleton" aria-busy="true" /> : !cmp.data?.cold || !cmp.data.with_lessons ? (
          <p className="empty">No saved before-and-after pair for this company.</p>
        ) : (
          <>
            <p className="small muted">“{cmp.data.request}” Both are recorded runs of Muse Spark Open. This is one example; the benchmark is under Proof.</p>
            <div className="agent-grid">
              <Side title="Without lessons" s={cmp.data.cold} vehicle={vehicle} />
              <Side title="With approved lessons" s={cmp.data.with_lessons} vehicle={vehicle} />
            </div>
          </>
        )}
      </section>

      <h3>What it has learned</h3>
      <p className="small muted">A person approves each lesson before it changes any plan. Each one shows the evidence it was proposed from.</p>
      <p className="small muted">You can undo an approval, retire a lesson or approve it again. That changes your own workspace and what live runs use; the saved runs stay as they were recorded.</p>
      {l.loading ? <div className="skeleton" aria-busy="true" /> : lessons.length === 0 ? <p className="empty">Nothing learned yet for this company.</p> : groups.map(([title, items]) => items.length > 0 && (
        <section key={title} aria-label={title}>
          <h4>{title} ({items.length})</h4>
          <ul className="plain lessons">
            {items.map((x) => (
              <LessonItem key={x.lesson_id} x={x} onChanged={() => setVersion((v) => v + 1)}
                target={x.kind && lessons.find((y) => y.kind === x.kind) === x ? `lesson:${x.kind}` : null} />
            ))}
          </ul>
        </section>
      ))}

      <details className="timeline-box">
        <summary><h3>Learning timeline ({t.data?.length ?? "…"})</h3></summary>
        <p className="small muted">Every lesson and tool decision: proposed, checked, approved or refused, and by whom.</p>
        {t.loading ? <div className="skeleton" aria-busy="true" /> : (t.data ?? []).length === 0 ? (
          <p className="empty">No learning decisions yet.</p>
        ) : (
          <ol className="plain">{t.data!.map((e, i) => (
            <li key={i} className="panel"><AgentTag id={e.agent} /> <b>{e.kind} {e.decision.replace("_", " ")}</b>
              <div className="small muted">{shortTime(e.ts)} · by {e.by}</div><div>{e.what}</div>{e.note && <div className="small muted">{e.note}</div>}</li>
          ))}</ol>
        )}
      </details>
    </div>
  );
}
