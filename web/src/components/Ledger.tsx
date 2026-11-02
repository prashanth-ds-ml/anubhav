import { useState } from "react";
import { api } from "../lib/api";
import { useApi } from "../lib/useApi";
import { useSettings } from "../lib/ctx";
import { AGENTS, label } from "../agents";
import { AgentTag } from "./Badges";
import { describe } from "./Timeline";
import { shortTime } from "../lib/text";

const brief = (s: string, n = 110) => (s.length > n ? `${s.slice(0, n).replace(/\s+\S*$/, "")}…` : s);

const NAMES: Record<string, string> = {
  handoff: "Handed off work", draft_created: "Created a draft", tool_missing: "Found no tool",
  validator_check: "Code check", lesson_used: "Used a lesson", learning_event: "Learning decision",
};
const TYPES = ["", ...Object.keys(NAMES)];

export function Ledger({ refreshKey }: { refreshKey: number }) {
  const { company } = useSettings();
  const [agent, setAgent] = useState("");
  const [type, setType] = useState("");
  const { data, loading } = useApi(() => api.ledger(company, agent, type), [company, agent, type, refreshKey]);
  return (
    <div>
      <p className="small muted">Every decision the agents and the people made, newest first. Each row links to a run you can replay.</p>
      <div className="filters">
        <label>Agent{" "}
          <select value={agent} onChange={(e) => setAgent(e.target.value)}>
            <option value="">All</option>
            {AGENTS.filter((a) => a.kind === "agent").map((a) => <option key={a.agent_id} value={a.agent_id}>{a.label}</option>)}
          </select>
        </label>
        <label>Decision{" "}
          <select value={type} onChange={(e) => setType(e.target.value)}>
            {TYPES.map((t) => <option key={t} value={t}>{NAMES[t] ?? "All"}</option>)}
          </select>
        </label>
      </div>
      {loading ? <div className="skeleton" aria-busy="true" /> : data!.length === 0 ? (
        <p className="empty">No decisions yet. Play a request in the chat and its decisions appear here.</p>
      ) : (
        <div className="tablewrap"><table>
          <thead><tr><th>Time</th><th>Agent</th><th>Decision</th><th>Detail</th></tr></thead>
          <tbody>{data!.slice(0, 80).map((e, i) => {
            const b = describe(e);
            return (
              <tr key={`${e.run_id}-${e.seq}-${i}`}>
                <td className="nowrap small">{shortTime(e.ts)}</td>
                <td><AgentTag id={e.agent_id} /></td>
                <td>{NAMES[e.type] ?? e.type}</td>
                {(() => {
                  const full = e.type === "handoff" ? `To ${label(e.payload.to)}: ${e.payload.brief}` : e.type === "learning_event" ? `${String(e.payload.decision).replace("_", " ")}: ${e.payload.what ?? e.payload.ref}` : `${b.title}${b.text ? `. ${b.text}` : ""}`;
                  return <td className="wrap" title={full}>{brief(full)}</td>;
                })()}
              </tr>
            );
          })}</tbody>
        </table></div>
      )}
    </div>
  );
}
