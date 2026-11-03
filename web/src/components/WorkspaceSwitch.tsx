import { useState } from "react";
import { api } from "../lib/api";
import { useApi } from "../lib/useApi";
import { useSettings } from "../lib/ctx";

// Two workspaces, one switch (owner, Nov 3): start from zero to watch the agents learn, or load the lessons the recorded
// runs and the measured results used. Only this visitor's workspace changes; the records and the experiments don't.
export function WorkspaceSwitch() {
  const { company, dataVersion, bumpData, refreshSession } = useSettings();
  const s = useApi(() => api.freshStatus(company), [company, dataVersion], { keep: true });
  const [busy, setBusy] = useState(false);
  if (!s.data) return null;
  const fresh = s.data.fresh;
  async function pick(toFresh: boolean) {
    if (busy || toFresh === fresh) return;
    setBusy(true);
    try {
      await (toFresh ? api.freshStart(company) : api.freshRestore(company));
      bumpData();
      refreshSession();
    } finally { setBusy(false); }
  }
  return (
    <div className="ws-switch" role="group" aria-label="Workspace">
      <span className="small muted">Workspace:</span>
      <button type="button" aria-pressed={fresh} disabled={busy} onClick={() => pick(true)}
        title="No lessons and no tools: watch the agents learn from the records">Start from zero</button>
      <button type="button" aria-pressed={!fresh} disabled={busy} onClick={() => pick(false)}
        title="The lessons the recorded runs and the measured results used (EXP-008)">With recorded lessons</button>
      <span className="small muted" aria-live="polite">{s.data.lessons} lesson{s.data.lessons === 1 ? "" : "s"} · {s.data.tools} tool{s.data.tools === 1 ? "" : "s"}</span>
    </div>
  );
}
