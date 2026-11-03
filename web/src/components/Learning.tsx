import { useEffect, useState } from "react";
import { api, modelName, type CompareSide, type Lesson, withVisitor } from "../lib/api";
import { LessonActions } from "./LessonActions";
import { useApi } from "../lib/useApi";
import { useSettings } from "../lib/ctx";
import { AgentTag } from "./Badges";
import { Reply, shortTime } from "../lib/text";
import { FOCUS_EVENT, peekFocus, useFocusTarget } from "../lib/focus";
import { go } from "../lib/route";
import { ClosureStory, TripStrip } from "./EvidenceChart";
import { LifeCycle } from "./LifeCycle";
import { LearnFromRecords } from "./LearnFromRecords";

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
const KIND: Record<string, string> = {
  site_access: "gate limit", night_only: "night only", receiving_hours: "receiving hours", weekly_off: "day off", alias: "nickname",
  real_capacity: "real capacity", vendor_reliability: "vendor", closure: "road", time_window: "time window", moved_site: "moved site",
};

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

/** A scenario step asks for "lesson:<kind>" or "lesson:<kind>/<part>": pick the first lesson of that kind. */
function kindAsked(): string | null {
  const t = peekFocus();
  return t?.startsWith("lesson:") ? t.slice(7).split("/")[0] : null;
}

function Detail({ x, onChanged }: { x: Lesson; onChanged: () => void }) {
  const { company } = useSettings();
  const target = x.kind ? `lesson:${x.kind}` : null;
  const ref = useFocusTarget<HTMLElement>(target, true);
  const ev = useApi(() => api.evidence(company, x.lesson_id), [company, x.lesson_id]);
  const st = STATE[x.state] ?? { text: x.state, cls: "" };
  const e = ev.data;
  return (
    <article ref={ref} className="lesson-detail" aria-label={`Lesson ${x.lesson_id}`}>
      <div className="card-head">
        <span className="mono">{x.lesson_id}</span>
        <span className={`pill ${st.cls}`}>{st.text}</span>
        {x.kind && <span className="pill">{KIND[x.kind] ?? x.kind}</span>}
      </div>
      <h3 className="lesson-title">{x.display || x.what || x.claim}</h3>
      <p className="small muted">{x.miner?.model ? `Mined by ${modelName(x.miner.model)}` : "Not mined by a model here"}{x.created ? ` · ${x.created.slice(0, 10)}` : ""}</p>
      <p className="small muted">Evidence check: {x.gate.reason}</p>
      <LessonActions lesson={x} onChanged={onChanged} />
      {ev.loading ? <div className="skeleton" aria-busy="true" /> : e?.kind === "trips" ? <TripStrip e={e} target={target && `${target}/chart`} />
        : e?.kind === "closure" ? <ClosureStory e={e} target={target} />
        : e?.kind === "imported" ? <p className="note-box small">{e.note}</p>
        : x.miner?.evidence?.length ? (
          <details><summary>Evidence the miner cited</summary><ul>{x.miner.evidence.map((m) => <li key={m}>{m}</li>)}</ul></details>
        ) : null}
      {e && e.kind !== "none" && e.kind !== "imported" && (
        <p className="small"><a href={withVisitor(`/api/learning/lessons/${encodeURIComponent(x.lesson_id)}/evidence?company=${encodeURIComponent(company)}`)} target="_blank" rel="noreferrer">This evidence as data (JSON)</a></p>
      )}
      <LifeCycle lesson={x} target={target && `${target}/life`} />
    </article>
  );
}

export function Learning({ item }: { item?: string | null }) {
  const { company, requests, dataVersion, bumpData } = useSettings();
  const [version, setVersion] = useState(0); // a decision on a lesson reloads the lessons and the timeline
  const t = useApi(() => api.timeline(company), [company, version, dataVersion], { keep: true });
  const l = useApi(() => api.lessons(company), [company, version, dataVersion], { keep: true });
  const fleet = useApi(() => api.fleet(company), [company]);
  const cmpRef = useFocusTarget<HTMLElement>("compare", true);
  const request = requests.find((r) => r.label === "English")?.request;
  const cmp = useApi(() => (request ? api.compare(company, request) : Promise.resolve(null)), [company, request]);
  const [asked, setAsked] = useState<string | null>(kindAsked);
  useEffect(() => {
    const on = () => { const k = kindAsked(); if (k) setAsked(k); };
    window.addEventListener(FOCUS_EVENT, on);
    return () => window.removeEventListener(FOCUS_EVENT, on);
  }, []);
  const vehicle = (id: string) => {
    const v = fleet.data?.vehicles.find((x) => x.vehicle_id === id);
    return v ? `${v.class}, ${v.length_ft} ft` : "";
  };
  const lessons = l.data ?? [];
  // A step's request wins over the address once; after that the address (a click in the list) decides.
  const byKind = asked ? lessons.find((x) => x.kind === asked) : undefined;
  const selected = byKind ?? lessons.find((x) => x.lesson_id === item) ?? lessons.find((x) => x.state.startsWith("ACTIVE")) ?? lessons[0];
  useEffect(() => { if (byKind) { setAsked(null); go(`learning/${byKind.lesson_id}`); } }, [byKind?.lesson_id]); // eslint-disable-line react-hooks/exhaustive-deps
  // On a narrow screen the lesson opens below the list: bring it into view when one is chosen by address.
  const ready = !!l.data;
  useEffect(() => {
    if (item && ready && window.matchMedia("(max-width: 900px)").matches) document.querySelector(".lesson-detail")?.scrollIntoView({ block: "start" });
  }, [item, ready]);
  const groups: [string, typeof lessons][] = [
    ["Waiting for a person", lessons.filter((x) => WAITING.has(x.state))],
    ["Active", lessons.filter((x) => x.state.startsWith("ACTIVE"))],
    ["Rejected or retired", lessons.filter((x) => !WAITING.has(x.state) && !x.state.startsWith("ACTIVE"))],
  ];
  return (
    <div className="learning">
      <h3>What it has learned</h3>
      <p className="small muted">The Lesson Miner proposes, code checks the evidence, and a person approves each lesson before it changes any plan.
        You can undo an approval, retire a lesson or approve it again. That changes your own workspace and what live runs use; the saved runs stay as they were recorded.</p>
      <LearnFromRecords />
      {l.loading ? <div className="skeleton" aria-busy="true" /> : lessons.length === 0 ? <p className="empty">Nothing learned yet for this company.</p> : (
        <div className="learning-panes">
          <nav className="lesson-list" aria-label="Lessons">
            {groups.map(([title, items]) => items.length > 0 && (
              <section key={title} aria-label={title}>
                <h4>{title} ({items.length})</h4>
                <ul className="plain">
                  {items.map((x) => {
                    const st = STATE[x.state] ?? { text: x.state, cls: "" };
                    const on = x.lesson_id === selected?.lesson_id;
                    return (
                      <li key={x.lesson_id}>
                        <button type="button" className={`lesson-row ${on ? "on" : ""}`} aria-current={on ? "true" : undefined}
                          title={st.text} onClick={() => go(`learning/${x.lesson_id}`)}>
                          <span className="mono small">{x.lesson_id}</span><span className="sr-only">: </span>
                          <span className="lesson-row-text">{x.display || x.what || x.claim}</span>
                          <span className={`pill ${st.cls}`}>{KIND[x.kind ?? ""] ?? st.text}</span>
                        </button>
                      </li>
                    );
                  })}
                </ul>
              </section>
            ))}
          </nav>
          {selected && <Detail key={selected.lesson_id} x={selected} onChanged={() => { setVersion((v) => v + 1); bumpData(); }} />}
        </div>
      )}

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
