import { modelName, type Lesson, type WorkspaceDraft } from "../lib/api";
import type { Draft, Vehicle } from "../types";
import { Sample } from "./Sample";
import { Verdict } from "./Badges";
import { WhyCard } from "./WhyCard";
import { DraftDecision, gateCheck, GateLine } from "./PlanCard";

export const day = (d: string) => (d ? new Date(d + "T00:00").toLocaleDateString("en-IN", { day: "numeric", month: "short" }) : "");
export const kg = (n: number) => `${Math.round(n).toLocaleString("en-IN")} kg`;

/** The plain-language status of a draft. Approved is still not a dispatch. */
export function statusOf(s: string): { text: string; tone: "wait" | "ok" | "err" | "off" } {
  if (s === "draft") return { text: "Draft · waiting for a person", tone: "wait" };
  if (s === "approved") return { text: "Approved (not dispatched)", tone: "ok" };
  if (s === "rejected") return { text: "Rejected", tone: "err" };
  if (s === "cancelled") return { text: "Cancelled", tone: "off" };
  return { text: "Recorded draft (not dispatched)", tone: "off" };
}

const SHORT: Record<string, string> = { draft: "Draft, waiting", approved: "Approved", rejected: "Draft rejected", cancelled: "Draft cancelled" };

/** A draft's status as a small chip; `short` for tight table cells. */
export function StatusChip({ status, short }: { status: string; short?: boolean }) {
  const s = statusOf(status);
  return <span className={`st st-${s.tone}`}>{short ? SHORT[status] ?? s.text : s.text}</span>;
}

/** Drafts holding a truck and its orders: waiting for a person, or approved (still not dispatched). */
export const isLive = (d: Draft) => d.status === "draft" || d.status === "approved";

export type PlanFilter = "all" | "draft" | "approved";

type Decision = { decision?: string; notes?: string; ts?: string };

function DraftRow({ x, v, lessons, isNew, recorded, onDecided }: { x: WorkspaceDraft; v?: Vehicle; lessons: Lesson[]; isNew: boolean; recorded: boolean; onDecided: () => void }) {
  const g = gateCheck(lessons, x.load?.sites ?? [], v);
  const sites = x.sites?.length ? x.sites : x.stops?.stops?.map((s) => `${s.name}, ${s.town}`) ?? [];
  const orders = x.orders ?? [];
  const warnings = x.warnings ?? [];
  const last = ((x.decisions ?? []) as Decision[]).at(-1);
  return (
    <article id={`draft-${x.draft_id}`} tabIndex={-1} className={`panel draft-row${isNew ? " is-new" : ""}`} aria-label={`Draft ${x.draft_id}, ${statusOf(x.status).text}`}>
      <header className="card-head">
        <StatusChip status={x.status} />
        {isNew && <span className="badge-new">New</span>}
        {recorded && <span className="st st-off">Recorded, not in your workspace</span>}
        <Verdict v={x.why?.checks?.every((k) => k.pass) === false ? "fail" : "pass"} />
      </header>
      <p className="draft-line">
        <strong className="mono">{x.draft_id}</strong> on <span className="mono">{x.vehicle_id}</span>
        {v && <span className="muted"> · {v.length_ft ?? "–"} ft {v.class ?? ""}, {v.payload_kg != null ? v.payload_kg.toLocaleString("en-IN") : "–"} kg payload</span>}
      </p>
      <p className="small">{orders.length === 1 ? "Order" : "Orders"} <span className="mono">{orders.join(", ") || "–"}</span>{x.load ? ` · ${kg(x.load.kg)}` : ""}</p>
      {sites.length > 0 && (
        <ol className="draft-sites small" aria-label="Sites in order">
          {sites.map((s, i) => <li key={`${s}-${i}`}>{s}</li>)}
        </ol>
      )}
      {x.stops?.stops?.length ? <p className="small muted">About {x.stops.total_km} km, {Math.round(Math.max(...x.stops.stops.map((s) => s.est_minutes_total ?? 0)))} min ({x.stops.method})</p> : null}
      <p className="small muted">
        {x.run_id ? <>Made by run <span className="mono">{x.run_id}</span></> : "Made by an agent run"}
        {x.model ? ` · ${modelName(x.model)}` : ""}
      </p>
      {g && <GateLine g={g} />}
      {warnings.length > 0 && <ul className="plain small">{warnings.map((w, i) => <li key={`${w.code}-${i}`}>{w.message}</li>)}</ul>}
      {last && x.status !== "draft" && (
        <p className="small">{last.decision === "approve" ? "Approved" : "Rejected"} by a person{last.notes ? <>: <q>{last.notes}</q></> : "."}{x.status === "approved" ? " It is still not dispatched." : ""}</p>
      )}
      {x.why && <WhyCard why={x.why} />}
      {x.status === "draft" && x.source === "live" && <DraftDecision d={x} onDecided={onDecided} />}
    </article>
  );
}

/** Every draft in this workspace, grouped by delivery date and newest first; the drafts of the run being viewed are
 * marked New. Drafts rebuilt from a recorded run are shown only for that run, and labelled as such. */
export function DraftList({ drafts, current, runId, vehicles, lessons, filter, setFilter, onDecided }: {
  drafts: WorkspaceDraft[]; current: WorkspaceDraft[]; runId: string | null; vehicles: Vehicle[]; lessons: Lesson[];
  filter: PlanFilter; setFilter: (f: PlanFilter) => void; onDecided: () => void;
}) {
  const mine = new Set(drafts.map((d) => d.draft_id));
  const newIds = new Set(current.map((d) => d.draft_id));
  const extra = current.filter((d) => !mine.has(d.draft_id));            // in the viewed run, not in this workspace
  const recorded = extra.some((d) => d.source === "run");
  const shown = drafts.filter((d) => filter === "all" || d.status === filter);
  const dates = [...new Set(shown.map((d) => d.delivery_date || ""))];
  const vOf = (id: string) => vehicles.find((y) => y.vehicle_id === id);
  const row = (x: WorkspaceDraft, rec: boolean) => (
    <DraftRow key={x.draft_id} x={x} v={vOf(x.vehicle_id)} lessons={lessons} isNew={!!runId && (newIds.has(x.draft_id) || x.run_id === runId)} recorded={rec} onDecided={onDecided} />
  );
  return (
    <>
      {extra.length > 0 && (
        <section aria-label="From the run you are viewing" className="draft-group">
          <h3 className="group-h">From the run you are viewing</h3>
          {recorded && <Sample tone="note" title="From a recorded run." what="This draft was rebuilt from the recording and is not in your workspace, so it cannot be approved here. Approving needs a live run." />}
          {extra.map((x) => row(x, x.source === "run"))}
        </section>
      )}
      {drafts.length === 0 && extra.length === 0 && <p className="empty">No plans yet. Try "Plan a truck" in the chat, and its draft appears here.</p>}
      {drafts.length > 0 && (
        <div className="filter-bar" role="group" aria-label="Show drafts">
          {(["all", "draft", "approved"] as PlanFilter[]).map((f) => (
            <button key={f} type="button" className="chip-sm" aria-pressed={filter === f} onClick={() => setFilter(f)}>
              {f === "all" ? `All (${drafts.length})` : f === "draft" ? `Waiting (${drafts.filter((d) => d.status === "draft").length})` : `Approved (${drafts.filter((d) => d.status === "approved").length})`}
            </button>
          ))}
        </div>
      )}
      {drafts.length > 0 && shown.length === 0 && <p className="empty">No drafts with this status.</p>}
      {dates.map((dt) => (
        <section key={dt} aria-label={`Drafts for delivery on ${day(dt) || "an unknown date"}`} className="draft-group">
          <h3 className="group-h">For delivery on {day(dt) || "an unknown date"}</h3>
          {shown.filter((d) => (d.delivery_date || "") === dt).map((x) => row(x, false))}
        </section>
      ))}
    </>
  );
}
