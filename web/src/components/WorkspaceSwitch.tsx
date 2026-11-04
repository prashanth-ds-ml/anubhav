import { useState } from "react";
import { RotateCcw } from "lucide-react";
import { api } from "../lib/api";
import { useApi } from "../lib/useApi";
import { useSettings } from "../lib/ctx";

// Two workspaces, one switch (owner, Nov 3). "Fresh start" is the business on day one: no lessons, no tools, agents at
// version 1, and only the runs made here. "After learning" has the lessons the recorded runs and the measured results
// used. Only this visitor's workspace changes; the company's records and the experiments don't.
export function WorkspaceSwitch({ onFresh }: { onFresh?: () => Promise<unknown> }) {
  const { company, dataVersion, bumpData, refreshSession, setWsMode, wsMode } = useSettings();
  const s = useApi(() => api.freshStatus(company), [company, dataVersion], { keep: true });
  const [busy, setBusy] = useState(false);
  if (!s.data) return null;
  const fresh = wsMode ? wsMode === "fresh" : s.data.fresh;
  // Switching only changes which workspace is active: each keeps its own lessons, tools, drafts, runs and chat.
  // Reset (Fresh start only) is the one action that empties anything.
  async function act(what: "fresh" | "learned" | "reset") {
    if (busy) return;
    setBusy(true);
    try {
      if (what === "reset") await (onFresh ? onFresh() : api.freshStart(company));
      else await api.freshMode(company, what);
      setWsMode(what === "learned" ? "learned" : "fresh");      // every part of the page changes at once
      bumpData();
      refreshSession();
    } finally { setBusy(false); }
  }
  return (
    <div className="ws-switch" role="group" aria-label="Workspace">
      <span className="small muted ws-label">Workspace:</span>
      <button type="button" aria-pressed={fresh} disabled={busy} onClick={() => act("fresh")}
        title="Your workspace from day one: it keeps what you learn and run here until you press Reset">Fresh start</button>
      <button type="button" aria-pressed={!fresh} disabled={busy} onClick={() => act("learned")}
        title="The lessons the recorded runs and the measured results used (mined in EXP-008), the recorded runs, and what you do here">After learning</button>
      {fresh && (
        <button type="button" className="ws-reset" aria-label="Reset" disabled={busy} onClick={() => act("reset")}
          title="Empty Fresh start: its lessons, tools, drafts, conversation and runs. After learning is not touched">
          <RotateCcw size={14} aria-hidden /> <span className="ws-reset-label">Reset</span>
        </button>
      )}
      <span className="small muted ws-count" aria-live="polite">{s.data.lessons} lesson{s.data.lessons === 1 ? "" : "s"} · {s.data.tools} tool{s.data.tools === 1 ? "" : "s"}</span>
    </div>
  );
}
