import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { useApi } from "../lib/useApi";
import { useSettings } from "../lib/ctx";
import { Ledger } from "./Ledger";
import { AgentCards } from "./AgentCards";
import { Proof } from "./Proof";
import { Learning } from "./Learning";
import { Sample } from "./Sample";
import { Verdict } from "./Badges";
import { WhyCard } from "./WhyCard";
import { NewTools } from "./NewTools";
import { gateCheck, GateLine } from "./PlanCard";
import { humanName } from "../lib/text";

const day = (d: string) => (d ? new Date(d + "T00:00").toLocaleDateString("en-IN", { day: "numeric", month: "short" }) : "");
const kg = (n: number) => `${Math.round(n).toLocaleString("en-IN")} kg`;

const TABS = ["Orders", "Route plans and drafts", "Fleet", "Company", "Ledger", "Agents", "Learning", "New tools", "Proof"] as const;

// Each tab has a short address (#plans, #ledger ...) so a link can open it directly.
const SLUGS = ["orders", "plans", "fleet", "company", "ledger", "agents", "learning", "tools", "proof"];

/** "expired: insurance_until" → "Insurance expired"; other reasons lose their underscores. */
const vehicleReason = (r: unknown): string => {
  if (Array.isArray(r)) return r.map(vehicleReason).join("; ");     // the server sends a list of reasons
  const s = String(r ?? "");
  const m = s.match(/^expired:\s*(\w+?)_until$/);
  return m ? `${humanName(m[1] === "puc" ? "PUC certificate" : m[1])} expired` : humanName(s);
};
const fromHash = () => TABS[Math.max(0, SLUGS.indexOf(window.location.hash.replace("#", "")))];

const FACTS: [string, (f: any) => string | undefined][] = [
  ["Service area", (f) => f.service_area && `${f.service_area.sites} sites in ${f.service_area.towns} towns, mostly ${f.service_area.most_sites_in.join(", ")}`],
  ["Clients", (f) => f.clients && `${f.clients.brands} brands, largest ${f.clients.largest.join(", ")}`],
  ["Fleet", (f) => f.fleet && `${f.fleet.vehicles} vehicles (${f.fleet.own} own, ${f.fleet.hired} hired from ${f.fleet.hired_from_vendors} vendors)`],
  ["Volume", (f) => f.volume && `${f.volume.orders} orders over ${f.volume.days} days, about ${f.volume.orders_per_day} a day`],
  ["Planners write in", (f) => f.planner_languages && Object.entries(f.planner_languages.by_share as Record<string, number>).map(([k, v]) => `${({ rt: "Roman Telugu", te: "Telugu", en: "English" } as Record<string, string>)[k] ?? k} ${v}%`).join(", ")],
  ["Busiest day", (f) => f.busiest_days && `${f.busiest_days.top.join(", ")} (quietest ${f.busiest_days.quietest})`],
];

export function Dashboard({ refreshKey, runId, onPlan, onAsk }: { refreshKey: number; runId: string | null; onPlan: (text: string) => void; onAsk: (label: string) => void }) {
  const { company, companies, dataVersion } = useSettings();
  const [tab, setTabState] = useState<(typeof TABS)[number]>(fromHash);
  useEffect(() => {
    const on = () => setTabState(fromHash());
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  const setTab = (t: (typeof TABS)[number]) => {
    setTabState(t);
    window.history.replaceState(null, "", `#${SLUGS[TABS.indexOf(t)]}`);
  };
  const o = useApi(() => api.orders(company), [company]);
  const f = useApi(() => api.fleet(company), [company]);
  const d = useApi(() => api.drafts(company, runId ?? undefined), [company, runId, refreshKey]);
  const c = useApi(() => api.company(company), [company]);
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
  return (
    <section aria-label="Dashboard">
      <ul className="kpis" aria-label="At a glance">
        <li><strong>{o.data ? orders.length : "…"}</strong> open orders</li>
        <li><strong>{o.data ? `${Math.round(orders.reduce((a, x) => a + x.kg, 0) / 1000)} t` : "…"}</strong> to move</li>
        <li><strong>{f.data ? vehicles.length : "…"}</strong> vehicles</li>
      </ul>
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
          <div className="tablewrap"><table className="orders">
            <caption className="small muted">Open orders for delivery on {day(o.data!.delivery_date)}</caption>
            <thead><tr><th>Order</th><th>Site</th><th className="col-load">Load</th><th><span className="sr-only">Action</span></th></tr></thead>
            <tbody>
              {orders.map((x) => (
                <tr key={x.order_id}>
                  <td><span className="mono">{x.order_id}</span><br /><span className="small muted">Window {x.window}{x.in_draft ? " · in a draft" : ""}</span></td>
                  <td>{x.site}<br /><span className="small muted">{x.town}<span className="only-narrow"> · {kg(x.kg)}</span></span></td>
                  <td className="col-load">{kg(x.kg)}</td>
                  <td><button className="plan" aria-label={`Plan a truck for ${x.site}, ${x.town}`} onClick={() => onPlan(`Plan a truck for ${x.site}, ${x.town} order.`)}>Plan<span className="more"> a truck</span></button></td>
                </tr>
              ))}
            </tbody>
          </table></div>
        ))}
        {tab === "Route plans and drafts" && (d.loading ? wait : (
          <>
            {d.data!.drafts.length === 0 && <p className="empty">No plans yet. Try "Plan a truck" in the chat, and its draft appears here.</p>}
            {d.data!.source === "run" && d.data!.drafts.length > 0 && <Sample tone="note" title="From a recorded run." what="This draft was rebuilt from the recording, so it cannot be approved here. Approving needs a live run." />}
            {d.data!.drafts.map((x) => {
              const v = vehicles.find((y) => y.vehicle_id === x.vehicle_id);
              const g = gateCheck(lessons.data ?? [], x.load?.sites ?? [], v);
              return (
              <article key={x.draft_id} className="panel">
                <header className="card-head">
                  <strong className="mono">{x.draft_id}</strong> on <span className="mono">{x.vehicle_id}</span>
                  {v && <span className="pill">{v.length_ft} ft · {v.class}</span>}
                  <Verdict v={x.why?.checks?.every((k) => k.pass) === false ? "fail" : "pass"} />
                </header>
                {g && <GateLine g={g} />}
                <p className="small muted">{x.status} · {x.orders.join(", ")} · {kg(x.load.kg)}</p>
                {x.stops && (
                  <>
                    <ol className="stops">{x.stops.stops.map((s) => <li key={s.stop}>{s.name}, {s.town} <span className="muted small">({s.leg_km} km from the previous stop)</span></li>)}</ol>
                    <p className="small">About {x.stops.total_km} km, {Math.round(Math.max(...x.stops.stops.map((s) => s.est_minutes_total)))} min <span className="muted">({x.stops.method})</span></p>
                  </>
                )}
                {x.warnings.length > 0 && <ul className="plain small">{x.warnings.map((w) => <li key={w.code}>{w.message}</li>)}</ul>}
                {x.why && <WhyCard why={x.why} />}
              </article>
              );
            })}
          </>
        ))}
        {tab === "Fleet" && (f.loading ? wait : vehicles.length === 0 ? <p className="empty">No vehicles to show.</p> : (
          <div className="tablewrap"><table>
            <caption className="small muted">Fleet on {day(f.data!.delivery_date)}</caption>
            <thead><tr><th>Vehicle</th><th>Class</th><th>Length</th><th>Payload kg</th><th>Status</th><th>Owner</th></tr></thead>
            <tbody>
              {vehicles.map((v) => (
                <tr key={v.vehicle_id}>
                  <td className="mono">{v.vehicle_id}</td><td>{v.class}</td><td>{v.length_ft} ft</td><td>{v.payload_kg.toLocaleString("en-IN")}</td>
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
        {tab === "Learning" && <Learning />}
        {tab === "New tools" && <NewTools onAsk={onAsk} />}
        {tab === "Proof" && <Proof />}
        {tab === "Agents" && <AgentCards />}
        {tab === "Ledger" && <Ledger refreshKey={refreshKey} />}
      </div>
    </section>
  );
}
