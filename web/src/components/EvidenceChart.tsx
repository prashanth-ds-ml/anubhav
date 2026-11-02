import type { Evidence, TripRow } from "../lib/api";
import { useFocusTarget } from "../lib/focus";

// Charts of a lesson's evidence, drawn from /api/learning/lessons/{id}/evidence. Every number comes from that response.
// Marks carry their meaning by shape first (filled dot delivered, hollow ring part-delivered, cross refused), colour second;
// each mark has a tooltip, and each chart has a table view.

const WEEKDAY = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const STATUS: Record<string, string> = { delivered: "delivered", partial: "part delivered", returned: "turned back" };
const W = 760, H = 210, L = 56, R = 12, T = 14, B = 26;
const day = (d: string) => new Date(d + "T00:00").getTime();
const fmt = (d: string) => new Date(d + "T00:00").toLocaleDateString("en-IN", { day: "numeric", month: "short" });

interface Axis { title: string; label: string; value: (r: TripRow) => number; min: number; max: number; ticks: { v: number; t: string }[];
  guides: { v: number; t: string }[]; band?: [number, number][]; bandLabel?: string }

/** The measure each kind of lesson is about, and the limit it learned, as a y axis. */
function axisFor(e: Extract<Evidence, { kind: "trips" }>): Axis {
  const lim = e.limit;
  if (e.lesson_kind === "site_access") {
    const mx = lim.max_length_ft;
    return { title: "truck length", label: "ft", value: (r) => r.length_ft ?? 0, min: 0, max: 34,
      ticks: [{ v: 10, t: "10 ft" }, { v: 32, t: "32 ft" }], guides: mx ? [{ v: mx, t: `limit it learned: ${mx} ft` }] : [] };
  }
  if (e.lesson_kind === "weekly_off") {
    return { title: "weekday", label: "", value: (r) => 6 - r.weekday, min: -0.5, max: 6.5,
      ticks: WEEKDAY.map((t, i) => ({ v: 6 - i, t })), guides: [], band: lim.weekday != null ? [[6 - lim.weekday - 0.5, 6 - lim.weekday + 0.5]] : [], bandLabel: "the day it learned is closed" };
  }
  const hourTicks = [0, 6, 12, 18, 24].map((v) => ({ v, t: `${String(v).padStart(2, "0")}:00` }));
  if (e.lesson_kind === "night_only" && lim.from_hour != null && lim.to_hour != null) {
    return { title: "arrival hour", label: "", value: (r) => r.hour, min: 0, max: 24, ticks: hourTicks, guides: [],
      band: [[lim.from_hour, 24], [0, lim.to_hour]], bandLabel: `receives only ${lim.from_hour}:00–${lim.to_hour}:00` };
  }
  return { title: "arrival hour", label: "", value: (r) => r.hour, min: 0, max: 24, ticks: hourTicks,
    guides: lim.until_hour != null ? [{ v: lim.until_hour, t: `receives until ${lim.until_hour}:00` }] : [] };
}

function Mark({ r, x, y }: { r: TripRow; x: number; y: number }) {
  const tip = `${fmt(r.date)}, ${String(r.hour).padStart(2, "0")}:00 · ${r.vehicle_id} (${r.vehicle_class}${r.length_ft ? `, ${r.length_ft} ft` : ""}) · ${STATUS[r.status] ?? r.status}${r.wait_min ? ` · waited ${r.wait_min} min` : ""}`;
  return (
    <g className={`ev-mark ${r.status}`}>
      <title>{tip}</title>
      <circle cx={x} cy={y} r={10} fill="transparent" />
      {r.status === "returned" ? (
        <path d={`M${x - 5} ${y - 5}L${x + 5} ${y + 5}M${x + 5} ${y - 5}L${x - 5} ${y + 5}`} stroke="var(--chart-bad)" strokeWidth={2.5} strokeLinecap="round" />
      ) : r.status === "partial" ? (
        <circle cx={x} cy={y} r={4.5} fill="var(--surface)" stroke="var(--chart-ok)" strokeWidth={2.5} />
      ) : (
        <circle cx={x} cy={y} r={5} fill="var(--chart-ok)" stroke="var(--surface)" strokeWidth={2} />
      )}
    </g>
  );
}

/** Every trip to the lesson's site, by date and by the measure the lesson is about. */
export function TripStrip({ e, target }: { e: Extract<Evidence, { kind: "trips" }>; target: string | null }) {
  const ref = useFocusTarget<HTMLElement>(target, true);
  const a = axisFor(e);
  const rows = e.rows;
  if (rows.length === 0) return <p className="empty">No trips to this site in the records.</p>;
  const x0 = day(rows[0].date.slice(0, 8) + "01"), x1 = Math.max(day(e.window.to), day(rows[rows.length - 1].date) + 86400000);
  const sx = (d: string) => L + ((day(d) - x0) / (x1 - x0)) * (W - L - R);
  const sy = (v: number) => T + (1 - (v - a.min) / (a.max - a.min)) * (H - T - B);
  const refused = rows.filter((r) => r.status === "returned");
  const months = Array.from(new Set(rows.map((r) => r.date.slice(0, 7)))).map((m) => m + "-01").filter((m) => day(m) >= x0);
  const counts = { delivered: rows.filter((r) => r.status === "delivered").length, partial: rows.filter((r) => r.status === "partial").length, returned: refused.length };
  return (
    <figure ref={ref} className="ev-chart" aria-label="Evidence: every trip to this site">
      <figcaption>
        <strong>Every trip to {e.site.name}, by {a.title}</strong>
        <span className="small muted"> · {rows.length} trips from the company's own records</span>
      </figcaption>
      <div className="ev-scroll"><svg viewBox={`0 0 ${W} ${H}`} className="ev-svg" role="img"
        aria-label={`${rows.length} trips: ${counts.returned} turned back, ${counts.delivered} delivered, ${counts.partial} part delivered.${a.guides[0] ? ` Limit learned: ${a.guides[0].t}.` : ""}`}>
        {(a.band ?? []).map(([lo, hi], i) => (
          <rect key={i} x={L} width={W - L - R} y={sy(hi)} height={Math.max(0, sy(lo) - sy(hi))} fill="var(--chart-band)" />
        ))}
        {a.band && a.bandLabel && <text x={W - R - 4} y={sy(a.band[0][1]) + 14} textAnchor="end" className="ev-note">{a.bandLabel}</text>}
        {a.ticks.map((t) => (
          <g key={t.t}><line x1={L} x2={W - R} y1={sy(t.v)} y2={sy(t.v)} className="ev-grid" /><text x={L - 8} y={sy(t.v) + 4} textAnchor="end" className="ev-tick">{t.t}</text></g>
        ))}
        {a.guides.map((g) => (
          <g key={g.t}><line x1={L} x2={W - R} y1={sy(g.v)} y2={sy(g.v)} className="ev-guide" />
            <text x={W - R - 4} y={sy(g.v) - 6} textAnchor="end" className="ev-guide-label">{g.t}</text></g>
        ))}
        <line x1={L} x2={W - R} y1={H - B} y2={H - B} className="ev-axis" />
        {months.map((m) => <text key={m} x={sx(m)} y={H - 8} className="ev-tick">{new Date(m + "T00:00").toLocaleDateString("en-IN", { month: "short" })}</text>)}
        {rows.map((r, i) => <Mark key={i} r={r} x={sx(r.date)} y={sy(a.value(r))} />)}
      </svg></div>
      <ul className="ev-legend small" aria-label="Legend">
        <li><svg width="14" height="14" aria-hidden><circle cx="7" cy="7" r="5" fill="var(--chart-ok)" /></svg> delivered ({counts.delivered})</li>
        {counts.partial > 0 && <li><svg width="14" height="14" aria-hidden><circle cx="7" cy="7" r="4.5" fill="var(--surface)" stroke="var(--chart-ok)" strokeWidth="2.5" /></svg> part delivered ({counts.partial})</li>}
        <li><svg width="14" height="14" aria-hidden><path d="M2 2L12 12M12 2L2 12" stroke="var(--chart-bad)" strokeWidth="2.5" strokeLinecap="round" /></svg> turned back ({counts.returned})</li>
      </ul>
      <details className="ev-table">
        <summary>See the {rows.length} trips as a table</summary>
        <div className="tablewrap"><table>
          <thead><tr><th>Date</th><th>Arrived</th><th>Vehicle</th><th>Length</th><th>Outcome</th></tr></thead>
          <tbody>{rows.map((r, i) => (
            <tr key={i}><td className="nowrap">{fmt(r.date)}</td><td>{String(r.hour).padStart(2, "0")}:00</td><td className="mono">{r.vehicle_id}</td>
              <td>{r.length_ft ? `${r.length_ft} ft` : "—"}</td><td>{STATUS[r.status] ?? r.status}{r.wait_min ? `, waited ${r.wait_min} min` : ""}</td></tr>
          ))}</tbody>
        </table></div>
      </details>
    </figure>
  );
}

/** A closure: delays by week, the closure window shaded, drivers' notes as pins; and those notes, as written. */
export function ClosureStory({ e, target }: { e: Extract<Evidence, { kind: "closure" }>; target: string | null }) {
  const chartRef = useFocusTarget<HTMLElement>(target && `${target}/chart`, true);
  const notesRef = useFocusTarget<HTMLElement>(target && `${target}/notes`, true);
  const weeks = e.weeks;
  if (weeks.length === 0) return <p className="empty">No closure delays in the records.</p>;
  const max = Math.max(1, ...weeks.map((w) => w.delays));
  const step = (W - L - R) / weeks.length;
  const PIN = 14; // a row for the drivers' notes, above the bars
  const sy = (v: number) => T + PIN + 18 + (1 - v / max) * (H - T - B - PIN - 18);
  const wx = (iso: string) => L + ((day(iso) - day(weeks[0].week)) / (7 * 86400000)) * step;
  const end = e.window.to;
  const after = weeks.filter((w) => end && w.week > end);
  const inside = e.window.from && end ? [wx(e.window.from), wx(end) + step / 7] : null;
  return (
    <>
      <figure ref={chartRef} className="ev-chart" aria-label="Closure delays by week">
        <figcaption>
          <strong>{e.delays} closure delays{end ? `, all inside the closure${after.length && after.every((w) => w.delays === 0) ? ", none after it" : ""}` : ""}</strong>
          <span className="small muted"> · delays recorded as a closure, per week, on trips through {e.place}</span>
        </figcaption>
        <div className="ev-scroll"><svg viewBox={`0 0 ${W} ${H}`} className="ev-svg" role="img"
          aria-label={`Closure delays per week near ${e.place}: ${weeks.map((w) => w.delays).join(", ")}. ${e.notes.length} drivers' notes on those trips.`}>
          {inside && <rect x={inside[0]} width={Math.max(0, inside[1] - inside[0])} y={T + PIN} height={H - T - B - PIN} fill="var(--chart-band)" />}
          <line x1={L} x2={W - R} y1={H - B} y2={H - B} className="ev-axis" />
          {weeks.map((w, i) => (
            <g key={w.week}>
              <title>{`Week of ${fmt(w.week)}: ${w.delays} closure delay${w.delays === 1 ? "" : "s"}`}</title>
              <rect x={L + i * step + 3} width={Math.max(2, step - 6)} y={sy(w.delays)} height={Math.max(0, H - B - sy(w.delays))} rx={3} fill="var(--chart-bar)" />
              {w.delays > 0 && <text x={L + i * step + step / 2} y={sy(w.delays) - 4} textAnchor="middle" className="ev-tick">{w.delays}</text>}
              {(i === 0 || w.week.slice(5, 7) !== weeks[i - 1].week.slice(5, 7)) && <text x={L + i * step + 3} y={H - 8} className="ev-tick">{new Date(w.week + "T00:00").toLocaleDateString("en-IN", { month: "short" })}</text>}
            </g>
          ))}
          {after.length > 0 && after.every((w) => w.delays === 0) && (
            <text x={wx(after[0].week) + 4} y={H - B - 8} className="ev-ok-label">0 after it ended</text>
          )}
          {e.notes.map((n, i) => (
            <g key={i}><title>{`${fmt(n.ts.slice(0, 10))} · ${n.text}`}</title>
              <path d={`M${wx(n.ts.slice(0, 10))} ${T + 8}l-4 -7h8z`} fill="var(--chart-bar)" opacity={0.85} /></g>
          ))}
        </svg></div>
        <ul className="ev-legend small" aria-label="Legend">
          <li><svg width="14" height="14" aria-hidden><rect x="2" y="2" width="10" height="10" rx="2" fill="var(--chart-bar)" /></svg> closure delays in the week</li>
          <li><svg width="14" height="14" aria-hidden><path d="M7 11l-4 -7h8z" fill="var(--chart-bar)" /></svg> a driver's note</li>
          <li><svg width="14" height="14" aria-hidden><rect x="1" y="1" width="12" height="12" fill="var(--chart-band)" /></svg> the closure{e.window.from && end ? `, ${fmt(e.window.from)} – ${fmt(end)}` : ""}</li>
        </ul>
        <details className="ev-table">
          <summary>See the weeks as a table</summary>
          <div className="tablewrap"><table><thead><tr><th>Week of</th><th>Closure delays</th></tr></thead>
            <tbody>{weeks.map((w) => <tr key={w.week}><td>{fmt(w.week)}</td><td>{w.delays}</td></tr>)}</tbody></table></div>
        </details>
      </figure>
      <section ref={notesRef} className="ev-notes" aria-label="What the drivers wrote">
        <h4>What drivers wrote on the delayed trips ({e.notes.length})</h4>
        <p className="small muted">As written, in their own languages. Linked to the delays by trip and stop in the records; not every note is about the road.</p>
        <ol className="plain notes-list" tabIndex={0} aria-label={`${e.notes.length} drivers' notes`}>
          {e.notes.map((n, i) => (
            <li key={i} lang={n.lang === "te" ? "te" : "en"}>
              <span className="note-text">{n.text}</span>
              <span className="small muted">{fmt(n.ts.slice(0, 10))} · {n.lang === "te" ? "Telugu" : n.lang === "rt" ? "Roman Telugu" : n.lang === "en" ? "English" : n.lang} · {n.source}</span>
            </li>
          ))}
        </ol>
      </section>
    </>
  );
}
