import { CheckCircle2, Truck, XCircle } from "lucide-react";
import { api, type Lesson } from "../lib/api";
import { useApi } from "../lib/useApi";
import { useSettings } from "../lib/ctx";
import type { Draft, Vehicle } from "../types";

/** A site's gate-size lessons, checked against a truck: the rule comes from the lesson store, never from this file. */
export function gateCheck(lessons: Lesson[], sites: string[], v?: Vehicle) {
  if (!v) return null;
  const rule = lessons.find((l) => l.kind === "site_access" && l.state !== "REJECTED" && sites.includes(l.params?.site_id) && typeof l.params?.max_length_ft === "number");
  if (!rule) return null;
  return { ok: v.length_ft <= rule.params!.max_length_ft, rule, active: rule.state.startsWith("ACTIVE") };
}

export function GateLine({ g, lessonsOn }: { g: NonNullable<ReturnType<typeof gateCheck>>; lessonsOn?: boolean }) {
  const why = !g.active ? " The rule is retired, so the agent was not told it." : lessonsOn === false ? " Lessons were off for this run, so the agent was not told it." : "";
  return g.ok ? (
    <p className="gate ok-text"><CheckCircle2 size={16} aria-hidden /> Fits the learned gate rule: {g.rule.what}</p>
  ) : (
    <p className="gate err-text"><XCircle size={16} aria-hidden /> Too long for this gate: {g.rule.what}.{why}</p>
  );
}

const lessonText = (l: unknown) => (typeof l === "string" ? l : (l as { rule?: string })?.rule ?? JSON.stringify(l));

/** The plan a run drafted, in one glance: which truck, whether it fits what the company learned, and what it used. */
export function PlanCard({ runId, lessonsOn }: { runId: string; lessonsOn: boolean }) {
  const { company, dataVersion } = useSettings();
  const d = useApi(() => api.drafts(company, runId), [company, runId]);
  const f = useApi(() => api.fleet(company), [company]);
  const l = useApi(() => api.lessons(company), [company, dataVersion], { keep: true });
  const drafts: Draft[] = d.data?.drafts ?? [];
  if (drafts.length === 0) return null;
  return (
    <div className="plan-cards">
      {drafts.map((x) => {
        const v = f.data?.vehicles.find((y) => y.vehicle_id === x.vehicle_id);
        const g = gateCheck(l.data ?? [], x.load?.sites ?? [], v);
        const used = [...new Set((x.why?.lessons ?? []).map(lessonText))];
        return (
          <article key={x.draft_id} className={`plan-card ${g ? (g.ok ? "good" : "bad") : ""}`} aria-label={`Plan ${x.draft_id}`}>
            <div className="plan-truck">
              <Truck size={28} aria-hidden />
              <div>
                <p className="plan-size">{v ? `${v.length_ft} ft` : x.vehicle_id}</p>
                <p className="small muted">{x.vehicle_id}{v ? ` · ${v.class} · ${v.payload_kg.toLocaleString("en-IN")} kg` : ""}</p>
              </div>
              <div className="plan-meta small">
                <span className="mono">{x.draft_id}</span> · {x.orders.join(", ")}<br />
                <span className="muted">Draft only, not dispatched</span>
              </div>
            </div>
            {g && <GateLine g={g} lessonsOn={lessonsOn} />}
            <p className="small">
              {used.length ? <>Lessons it used: {used.map((u) => <span key={u} className="chip-sm">{u}</span>)}</> : <span className="muted">It used no learned lesson for this plan.</span>}
            </p>
          </article>
        );
      })}
    </div>
  );
}

/** The same request with and without lessons, side by side, from the saved runs. */
export function ComparePair({ request }: { request: string }) {
  const { company, dataVersion } = useSettings();
  const c = useApi(() => api.compare(company, request), [company, request]);
  const f = useApi(() => api.fleet(company), [company]);
  const o = useApi(() => api.orders(company), [company]);
  const l = useApi(() => api.lessons(company), [company, dataVersion], { keep: true });
  if (!c.data?.cold || !c.data.with_lessons) return null;
  const side = (title: string, s: typeof c.data.cold) => {
    const dr = s!.drafts[0];
    const v = f.data?.vehicles.find((y) => y.vehicle_id === dr?.vehicle_id);
    const sites = (dr?.orders ?? []).map((id) => o.data?.orders.find((x) => x.order_id === id)?.site_id).filter(Boolean) as string[];
    const g = gateCheck(l.data ?? [], sites, v);
    return (
      <div className={`pair-side ${g ? (g.ok ? "good" : "bad") : ""}`}>
        <p className="small muted">{title}</p>
        <p className="plan-size">{v ? `${v.length_ft} ft` : dr?.vehicle_id ?? "No draft"}</p>
        <p className="small">{dr?.vehicle_id}{v ? ` · ${v.class}` : ""}</p>
        {g && <p className={`small ${g.ok ? "ok-text" : "err-text"}`}>{g.ok ? "Fits the gate" : "Too long for the gate"}</p>}
      </div>
    );
  };
  return (
    <div className="pair" aria-label="Before and after">
      {side("Without lessons", c.data.cold)}
      <span className="pair-arrow" aria-hidden>→</span>
      {side("With approved lessons", c.data.with_lessons)}
    </div>
  );
}
