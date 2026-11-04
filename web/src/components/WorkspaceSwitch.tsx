import { useState } from "react";
import { RotateCcw } from "lucide-react";
import { api } from "../lib/api";
import { useApi } from "../lib/useApi";
import { useSettings } from "../lib/ctx";

// Two workspaces, one switch (owner, Nov 3). "Fresh start" is the business on day one: no lessons, no tools, agents at
// version 1, and only the runs made here. "After learning" has the lessons the recorded runs and the measured results
// used. Only this visitor's workspace changes; the company's records and the experiments don't.
export function WorkspaceSwitch({ onFresh }: { onFresh?: () => Promise<unknown> }) {
  const { company, dataVersion, bumpData, refreshSession } = useSettings();
  const s = useApi(() => api.freshStatus(company), [company, dataVersion], { keep: true });
  const [busy, setBusy] = useState(false);
  if (!s.data) return null;
  const fresh = s.data.fresh;
  async function act(toFresh: boolean) {
    if (busy) return;
    setBusy(true);
    try {
      if (toFresh) await (onFresh ? onFresh() : api.freshStart(company));
      else await api.freshRestore(company);
      bumpData();
      refreshSession();
    } finally { setBusy(false); }
  }
  return (
    <div className="ws-switch" role="group" aria-label="Workspace">
      <span className="small muted ws-label">Workspace:</span>
      <button type="button" aria-pressed={fresh} disabled={busy} onClick={() => !fresh && act(true)}
        title="The business on day one: no lessons, no tools, agents at version 1, only the runs you make here">Fresh start</button>
      <button type="button" aria-pressed={!fresh} disabled={busy} onClick={() => fresh && act(false)}
        title="The lessons the recorded runs and the measured results used (mined in EXP-008), and the recorded runs">After learning</button>
      {fresh && (
        <button type="button" className="ws-reset" aria-label="Reset" disabled={busy} onClick={() => act(true)}
          title="Empty this workspace again: lessons, tools, drafts, the conversation and its runs list">
          <RotateCcw size={14} aria-hidden /> <span className="ws-reset-label">Reset</span>
        </button>
      )}
      <span className="small muted ws-count" aria-live="polite">{s.data.lessons} lesson{s.data.lessons === 1 ? "" : "s"} · {s.data.tools} tool{s.data.tools === 1 ? "" : "s"}</span>
    </div>
  );
}
