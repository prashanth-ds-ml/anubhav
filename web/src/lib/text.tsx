import type { ReactNode } from "react";

/** A short readable line from a tool result. The server sends trimmed JSON text, so fall back to its first fields. */
export function resultText(raw: unknown, max = 180): string {
  if (typeof raw !== "string") return "";
  try {
    const v = JSON.parse(raw);
    const hint = describeResult(v);
    if (hint) return hint;
    return fieldsOf(raw) || clip(raw, max);
  } catch { /* trimmed JSON does not parse: read its first fields */ }
  return fieldsOf(raw) || clip(raw, max);
}

const clip = (s: string, n: number) => (s.length > n ? `${s.slice(0, n)}…` : s);

/** The first few simple "key": value pairs of a JSON text, as words: never a raw brace on screen. */
function fieldsOf(raw: string): string {
  if (!/^\s*[[{]/.test(raw)) return "";
  const out: string[] = [];
  for (const m of raw.matchAll(/"([a-z_]+)":\s*(?:"([^"]{1,80})|(-?\d+(?:\.\d+)?)|(true|false))/gi)) {
    out.push(`${m[1].replace(/_/g, " ")}: ${m[2] ?? m[3] ?? m[4]}`);
    if (out.length === 3) break;
  }
  return out.length ? out.join(" · ") + (raw.length > 200 ? " …" : "") : "";
}

function describeResult(v: any): string {
  if (!v || typeof v !== "object") return "";
  if (Array.isArray(v.matches)) return `${v.matches.length} match${v.matches.length === 1 ? "" : "es"}${v.matches[0]?.name ? `: ${v.matches[0].name}${v.matches[0].town ? `, ${v.matches[0].town}` : ""}` : ""}`;
  if (Array.isArray(v.orders) && !v.draft_id) return `${v.orders.length} open orders`;
  if (Array.isArray(v.vehicles)) return `${v.vehicles.length} vehicles`;
  if (v.draft_id) return `Draft ${v.draft_id} on ${v.vehicle_id}${v.created === false ? " (not created)" : ""}`;
  if (v.agent && v.reply) return `${v.agent} replied: ${String(v.reply).slice(0, 140)}`;
  if (Array.isArray(v.rows)) return `${v.rows.length} rows`;
  if (typeof v.available === "boolean") return `${v.vehicle_id ?? "vehicle"}: ${v.available ? "available" : "not available"}`;
  if (v.tool_missing) return "No tool or teammate fits";
  if (v.question) return String(v.question);
  return "";
}

export const errorText = (e: any): string => (e && typeof e === "object" ? `${e.code ?? "Error"}: ${e.message ?? ""}` : String(e ?? ""));

/** "busiest_weekday_in_town" → "Busiest weekday in town". */
export const humanName = (s: string) => {
  const t = s.replace(/[_-]+/g, " ").trim();
  return t ? t[0].toUpperCase() + t.slice(1) : s;
};

/** "2026-10-29T19:44:05" → "29 Oct, 19:44". */
export function shortTime(ts: string | null | undefined): string {
  if (!ts) return "";
  const d = new Date(ts.length <= 19 ? ts : ts.slice(0, 19));
  if (Number.isNaN(d.getTime())) return ts.replace("T", " ").slice(0, 16);
  return `${d.getDate()} ${d.toLocaleString("en-IN", { month: "short" })}, ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

/** The server explains why live mode or voice is off in an operator's terms (an env var name). Say it for a visitor. */
export function plainReason(reason: string | null | undefined, what: "Live mode" | "Voice" = "Live mode"): string {
  if (!reason) return "";
  if (/no `[^`]+` set/.test(reason)) return what === "Voice" ? "Voice works in live mode, which is off on this demo." : "Live mode is off on this demo.";
  return reason.replace(/ Use Replay\.?$/, "").replace(/ Use Replay, or run it locally\.?$/, "");
}

function inline(line: string): ReactNode[] {
  return line.split(/\*\*(.+?)\*\*/g).map((part, j) => (j % 2 ? <strong key={j}>{part}</strong> : part));
}

/** Chat replies use a little markdown (bold, "* " or "- " bullets, "#" headings, blank lines). Show it without a library. */
export function Reply({ text }: { text: string }): ReactNode {
  const blocks: ReactNode[] = [];
  let items: string[] = [];
  const flush = () => {
    if (items.length) blocks.push(<ul key={`u${blocks.length}`}>{items.map((x, i) => <li key={i}>{inline(x)}</li>)}</ul>);
    items = [];
  };
  for (const raw of text.split("\n")) {
    const line = raw.trimEnd();
    const bullet = line.match(/^\s*[*-]\s+(.*)$/);
    if (bullet) { items.push(bullet[1]); continue; }
    flush();
    if (!line.trim()) continue;
    const head = line.match(/^#{1,4}\s+(.*)$/);
    if (head) blocks.push(<p key={`h${blocks.length}`} className="reply-head">{inline(head[1])}</p>);
    else blocks.push(<p key={`p${blocks.length}`}>{inline(line)}</p>);
  }
  flush();
  return <div className="reply">{blocks}</div>;
}
