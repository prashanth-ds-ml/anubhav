import { AGENTS, AGENT_STYLE } from "../agents";
import { AgentTag } from "./Badges";

export function Roster({ acting }: { acting: string | null }) {
  return (
    <ul className="roster" aria-label="Agent roster">
      {AGENTS.map((a) => (
        <li
          key={a.agent_id}
          className={`roster-item ${acting === a.agent_id ? "acting" : ""}`}
          style={{ borderColor: acting === a.agent_id ? AGENT_STYLE[a.agent_id].color : undefined }}
          title={a.purpose}
        >
          <AgentTag id={a.agent_id} />
          <span className="sr-only">{a.purpose}</span>
          {acting === a.agent_id && <span className="small"><b>Acting now</b></span>}
        </li>
      ))}
    </ul>
  );
}
