import { useState } from "react";
import { Dashboard } from "./components/Dashboard";
import { Chat } from "./components/Chat";
import { Roster } from "./components/Roster";
import { ThemeToggle } from "./components/ThemeToggle";
import { About } from "./components/About";
import { Info } from "lucide-react";
import { useNarrow } from "./lib/useNarrow";
import { useSettings } from "./lib/ctx";
import type { RunEvent } from "./types";

// Each step says what it means. Approve and Improve happen outside a run (a person approves what was learned),
// so they never light up during one: only steps backed by a real event do.
const LOOP: { step: string; hint: string; outsideRun?: boolean }[] = [
  { step: "Act", hint: "Agents call tools, hand work to each other and create draft plans." },
  { step: "Observe", hint: "They read results, retry what failed and notice when no tool fits." },
  { step: "Learn", hint: "Repeated work becomes a proposed lesson or tool." },
  { step: "Verify", hint: "Plain code checks every draft: capacity, driver hours, site rules." },
  { step: "Approve", hint: "A person approves anything learned. This happens outside a run.", outsideRun: true },
  { step: "Improve", hint: "Approved lessons make the next run better. This happens outside a run.", outsideRun: true },
];

const STEP: Record<string, string> = {
  tool_call: "Act", draft_created: "Act", handoff: "Act", agent_start: "Act",
  tool_result: "Observe", retry: "Observe", tool_missing: "Observe", lesson_used: "Observe",
  learning_event: "Learn", validator_check: "Verify",
};

export default function App() {
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [runId, setRunId] = useState<string | null>(null);
  const { company, setCompany, companies, session } = useSettings();
  const live = !!session && Object.values(session.models).some((m) => m.available);
  const [prefill, setPrefill] = useState({ text: "", n: 0 });
  const [ask, setAsk] = useState({ label: "", n: 0 }); // the Learning tab asks the chat to run a saved request
  const narrow = useNarrow();
  const [aboutOpen, setAboutOpen] = useState(false);
  const last = events[events.length - 1];
  const finished = last?.type === "agent_done" && last.depth === 0;
  const acting = last && !finished ? last.agent_id : null;
  const current = last && !finished ? STEP[last.type] : undefined;
  const factsEl = (
    <ul className="facts" aria-label="Key facts">
      <li>Drafts only</li>
      <li>A person approves what is learned</li>
      <li>{live ? "Live mode available" : "Replay mode: recorded runs"}</li>
    </ul>
  );
  const stripsEl = (
    <>
      <div className="strips">
        <ol className="loop" aria-label="Closed loop">
          {LOOP.map((l) => (
            <li
              key={l.step}
              title={l.hint}
              className={`${current === l.step ? "on" : ""} ${l.outsideRun ? "later" : ""}`}
              aria-current={current === l.step ? "step" : undefined}
            >
              {l.step}
              <span className="sr-only">: {l.hint}</span>
            </li>
          ))}
        </ol>
        <Roster acting={acting} />
      </div>
    </>
  );
  return (
    <div className="shell">
      <About open={aboutOpen} onClose={() => setAboutOpen(false)} />
      <header className="top">
        <div className="brand">
          <h1>Anubhav</h1>
          <button type="button" className="aboutbtn" onClick={() => setAboutOpen(true)}><Info size={16} aria-hidden /> About</button>
          <ThemeToggle />
          {companies.length > 1 && (
            <label className="company-pick">
              <span className="sr-only">Company</span>
              <select aria-label="Company" value={company} onChange={(e) => { setCompany(e.target.value); setEvents([]); setRunId(null); }}>
                {companies.filter((c) => ["T01", "TNEW"].includes(c.company)).map((c) => <option key={c.company} value={c.company}>{c.name}</option>)}
              </select>
            </label>
          )}
          <p className="pitch">
            An AI team that plans truck loads for a logistics company, learns its unwritten rules, and never dispatches without a person.
          </p>
          {!narrow && (
            <ul className="facts" aria-label="Mode">
              <li title={live ? "Muse Spark 1.3 answers live, within a few runs per visit. Saved requests still replay their recordings." : "No model keys here, so answers replay runs recorded earlier on Muse Spark Open. Nothing is simulated."}>{live ? "Live mode available" : "Replay mode: recorded runs"}</li>
            </ul>
          )}
        </div>
        {narrow ? (
          <details className="about">
            <summary>How it works</summary>
            {factsEl}
            {stripsEl}
          </details>
        ) : (
          stripsEl
        )}
      </header>
      <main className="center">
        <Chat onEvents={(e, id) => { setEvents(e); setRunId(id); }} prefill={prefill} ask={ask} />
      </main>
      <aside className="right" aria-label="Company data">
        <Dashboard refreshKey={events.length} runId={runId} onPlan={(text) => setPrefill((p) => ({ text, n: p.n + 1 }))} onAsk={(label) => setAsk((a) => ({ label, n: a.n + 1 }))} />
      </aside>
    </div>
  );
}
