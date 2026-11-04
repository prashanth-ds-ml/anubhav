import { useEffect, useState } from "react";
import { api, type WorkspaceDraft } from "../lib/api";
import { useApi } from "../lib/useApi";
import { useSettings } from "../lib/ctx";
import { Ledger } from "./Ledger";
import { DraftList, StatusChip, day, isLive, kg, type PlanFilter } from "./DraftList";
import { humanName } from "../lib/text";
import { go, type Desk } from "../lib/route";

const NONE = Promise.resolve({ drafts: [] as WorkspaceDraft[], source: "live" });

const TABS = ["Orders", "Route plans and drafts", "Fleet", "Company", "Ledger"] as const;

// Each tab has a short address (#plans, #ledger ...) so a link can open it directly.
const SLUGS: Desk[] = ["orders", "plans", "fleet", "company", "ledger"];

/** "expired: insurance_until" → "Insurance expired"; other reasons lose their underscores. */
const vehicleReason = (r: unknown): string => {
  if (Array.isArray(r)) return r.map(vehicleReason).join("; ");     // the server sends a list of reasons
  const s = String(r ?? "");
  const m = s.match(/^expired:\s*(\w+?)_until$/);
  return m ? `${humanName(m[1] === "puc" ? "PUC certificate" : m[1])} expired` : humanName(s);
};

const FACTS: [string, (f: any) => string | undefined][] = [
  ["Service area", (f) => f.service_area && `${f.service_area.sites} sites in ${f.service_area.towns} towns, mostly ${f.service_area.most_sites_in.join(", ")}`],
  ["Clients", (f) => f.clients && `${f.clients.brands} brands, largest ${f.clients.largest.join(", ")}`],
  ["Fleet", (f) => f.fleet && `${f.fleet.vehicles} vehicles (${f.fleet.own} own, ${f.fleet.hired} hired from ${f.fleet.hired_from_vendors} vendors)`],
  ["Volume", (f) => f.volume && `${f.volume.orders} orders over ${f.volume.days} days, about ${f.volume.orders_per_day} a day`],
  ["Planners write in", (f) => f.planner_languages && Object.entries(f.planner_languages.by_share as Record<string, number>).map(([k, v]) => `${({ rt: "Roman Telugu", te: "Telugu", en: "English" } as Record<string, string>)[k] ?? k} ${v}%`).join(", ")],
  ["Busiest day", (f) => f.busiest_days && `${f.busiest_days.top.join(", ")} (quietest ${f.busiest_days.quietest})`],
];

export function Dashboard({ panel, refreshKey, runId, onPlan }: { panel: Desk; refreshKey: number; runId: string | null; onPlan: (text: string) => void }) {
  const { company, companies, dataVersion, bumpData } = useSettings();
  const tab = TABS[SLUGS.indexOf(panel)] ?? "Orders";
  const setTab = (t: (typeof TABS)[number]) => go(SLUGS[TABS.indexOf(t)]);
  const o = useApi(() => api.orders(company), [company, dataVersion], { keep: true });
  const f = useApi(() => api.fleet(company), [company, dataVersion], { keep: true });
  // Every draft in this workspace, kept across asks; and the drafts of the run being viewed, to mark them New.
  const d = useApi(() => api.workspaceDrafts(company), [company, refreshKey, dataVersion], { keep: true });
  const cur = useApi(() => (runId ? api.drafts(company, runId) : NONE), [company, runId, refreshKey, dataVersion], { keep: true });
  const c = useApi(() => api.company(company), [company]);
  const [orderFilter, setOrderFilter] = useState<"all" | "need">("all");
  const [planFilter, setPlanFilter] = useState<PlanFilter>("all");
  const [focusId, setFocusId] = useState<string | null>(null);
  const lessons = useApi(() => api.lessons(company), [company, dataVersion], { keep: true });
  const name = companies.find((x) => x.company === company)?.name ?? company;
  const wait = <div className="skeleton" aria-busy="true" />;
  // Arrow keys, Home and End move between tabs, as people expect from a tab list.
  function onKey(e: React.KeyboardEvent) {
    const i = TABS.indexOf(tab);
    const to = { ArrowRight: (i + 1) % TABS.length, ArrowLeft: (i + TABS.length - 1) % TABS.length, Home: 0, End: TABS.length - 1 }[e.key as string];
    if (to === undefined) return;
    e.preventDefault();
    setTab(TABS[to]);
    document.getElementById(`tab-${to}`)?.focus();
  }
  const orders = o.data?.orders ?? [];
  const vehicles = f.data?.vehicles ?? [];
  const drafts = d.data?.drafts ?? [];
  // Only the viewed run's own drafts (a reload keeps the last answer on screen, which may be an earlier run's).
  const current = (cur.data?.drafts ?? []).filter((x) => x.run_id === runId) as WorkspaceDraft[];
  const date = o.data?.delivery_date ?? "";
  // The newest draft holding an order (waiting or approved), else its newest draft of any status.
  const draftOf = (id: string) =>
    drafts.find((x) => isLive(x) && (x.orders ?? []).includes(id) && (!x.delivery_date || !date || x.delivery_date === date)) ?? drafts.find((x) => (x.orders ?? []).includes(id));
  const needsTruck = (x: (typeof orders)[number]) => (d.data ? !(draftOf(x.order_id) && isLive(draftOf(x.order_id)!)) : !x.in_draft);
  const need = orders.filter(needsTruck);
  const waiting = drafts.filter((x) => x.status === "draft");
  const approved = drafts.filter((x) => x.status === "approved");
  // Move focus to the row a summary item or a "See draft" button points at, once that row is on screen.
  useEffect(() => {
    if (!focusId) return;
    const el = document.getElementById(focusId);
    if (!el) return;
    el.focus();
    el.scrollIntoView?.({ block: "nearest" });
    setFocusId(null);
  }, [focusId, tab, drafts.length, orders.length, planFilter, orderFilter]);
  function show(what: "need" | "draft" | "approved") {
    if (what === "need") {
      setOrderFilter("need");
      go("orders");
      setFocusId(need[0] ? `order-${need[0].order_id}` : null);
    } else {
      setPlanFilter(what);
      go("plans");
      const first = (what === "draft" ? waiting : approved)[0];
      setFocusId(first ? `draft-${first.draft_id}` : null);
    }
  }
  function seeDraft(id: string) {
    setPlanFilter("all");
    go("plans");
    setFocusId(`draft-${id}`);
  }
  const ready = !!o.data && !!d.data;
  const work: ["need" | "draft" | "approved", number, string, string][] = [
    ["need", need.length, need.length === 1 ? "order needs a truck" : "orders need a truck", "Open orders with no draft yet"],
    ["draft", waiting.length, waiting.length === 1 ? "draft waiting for a person" : "drafts waiting for a person", "Drafts to approve or reject"],
    ["approved", approved.length, "approved, not dispatched", "Approved drafts; dispatching happens outside Anubhav"],
  ];
  return (
    <section aria-label="Dashboard">
      <ul className="kpis" aria-label="At a glance">
        <li><strong>{o.data ? orders.length : "…"}</strong> open orders</li>
        <li><strong>{o.data ? `${Math.round(orders.reduce((a, x) => a + x.kg, 0) / 1000)} t` : "…"}</strong> to move</li>
        <li><strong>{f.data ? vehicles.length : "…"}</strong> vehicles</li>
      </ul>
      <section className="work" aria-labelledby="work-h">
        <h2 id="work-h" className="work-h">Today's work</h2>
        <ul className="work-list">
          {work.map(([k, n, label, hint]) => (
            <li key={k}>
              <button type="button" className={`work-item work-${k}`} disabled={!ready || n === 0} title={hint}
                aria-label={ready ? `${n} ${label}${n ? ": show them" : ""}` : `${label}: loading`} onClick={() => show(k)}>
                <strong>{ready ? n : "…"}</strong> {label}
              </button>
            </li>
          ))}
        </ul>
      </section>
      <p className="small muted note">{name}: a synthetic company generated for this project, not real records.</p>
      <div role="tablist" aria-label="Company data" className="tabs" onKeyDown={onKey}>
        {TABS.map((t, i) => (
          <button
            key={t}
            id={`tab-${i}`}
            role="tab"
            aria-selected={tab === t}
            aria-controls="panel"
            tabIndex={tab === t ? 0 : -1}
            onClick={() => setTab(t)}
          >
            {t}
          </button>
        ))}
      </div>
      <div role="tabpanel" id="panel" aria-labelledby={`tab-${TABS.indexOf(tab)}`}>
        <h2 className="sr-only">{tab}</h2>
        {tab === "Orders" && (o.loading ? wait : orders.length === 0 ? <p className="empty">No orders to show. The server may be unreachable.</p> : (
          <>
            {orderFilter === "need" && (
              <p className="filter-bar small" role="status">
                Showing the {need.length} {need.length === 1 ? "order" : "orders"} with no draft yet.{" "}
                <button type="button" className="chip-sm" onClick={() => setOrderFilter("all")}>Show all {orders.length} orders</button>
              </p>
            )}
            <div className="tablewrap"><table className="orders">
              <caption className="small muted">Open orders for delivery on {day(o.data!.delivery_date)}</caption>
              <thead><tr><th>Order</th><th>Site</th><th className="col-load">Load</th><th><span className="sr-only">Action</span></th></tr></thead>
              <tbody>
                {(orderFilter === "need" ? need : orders).map((x) => {
                  const dr = d.data ? draftOf(x.order_id) : undefined;
                  const holds = !!dr && isLive(dr);
                  return (
                    <tr key={x.order_id} id={`order-${x.order_id}`} tabIndex={-1}>
                      <td>
                        <span className="mono">{x.order_id}</span><br /><span className="small muted">Window {x.window}</span>
                        {dr ? <><br /><StatusChip status={dr.status} short /> <span className="mono small">{dr.draft_id}</span></> : !d.data && x.in_draft ? <><br /><span className="small muted">In a draft</span></> : null}
                      </td>
                      <td>{x.site}<br /><span className="small muted">{x.town}<span className="only-narrow"> · {kg(x.kg)}</span></span></td>
                      <td className="col-load">{kg(x.kg)}</td>
                      <td>
                        {holds ? (
                          <button className="plan" aria-label={`See draft ${dr!.draft_id} for ${x.site}, ${x.town}`} onClick={() => seeDraft(dr!.draft_id)}>See<span className="more"> draft</span></button>
                        ) : (
                          <button className="plan" aria-label={`Plan a truck for ${x.site}, ${x.town}`} onClick={() => onPlan(`Plan a truck for ${x.site}, ${x.town} order.`)}>Plan<span className="more"> a truck</span></button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table></div>
          </>
        ))}
        {tab === "Route plans and drafts" && (d.loading ? wait : (
          <DraftList drafts={drafts} current={current} runId={runId} vehicles={vehicles} lessons={lessons.data ?? []}
            filter={planFilter} setFilter={setPlanFilter} onDecided={bumpData} />
        ))}
        {tab === "Fleet" && (f.loading ? wait : vehicles.length === 0 ? <p className="empty">No vehicles to show.</p> : (
          <div className="tablewrap"><table>
            <caption className="small muted">Fleet on {day(f.data!.delivery_date)}</caption>
            <thead><tr><th>Vehicle</th><th>Class</th><th>Length</th><th>Payload kg</th><th>Status</th><th>Owner</th></tr></thead>
            <tbody>
              {vehicles.map((v) => (
                <tr key={v.vehicle_id}>
                  <td className="mono">{v.vehicle_id}</td><td>{v.class}</td><td>{v.length_ft} ft</td><td>{v.payload_kg != null ? v.payload_kg.toLocaleString("en-IN") : "–"}</td>
                  <td>{v.free ? "Free" : vehicleReason(v.reason ?? v.status)}</td><td>{humanName(v.owner)}</td>
                </tr>
              ))}
            </tbody>
          </table></div>
        ))}
        {tab === "Company" && (c.loading ? wait : !c.data ? <p className="empty">No company data.</p> : (
          <div className="panel">
            <h3>{name}</h3>
            <dl className="facts-list">
              {FACTS.map(([k, fn]) => { const v = fn(c.data!.facts); return v ? <div key={k}><dt>{k}</dt><dd>{v}</dd></div> : null; })}
            </dl>
            <h4>Written rules ({c.data.written_rules.length})</h4>
            <ul>{c.data.written_rules.map((r) => <li key={r.id}>{r.text}</li>)}</ul>
          </div>
        ))}
        {tab === "Ledger" && <Ledger refreshKey={refreshKey} />}
      </div>
    </section>
  );
}
