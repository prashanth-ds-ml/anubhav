import type { Draft } from "../types";
import { AgentTag } from "./Badges";

export function WhyCard({ why: raw }: { why: NonNullable<Draft["why"]> }) {
  const list = <T,>(x: T[] | undefined | null): T[] => (Array.isArray(x) ? x : []);
  const why = { ...raw, lessons: list(raw.lessons), agents: list(raw.agents), tools: list(raw.tools), checks: list(raw.checks).filter(Boolean) };
  return (
    <details className="why">
      <summary>Why this plan</summary>
      <dl>
        <dt>Lessons used</dt>
        <dd>{why.lessons.length ? <ul>{(why.lessons as unknown[]).map((l, i) => typeof l === "string" ? <li key={i}>{l}</li> : <li key={i}>{(l as { rule?: string } | null)?.rule ?? "—"}{(l as { evidence?: string } | null)?.evidence ? <span className="muted small"> ({(l as { evidence: string }).evidence})</span> : null}</li>)}</ul> : `None. It had ${why.lessons_in_prompt ?? 0} approved lessons in its instructions, and none applied to this plan.`}</dd>
        <dt>Agents</dt>
        <dd>{why.agents.length ? why.agents.map((a) => <AgentTag key={a} id={a} />) : "—"}</dd>
        <dt>Tools</dt>
        <dd className="mono">{why.tools.join(", ") || "—"}</dd>
        <dt>Checks by code</dt>
        <dd>{why.checks.length ? why.checks.map((c, i) => <span key={i} className={`pill ${c.pass ? "ok" : "err"}`}>{c.tool}: {c.pass ? "passed" : "failed"}</span>) : "None recorded"}</dd>
      </dl>
    </details>
  );
}
