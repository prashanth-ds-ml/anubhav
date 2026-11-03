// Shapes follow contracts/events.schema.json and what the API really sends (checked against the running server).

export type EventType =
  | "agent_start" | "tool_call" | "tool_result" | "retry" | "tool_missing" | "handoff"
  | "lesson_used" | "validator_check" | "draft_created" | "agent_done" | "learning_event" | "needs_person";

export const EVENT_TYPES: EventType[] = [
  "agent_start", "tool_call", "tool_result", "retry", "tool_missing", "handoff",
  "lesson_used", "validator_check", "draft_created", "agent_done", "learning_event", "needs_person",
];

export interface RunEvent {
  run_id: string; seq: number; agent_id: string; agent_run_id: string; caller: string; depth: number;
  ts: string | null; type: EventType; payload: Record<string, any>;
}

export interface AgentInfo { agent_id: string; label: string; purpose: string; kind: "agent" | "code"; }

export interface Order {
  order_id: string; site_id: string; site: string; town: string; window: string; priority: string;
  kg: number; m3: number; value_rs: number; cases: number; handling_classes: string[]; in_draft: boolean;
}
export interface Vehicle {
  vehicle_id: string; class: string; length_ft: number; payload_kg: number; volume_m3: number; body: string;
  owner: string; vendor: string; reg_no: string; status: string; free: boolean; reason: string | null; held_today: boolean;
}
export interface Draft {
  draft_id: string; status: string; vehicle_id: string; delivery_date: string; orders: string[];
  /** The run that made it, and the model that run used. */
  run_id?: string | null; model?: string | null;
  load: { kg: number; m3: number; value_rs: number; stops: number; sites: string[]; handling_classes: string[] };
  warnings: { code: string; message: string }[];
  /** "live": a draft in this visitor's workspace, which a person can approve or reject; "run": rebuilt from a recording. */
  source?: "live" | "run";
  decisions?: unknown[];
  stops?: { from: string; total_km: number; method: string; stops: { stop: number; site_id: string; name: string; town: string; leg_km: number; total_km: number; est_minutes_total: number }[] };
  why?: {
    request: string; lessons: { id: string; rule: string; evidence: string }[]; lessons_in_prompt: number;
    agents: string[]; tools: string[]; checks: { tool: string; pass: boolean; draft_id?: string }[];
  };
}
export interface Company {
  company: string;
  facts: Record<string, any>;
  written_rules: { id: string; text: string }[];
  owner: Record<string, string>;
  owner_fields: Record<string, string>;
}
export interface Suggestion { label: string; request: string; has_replay: boolean; }
export interface CompanyRow { company: string; name: string; sites: number; vehicles: number; towns: number; plan_date: string; }
export interface Session {
  public: boolean; default_mode: string; default_team: boolean; default_model?: string;
  models: Record<string, { available: boolean; reason: string | null; key?: string }>;
  voice: { available: boolean; reason: string | null };
  /** The smaller of this visit's and today's runs left. */
  live_runs_left: number;
  live_runs_used?: number; live_runs_left_today?: number;
  caps: { per_session: number; per_day: number };
}
