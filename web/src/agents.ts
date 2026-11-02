import { Compass, Search, Wrench, BookOpen, ShieldCheck } from "lucide-react";
import type { AgentInfo } from "./types";

export const AGENTS: AgentInfo[] = [
  { agent_id: "planner", label: "Planner", purpose: "Talks to you, delegates, drafts plans", kind: "agent" },
  { agent_id: "analyst", label: "Analyst", purpose: "Answers data questions with read-only SQL", kind: "agent" },
  { agent_id: "tool_forge", label: "Tool Forge", purpose: "Names reusable tools from repeated queries", kind: "agent" },
  { agent_id: "lesson_miner", label: "Lesson Miner", purpose: "Proposes lessons from history", kind: "agent" },
  { agent_id: "code", label: "Safety checks", purpose: "Plain code, not AI: validator, evidence gate, reply check", kind: "code" },
];

export const AGENT_STYLE: Record<string, { icon: typeof Compass; color: string }> = {
  planner: { icon: Compass, color: "var(--agent-planner)" },
  analyst: { icon: Search, color: "var(--agent-analyst)" },
  tool_forge: { icon: Wrench, color: "var(--agent-forge)" },
  lesson_miner: { icon: BookOpen, color: "var(--agent-miner)" },
  code: { icon: ShieldCheck, color: "var(--agent-code)" },
};

export const label = (id: string) => AGENTS.find((a) => a.agent_id === id)?.label ?? id;
