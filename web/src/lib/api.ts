import { EVENT_TYPES, type RunEvent, type Order, type Vehicle, type Draft, type Company, type Suggestion, type CompanyRow, type Session } from "../types";
import { BUNDLED } from "./fixtures";

export class ApiError extends Error {
  constructor(public code: string, message: string, public body: any = {}) { super(message); }
}

/**
 * The server gives each visitor a workspace through a cookie, and it makes a new workspace for every request that arrives without one.
 * A page that fires several requests at once on the first visit would get several workspaces, and the cookie would end up pointing at
 * whichever answer came last: an approval made early could then seem to vanish. So the first request is /api/session alone, and
 * every other request waits for it. If the server cannot be reached, the wait ends and the request fails in the usual way.
 *
 * A new workspace also gets its lessons copied in on the first request that needs them, and the server does that without a lock:
 * two requests at once can fail with a 500, or one can read the lessons while they are half copied and see none. So the
 * gate also makes that first read alone. This is a workaround; once the server seeds under a lock it is harmless and can go.
 */
let sessionStarted: Promise<unknown> | null = null;
const started = () => (sessionStarted ??= fetch("/api/session").then(() => fetch("/api/tools?company=T01")).catch(() => null));

/** One place for every request: JSON in, JSON out, the server's one error shape turned into an ApiError. */
async function call<T>(path: string, init?: RequestInit): Promise<T> {
  await started();
  let r: Response;
  try { r = await fetch(path, init); } catch { throw new ApiError("NETWORK", "The server could not be reached."); }
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw new ApiError(body?.error?.code ?? "ERROR", body?.error?.message ?? `Request failed (${r.status}).`, body?.error ?? {});
  return body as T;
}

/** An action. Unlike a read it throws an ApiError, so the page can say why it did not happen. */
const post = <T>(path: string, body: unknown) =>
  call<T>(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

/** A read that never throws: if the server is down the page shows its empty state instead of breaking. */
async function read<T>(path: string, fallback: T): Promise<T> {
  try { return await call<T>(path); } catch { return fallback; }
}

const q = (company: string, extra: Record<string, string | boolean | undefined> = {}) => {
  const p = new URLSearchParams({ company });
  for (const [k, v] of Object.entries(extra)) if (v !== undefined && v !== "") p.set(k, String(v));
  return p.toString();
};

export interface RunRow { run_id: string; saved_at: string; label: string; company: string; model: string; request: string; mode: string; agents: string[]; tool_calls: number; drafts: string[]; stop: string; cost_usd: number; issues: string }

export interface TripRow { date: string; hour: number; weekday: number; vehicle_id: string; vehicle_class: string; length_ft: number | null; status: string; status_seen: string | null; wait_min: number }
export type Evidence =
  | { kind: "trips"; lesson_kind: string; site: { site_id: string; name: string; town: string }; limit: Record<string, number>; window: { from: string | null; to: string }; rows: TripRow[] }
  | { kind: "closure"; lesson_kind: string; place: string; what?: string; window: { from: string | null; to: string | null }; today: string; delays: number; weeks: { week: string; delays: number }[]; notes: { ts: string; lang: string; source: string; text: string }[] }
  | { kind: "imported"; lesson_kind: string; source: string; note: string }
  | { kind: "none"; lesson_kind: string };

export const api = {
  evidence: (c: string, id: string) => read<Evidence | null>(`/api/learning/lessons/${encodeURIComponent(id)}/evidence?${q(c)}`, null),
  runs: (c: string) => read<RunRow[]>(`/api/logs/runs?${q(c)}`, []),
  session: () => read<Session | null>("/api/session", null),
  companies: () => read<CompanyRow[]>("/api/companies", []),
  suggestions: (company: string, useLessons: boolean) => read<Suggestion[]>(`/api/suggestions?${q(company, { use_lessons: useLessons })}`, []),
  orders: (c: string) => read<{ delivery_date: string; orders: Order[] }>(`/api/dashboard/orders?${q(c)}`, { delivery_date: "", orders: [] }),
  fleet: (c: string) => read<{ delivery_date: string; vehicles: Vehicle[] }>(`/api/dashboard/fleet?${q(c)}`, { delivery_date: "", vehicles: [] }),
  drafts: (c: string, runId?: string) => read<{ drafts: Draft[]; source: string }>(`/api/dashboard/drafts?${q(c, { run_id: runId })}`, { drafts: [], source: "live" }),
  company: (c: string) => read<Company | null>(`/api/dashboard/company?${q(c)}`, null),
  ledger: (c: string, agent = "", type = "") => read<RunEvent[]>(`/api/ledger?${q(c, { agent, type })}`, []),
  agents: (c: string) => read<AgentRow[]>(`/api/agents?${q(c)}`, []),
  lessons: (c: string) => read<Lesson[]>(`/api/learning/lessons?${q(c)}`, []),
  timeline: (c: string) => read<TimelineRow[]>(`/api/learning/timeline?${q(c)}`, []),
  toolCandidates: (c: string) => read<ToolCandidate[]>(`/api/tools/candidates?${q(c)}`, []),
  decideLesson: (c: string, id: string, body: LessonDecision) => post<Lesson>(`/api/learning/lessons/${encodeURIComponent(id)}/decide?${q(c)}`, body),
  tools: (c: string) => read<NewTool[]>(`/api/tools?${q(c)}`, []),
  // The three actions on a repeated question. They change this visitor's own workspace only; a person is always the one who approves.
  checkTool: (c: string, key: string) => post<NewTool>(`/api/tools/candidates/${encodeURIComponent(key)}/check?${q(c)}`, {}),
  decideTool: (c: string, id: string, approve: boolean, note: string) => post<NewTool>(`/api/tools/${encodeURIComponent(id)}/decide?${q(c)}`, { approve, note }),
  retireTool: (c: string, id: string, note: string) => post<NewTool>(`/api/tools/${encodeURIComponent(id)}/retire?${q(c)}`, { note }),
  proof: () => read<ProofEntry[]>("/api/proof", []),
  compare: (c: string, request: string) => read<Compare | null>(`/api/compare?${q(c, { request })}`, null),
};

export interface AgentRow { agent: string; name: string; purpose: string; status: string; model: string; version: string; versions_tried: number; knowledge_items: number; }
export interface Lesson {
  lesson_id: string; claim: string; what: string; state: string; effect: string; source: string; created: string; reviewer: string;
  kind?: string; params?: Record<string, any>; valid_from?: string | null; valid_to?: string | null;
  gate: { verdict: string; reason: string; support: number; counter: number; strength: string; enforceable?: boolean };
  miner: { evidence?: string[]; counter_evidence?: string[]; confidence?: string; model?: string } | null;
  events: { ts: string; actor: string; action: string; from_state: string | null; to_state: string; note: string }[];
}
export type LessonDecision =
  | { decision: "approve"; effect: "advisory" | "policy"; verified?: string }
  | { decision: "reject" | "retire"; why: string }
  | { decision: "rollback" };
export interface TimelineRow { ts: string; kind: string; agent: string; decision: string; ref: string; by: string; what: string; state?: string; note?: string; }
export interface ToolCandidate { key: string; requests: string[]; uses: number; reached_threshold: boolean; threshold: number; suggested_name: string; suggested_description: string; }
export interface NewTool {
  tool_id: string; name: string; description: string; status: "candidate" | "active" | "rejected" | "retired" | string;
  params: { name: string; kind: string; column?: string; example?: string }[];
  checks: {
    pass: boolean;
    same_rows: { request: string; rows: number; same: boolean }[];
    held_out: { values: Record<string, string>; ok: boolean; rows: number }[];
    reasons: string[];
  };
}
export interface ProofEntry { id: string; measured_on: string; pooled?: Record<string, any>; arms?: Record<string, any>; decision?: Record<string, any>; replicated?: Record<string, boolean>; repeats?: any[]; learning_round?: any; cost_usd?: number; }
export interface CompareSide { run_id: string; reply: string; drafts: { vehicle_id: string; orders: string[] }[]; tool_calls: number; cost_usd: number; lessons_in_prompt: number; }
export interface Compare { request: string; cold: CompareSide | null; with_lessons: CompareSide | null; with_learned_tools: CompareSide | null; }

/** "meta-models/muse-spark-open-1026" -> "Muse Spark Open". Scripted test runs say so. */
export function modelName(id?: string): string {
  if (!id) return "unknown model";
  if (/mock|scripted/i.test(id)) return "scripted test model";
  if (/spark-open/i.test(id)) return "Muse Spark Open";
  if (/spark-1\.3|spark_1_3|spark1\.3/i.test(id)) return "Muse Spark 1.3";
  return id;
}

export interface RunOptions { company: string; useLessons: boolean; team: boolean; live?: boolean }
export interface RunHandlers {
  onEvent: (e: RunEvent) => void;
  onRun: (info: { run_id: string; mode: string; replay_of?: string; bundled?: boolean }) => void;
  onNote: (text: string | null) => void;
  onEnd: (stop?: string) => void;
  onNoReplay: (message: string) => void;
}

/** Start a run and stream its events. Returns a stop function. Plays a bundled example only if the server is unreachable. */
export function startRun(message: string, opt: RunOptions, h: RunHandlers): () => void {
  let es: EventSource | null = null;
  let timer: number | undefined;
  let stopped = false;
  let last = -1;

  const bundled = () => {
    const run = BUNDLED.find((r) => r.request === message);
    if (!run) { h.onNoReplay("The server cannot be reached, and no bundled example matches this request."); return; }
    h.onNote("The server cannot be reached, so this plays a bundled example.");
    h.onRun({ run_id: run.events[0].run_id, mode: "replay", bundled: true });
    let i = 0;
    timer = window.setInterval(() => {
      if (i >= run.events.length) { clearInterval(timer); h.onEnd(); return; }
      h.onEvent(run.events[i++]);
    }, 450);
  };

  call<{ run_id: string; mode: string; replay_of?: string; reason?: string }>("/api/chat", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ company: opt.company, message, mode: opt.live ? "live" : "replay", ...(opt.live ? { model: "spark" } : {}), use_lessons: opt.useLessons, team: opt.team }),
  })
    .then((r) => {
      if (stopped) return;
      h.onNote(r.reason ?? null);
      h.onRun(r);
      const open = () => {
        es = new EventSource(`/api/chat/stream?run_id=${encodeURIComponent(r.run_id)}&after=${last}`);
        const take = (m: MessageEvent) => {
          const e: RunEvent = JSON.parse(m.data);
          last = e.seq;
          h.onEvent(e);
        };
        for (const t of EVENT_TYPES) es.addEventListener(t, take as EventListener);
        es.addEventListener("end", (m) => {
          es?.close();
          h.onEnd(JSON.parse((m as MessageEvent).data).stop);
        });
        es.onerror = () => { // dropped: reconnect once, asking only for what we missed
          es?.close();
          if (!stopped) window.setTimeout(open, 800);
        };
      };
      open();
    })
    .catch((e: ApiError) => {
      if (stopped) return;
      if (e.code === "NO_REPLAY") h.onNoReplay(e.message);
      else if (e.code === "NETWORK") bundled();
      else h.onNoReplay(e.message);
    });

  return () => { stopped = true; es?.close(); clearInterval(timer); };
}

export type VoiceResult =
  | { ok: true; transcript: string; audio_ms: number; cost_usd: number }
  | { ok: false; code: string; message: string };

/** Whether voice can be used, from /api/session (voice needs the Meta key, like live mode). */
export async function voiceStatus(): Promise<{ available: boolean; reason: string | null }> {
  const s = await api.session();
  if (!s) return { available: false, reason: "The backend is not reachable, so voice is off." };
  return s.voice ?? { available: false, reason: "Voice is not configured here." };
}

/** Send a 16 kHz mono WAV for transcription. Never throws: failures come back as { ok: false }. */
export async function sendVoice(wav: ArrayBuffer): Promise<VoiceResult> {
  try {
    const r = await fetch("/api/voice", { method: "POST", headers: { "Content-Type": "audio/wav" }, body: wav });
    const body = await r.json();
    if (!r.ok) return { ok: false, code: body?.error?.code ?? "ERROR", message: body?.error?.message ?? "Something went wrong." };
    return { ok: true, ...body };
  } catch {
    return { ok: false, code: "NETWORK", message: "Could not reach the server. Try again." };
  }
}
