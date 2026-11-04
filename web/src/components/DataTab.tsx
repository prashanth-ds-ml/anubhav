import { useEffect, useRef, useState } from "react";
import { dataApi, type Cell, type DataColumn, type DataPage, type DataTable } from "../lib/api";
import { useSettings } from "../lib/ctx";

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const QUICK = 6; // the first tables (the ones the server lists first) also get a button

/** "2026-08-01" → "1 Aug 2026"; "2026-08-01T05:24" → "1 Aug 2026, 05:24". Read as written: no time zone shift. */
function readable(v: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}:\d{2}))?/.exec(v);
  if (!m || Number(m[2]) < 1 || Number(m[2]) > 12) return v;
  return `${Number(m[3])} ${MONTHS[Number(m[2]) - 1]} ${m[1]}${m[4] ? `, ${m[4]}` : ""}`;
}

/** The day `n` days before an ISO date, as an ISO date. */
function daysBefore(iso: string, n: number): string {
  const d = new Date(`${iso}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() - n);
  return d.toISOString().slice(0, 10);
}

function CellView({ v, col }: { v: Cell; col: DataColumn }) {
  if (v === null || v === undefined || v === "") return <span className="muted" aria-label="empty">—</span>;
  if (typeof v === "number") return <>{v.toLocaleString("en-IN")}</>;
  return <>{readable(String(v))}</>; // plain text only: free text written by people is never rendered as markup
}

const numeric = (c: DataColumn) => c.type === "INTEGER" || c.type === "REAL";

export function DataTab() {
  const { company } = useSettings();
  const [tables, setTables] = useState<DataTable[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [table, setTable] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [all, setAll] = useState(false);
  const [page, setPage] = useState<DataPage | null>(null);
  const [rows, setRows] = useState<Cell[][]>([]);
  const [busy, setBusy] = useState(false);
  const ask = useRef(0); // only the latest request may fill the table

  const meta = tables?.find((t) => t.table === table) ?? null;
  const dated = !!meta?.date_column;

  function pick(t: DataTable | undefined) {
    if (!t) return;
    setTable(t.table);
    setAll(false);
    setFrom(t.date_max ? daysBefore(t.date_max, 6) : "");
    setTo(t.date_max ?? "");
  }

  useEffect(() => {
    let live = true;
    setTables(null); setError(null); setPage(null); setRows([]);
    dataApi.tables(company)
      .then((ts) => { if (!live) return; setTables(ts); pick(ts[0]); })
      .catch((e) => live && setError(e?.message ?? "The tables could not be loaded."));
    return () => { live = false; };
  }, [company]); // eslint-disable-line react-hooks/exhaustive-deps

  function load(offset: number) {
    if (!table) return;
    const n = ++ask.current;
    const useDates = dated && !all;
    setBusy(true); setError(null);
    dataApi.rows(company, table, useDates ? from : "", useDates ? to : "", offset)
      .then((p) => {
        if (n !== ask.current) return;
        setPage(p);
        setRows((r) => (offset === 0 ? p.rows : [...r, ...p.rows]));
      })
      .catch((e) => n === ask.current && setError(e?.message ?? "The rows could not be loaded."))
      .finally(() => n === ask.current && setBusy(false));
  }

  useEffect(() => { setRows([]); setPage(null); load(0); }, [company, table, from, to, all]); // eslint-disable-line react-hooks/exhaustive-deps

  const quick = (tables ?? []).slice(0, QUICK);
  const shown = page && page.table === table ? rows : [];
  const total = page && page.table === table ? page.total : 0;

  return (
    <div className="data-tab">
      <h3>The records the agents work on</h3>
      <p className="small muted">All companies and records are synthetic, generated for this project. These are the same tables the agents query.</p>

      {tables === null && !error && <div className="skeleton" aria-label="Loading the tables" />}
      {tables && tables.length === 0 && <p className="empty">This company has no records yet.</p>}

      {tables && tables.length > 0 && (
        <>
          <div className="data-controls">
            <div className="data-quick" role="group" aria-label="Main tables">
              {quick.map((t) => (
                <button key={t.table} type="button" className="chip" aria-pressed={t.table === table} onClick={() => t.table !== table && pick(t)}>
                  {t.title} <span className="muted">({t.rows.toLocaleString("en-IN")})</span>
                </button>
              ))}
            </div>
            <label className="data-field">
              <span>Table</span>
              <select aria-label="Table" value={table} onChange={(e) => pick(tables.find((t) => t.table === e.target.value))}>
                {tables.map((t) => <option key={t.table} value={t.table}>{t.title} · {t.table} ({t.rows.toLocaleString("en-IN")} rows)</option>)}
              </select>
            </label>
            {dated && meta ? (
              <fieldset className="data-dates">
                <legend>Dates <span className="small muted">(by <span className="mono">{meta.date_column}</span>)</span></legend>
                <label className="data-field">
                  <span>From</span>
                  <input type="date" aria-label="From" value={from} min={meta.date_min ?? undefined} max={to || meta.date_max || undefined} disabled={all}
                    onChange={(e) => setFrom(e.target.value)} />
                </label>
                <label className="data-field">
                  <span>To</span>
                  <input type="date" aria-label="To" value={to} min={from || meta.date_min || undefined} max={meta.date_max ?? undefined} disabled={all}
                    onChange={(e) => setTo(e.target.value)} />
                </label>
                <label className="data-check">
                  <input type="checkbox" checked={all} onChange={(e) => setAll(e.target.checked)} /> All dates
                </label>
              </fieldset>
            ) : meta ? (
              <p className="small muted data-nodate">This table has no date, so every row is shown.</p>
            ) : null}
          </div>

          {error && <p className="err-text" role="alert">{error}</p>}

          {meta && page && page.table === table && shown.length === 0 && !busy ? (
            <div className="empty">
              <p>No rows {dated && !all ? "for these dates" : "in this table"}.</p>
              {dated && !all && <button type="button" className="chip" onClick={() => setAll(true)}>Show all dates</button>}
            </div>
          ) : (
            meta && (
              <div className="data-scroll" tabIndex={0} role="region" aria-label={`${meta.title} table`}>
                <table className="data-table">
                  <caption className="sr-only">{meta.title}: showing {shown.length} of {total} rows</caption>
                  <thead>
                    <tr>{(page?.columns ?? []).map((c) => <th key={c.name} scope="col" className={numeric(c) ? "num" : undefined}>{c.name}</th>)}</tr>
                  </thead>
                  <tbody>
                    {shown.map((r, i) => (
                      <tr key={i}>
                        {(page?.columns ?? []).map((c, j) => (
                          <td key={c.name} className={numeric(c) ? "num" : c.free_text ? "free" : undefined}><CellView v={r[j]} col={c} /></td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
                {busy && shown.length === 0 && <div className="skeleton" aria-label="Loading rows" />}
              </div>
            )
          )}

          {meta && (
            <div className="data-more">
              <p className="small" aria-live="polite">
                {page && page.table === table ? <>Showing {shown.length.toLocaleString("en-IN")} of {total.toLocaleString("en-IN")} rows</> : "Loading…"}
              </p>
              {page && page.table === table && page.next_offset !== null && (
                <button type="button" className="send" disabled={busy} onClick={() => load(page.next_offset!)}>
                  {busy ? "Loading…" : "Load more"}
                </button>
              )}
            </div>
          )}
        </>
      )}
      {error && !tables && <p className="err-text" role="alert">{error}</p>}
    </div>
  );
}
