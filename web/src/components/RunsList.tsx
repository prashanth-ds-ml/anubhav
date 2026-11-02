import { api, modelName } from "../lib/api";
import { useApi } from "../lib/useApi";
import { useSettings } from "../lib/ctx";
import { shortTime } from "../lib/text";
import { label } from "../agents";

/** Every run this visitor can open: the recorded demo runs and their own live runs, each with its full record. */
export function RunsList() {
  const { company } = useSettings();
  const { data, loading } = useApi(() => api.runs(company), [company]);
  if (loading) return <div className="skeleton" aria-busy="true" />;
  const rows = data ?? [];
  return (
    <section aria-labelledby="runs-title">
      <h2 id="runs-title">Runs you can inspect</h2>
      <p className="small muted">Every recorded run, and your own live runs. Each opens as its full record: every tool call, its answer, and the final reply.</p>
      {rows.length === 0 ? <p className="empty">No runs for this company yet.</p> : (
        <div className="tablewrap"><table>
          <thead><tr><th>When</th><th>Request</th><th>Agents</th><th>Tool calls</th><th>Cost</th><th><span className="sr-only">Record</span></th></tr></thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.run_id}>
                <td className="nowrap small">{shortTime(r.saved_at)}<br /><span className="muted">{modelName(r.model)}</span></td>
                <td className="wrap">{r.request}</td>
                <td className="small">{r.agents.map(label).join(", ")}</td>
                <td>{r.tool_calls}</td>
                <td className="nowrap">${r.cost_usd.toFixed(3)}</td>
                <td><a href={`/api/runs/${encodeURIComponent(r.run_id)}`} target="_blank" rel="noreferrer">Record (JSON)</a></td>
              </tr>
            ))}
          </tbody>
        </table></div>
      )}
      <p className="small muted">A step-by-step view of each run, by agent, comes next.</p>
    </section>
  );
}
