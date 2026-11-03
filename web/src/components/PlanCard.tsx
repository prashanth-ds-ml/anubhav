import { CheckCircle2, Truck, XCircle } from "lucide-react";
import { useEffect, useState } from "react";
import { api, ApiError, modelName, type Lesson } from "../lib/api";
import { TruckScale } from "./TruckScale";
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
const limitOf = (g: NonNullable<ReturnType<typeof gateCheck>>) => g.rule.params!.max_length_ft as number;

/** What plain code checked on this draft, from the run's own record (why.checks). Creating a draft runs the validator
 * (weight and volume, vehicle papers, availability, written site limits); the final re-check runs it again at the end. */
function CodeChecks({ d, v, ruleSaysNo }: { d: Draft; v?: Vehicle; ruleSaysNo: boolean }) {
  const checks = d.why?.checks?.filter((c) => !c.draft_id || c.draft_id === d.draft_id) ?? [];
  if (checks.length === 0) return null;
  const made = checks.find((c) => c.tool === "create_dispatch_draft");
  const re = checks.find((c) => c.tool === "final_recheck");
  const items: [string, boolean][] = [];
  if (made) items.push([`Load fits${v && d.load ? ` (${Math.round(d.load.kg).toLocaleString("en-IN")} of ${v.payload_kg.toLocaleString("en-IN")} kg)` : ""}`, made.pass], ["Vehicle papers valid", made.pass]);
  if (re) items.push(["Final re-check", re.pass]);
  if (items.length === 0) return null;
  const all = items.every(([, ok]) => ok);
  return (
    <div className="code-checks" role="group" aria-label="What code checked">
      <ul className="plain">
        {items.map(([t, ok]) => <li key={t} className={ok ? "ok-text" : "err-text"}><span aria-hidden>{ok ? "✓" : "✕"} </span>{t}{ok ? "" : ": failed"}</li>)}
      </ul>
      <p className="small">{all ? <><strong>The code checks passed.</strong>{ruleSaysNo ? " Only the learned rule says no." : ""}</> : <strong>A code check failed.</strong>}</p>
    </div>
  );
}

/** A person's decision on a live draft: Approve (code re-checks it first) or Reject with a note. Neither dispatches.
 * Recorded drafts were never made in this workspace, so they offer nothing to decide. */
export function DraftDecision({ d, onDecided }: { d: Draft; onDecided: () => void }) {
  const { company } = useSettings();
  const [rejecting, setRejecting] = useState(false);
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const [status, setStatus] = useState(d.status);
  useEffect(() => setStatus(d.status), [d.status]); // decided in the other view (chat or Route plans)
  if (d.source !== "live") return null;
  async function send(decision: "approve" | "reject") {
    setBusy(true);
    setProblem(null);
    try {
      const out = await api.decideDraft(company, d.draft_id, { decision, notes: notes.trim(), revise: false });
      setStatus(out.status);
      setRejecting(false);
      onDecided();
    } catch (e) {
      setProblem(e instanceof ApiError ? e.message : "That did not work. Try again.");
    } finally {
      setBusy(false);
    }
  }
  if (status !== "draft") {
    return (
      <p className="small" role="status">
        <strong>{status === "approved" ? "Approved" : status === "rejected" ? "Rejected" : status}</strong>
        {status === "approved" ? " by you. It is still not dispatched: that happens outside Anubhav." : status === "rejected" ? " by you, with your note. The truck is free again." : ""}
      </p>
    );
  }
  return (
    <div className="draft-decide">
      {!rejecting ? (
        <div className="actions">
          <button type="button" className="send" disabled={busy} aria-label={`Approve draft ${d.draft_id}`} onClick={() => send("approve")}>{busy ? "Checking…" : "Approve draft"}</button>
          <button type="button" className="chip" disabled={busy} aria-label={`Reject draft ${d.draft_id} with a note…`} onClick={() => { setRejecting(true); setProblem(null); }}>Reject with a note…</button>
        </div>
      ) : (
        <form className="reason" onSubmit={(e) => { e.preventDefault(); if (notes.trim()) send("reject"); }}>
          <label htmlFor={`notes-${d.draft_id}`} className="small">What is wrong with this plan?</label>
          <input id={`notes-${d.draft_id}`} type="text" maxLength={300} value={notes} onChange={(e) => setNotes(e.target.value)} autoFocus />
          <div className="actions">
            <button type="submit" className="send" disabled={busy || !notes.trim()}>{busy ? "Working…" : "Reject it"}</button>
            <button type="button" className="chip" disabled={busy} onClick={() => setRejecting(false)}>Cancel</button>
          </div>
        </form>
      )}
      <p className="small muted">Approving re-checks the plan in code. Approved is still not dispatched.</p>
      {problem && <p role="alert" className="err-text">{problem}</p>}
    </div>
  );
}

/** The plan a run drafted, in one glance: which truck, whether it fits what the company learned, and what it used. */
export function PlanCard({ runId, lessonsOn }: { runId: string; lessonsOn: boolean }) {
  const { company, dataVersion, bumpData } = useSettings();
  const d = useApi(() => api.drafts(company, runId), [company, runId, dataVersion], { keep: true });
  // A busy server can miss the fleet lookup (the card would show a bare id instead of "32 ft"): ask again, up to 3 times.
  const [tries, setTries] = useState(0);
  const f = useApi(() => api.fleet(company), [company, tries], { keep: true });
  const missing = !f.loading && (d.data?.drafts ?? []).some((x) => !f.data?.vehicles.some((v) => v.vehicle_id === x.vehicle_id));
  useEffect(() => {
    if (!missing || tries >= 3) return;
    const t = setTimeout(() => setTries((n) => n + 1), 1500);
    return () => clearTimeout(t);
  }, [missing, tries]);
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
                <p className="plan-size">{v ? `${v.length_ft} ft` : f.loading || (missing && tries < 3) ? "…" : x.vehicle_id}</p>
                <p className="small muted">{x.vehicle_id}{v ? ` · ${v.class} · ${v.payload_kg.toLocaleString("en-IN")} kg payload` : ""}</p>
              </div>
              <div className="plan-meta small">
                <span className="mono">{x.draft_id}</span> · {x.orders.join(", ")}<br />
                <span className="muted">{x.source === "live" ? "Live draft, not dispatched" : "Draft only, not dispatched"}{x.model ? ` · ${modelName(x.model)}` : ""}</span>
              </div>
            </div>
            {g && v && <TruckScale rows={[{ vehicle: x.vehicle_id, length_ft: v.length_ft }]} limit={limitOf(g)} lesson={g.rule} />}
            {g && <GateLine g={g} lessonsOn={lessonsOn} />}
            <CodeChecks d={x} v={v} ruleSaysNo={!!g && !g.ok} />
            <p className="small">
              {used.length ? <>Lessons it used: {used.map((u) => <span key={u} className="chip-sm">{u}</span>)}</> : <span className="muted">It used no learned lesson for this plan.</span>}
            </p>
            <DraftDecision d={x} onDecided={bumpData} />
          </article>
        );
      })}
    </div>
  );
}

/** The same request with and without lessons, both trucks on one scale, from the saved runs. */
export function ComparePair({ request }: { request: string }) {
  const { company, dataVersion } = useSettings();
  const c = useApi(() => api.compare(company, request), [company, request]);
  const f = useApi(() => api.fleet(company), [company]);
  const o = useApi(() => api.orders(company), [company]);
  const l = useApi(() => api.lessons(company), [company, dataVersion], { keep: true });
  if (!c.data?.cold || !c.data.with_lessons) return null;
  const pairs: [string, NonNullable<typeof c.data.cold>][] = [["Without lessons", c.data.cold], ["With the approved lesson", c.data.with_lessons]];
  const sides = pairs.map(([title, s]) => {
    const dr = s.drafts[0];
    const v = f.data?.vehicles.find((y) => y.vehicle_id === dr?.vehicle_id);
    const sites = (dr?.orders ?? []).map((id) => o.data?.orders.find((x) => x.order_id === id)?.site_id).filter(Boolean) as string[];
    return { title, dr, v, g: gateCheck(l.data ?? [], sites, v) };
  });
  const g = sides.find((x) => x.g)?.g;
  if (g && sides.every((x) => x.v)) {
    return (
      <div className="pair-scale" aria-label="Before and after">
        <TruckScale rows={sides.map((x) => ({ label: x.title, vehicle: x.v!.vehicle_id, length_ft: x.v!.length_ft }))} limit={limitOf(g)} lesson={g.rule} />
      </div>
    );
  }
  return (
    <div className="pair" aria-label="Before and after">
      {sides.map((x) => (
        <div key={x.title} className={`pair-side ${x.g ? (x.g.ok ? "good" : "bad") : ""}`}>
          <p className="small muted">{x.title}</p>
          <p className="plan-size">{x.v ? `${x.v.length_ft} ft` : x.dr?.vehicle_id ?? "No draft"}</p>
          <p className="small">{x.dr?.vehicle_id}{x.v ? ` · ${x.v.class}` : ""}</p>
          {x.g && <p className={`small ${x.g.ok ? "ok-text" : "err-text"}`}>{x.g.ok ? "Fits the gate" : "Too long for the gate"}</p>}
        </div>
      ))}
    </div>
  );
}
