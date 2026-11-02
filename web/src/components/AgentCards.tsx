import { api } from "../lib/api";
import { useApi } from "../lib/useApi";
import { useSettings } from "../lib/ctx";
import { modelName } from "../lib/api";
import { AgentTag } from "./Badges";

export function AgentCards() {
  const { company } = useSettings();
  const { data, loading } = useApi(() => api.agents(company), [company]);
  if (loading) return <div className="skeleton" aria-busy="true" />;
  if (data!.length === 0) return <p className="empty">No agent data. The server may be unreachable.</p>;
  return (
    <>
      <p className="small muted">
        Four agents share one set of tools. Each has its own instructions and its own saved versions. The Planner is the only one that talks to the person.
      </p>
      <div className="agent-grid">
        {data!.map((a) => (
          <article key={a.agent} className="panel">
            <header className="card-head"><AgentTag id={a.agent} /><span className="pill ok" title={`Saved as ${a.version}`}>Version {Number(a.version.match(/(\d+)$/)?.[1] ?? 0) + 1}</span></header>
            <p className="small muted">{a.purpose}</p>
            <dl className="facts-list">
              <div><dt>Things it knows about this company</dt><dd>{a.knowledge_items}</dd></div>
              <div><dt>Instruction versions tried</dt><dd>{a.versions_tried === 0 ? "None yet; running the first version" : a.versions_tried}</dd></div>
              <div><dt>Default model for live runs</dt><dd>{a.model === "spark" ? modelName("muse-spark-1.3") : a.model}</dd></div>
            </dl>
            <p className="small muted">Improvement over versions: not measured yet.</p>
          </article>
        ))}
      </div>
    </>
  );
}
