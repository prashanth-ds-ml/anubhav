import { useEffect, useRef, useState } from "react";
import { Dashboard } from "./components/Dashboard";
import { Chat } from "./components/Chat";
import { Roster } from "./components/Roster";
import { ThemeToggle } from "./components/ThemeToggle";
import { About } from "./components/About";
import { Learning } from "./components/Learning";
import { NewTools } from "./components/NewTools";
import { AgentCards } from "./components/AgentCards";
import { Proof } from "./components/Proof";
import { RunsList } from "./components/RunsList";
import { LiveMeter } from "./components/LiveMeter";
import { MainNav, MAIN_LABEL } from "./components/MainNav";
import { ScenarioGuide, SCENARIOS, type LoopStep, type ScenarioActions } from "./components/Scenarios";
import { Info } from "lucide-react";
import { useNarrow } from "./lib/useNarrow";
import { useSettings } from "./lib/ctx";
import { go, useRoute } from "./lib/route";
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
  const { company, setCompany, companies } = useSettings();
  const route = useRoute();
  const [prefill, setPrefill] = useState({ text: "", n: 0 });
  const [ask, setAsk] = useState({ label: "", n: 0 }); // a tab asks the chat to run a saved request
  const narrow = useNarrow();
  const [aboutOpen, setAboutOpen] = useState(false);

  // The scenario guide belongs to the whole app, so it stays on screen when a step opens another main tab.
  const [scenario, setScenario] = useState<string | null>(null);
  const chatActions = useRef<ScenarioActions | null>(null);
  const toDesk = () => { if (route.main !== "desk") go("desk"); };
  const actions: ScenarioActions = {
    runSaved: (label, lessons) => { toDesk(); chatActions.current?.runSaved(label, lessons); },
    runLive: (text) => { toDesk(); chatActions.current?.runLive(text); },
    openTab: (slug, focus) => chatActions.current?.openTab(slug, focus),
    setCompany: (c) => chatActions.current?.setCompany(c),
    gateRule: (d) => chatActions.current!.gateRule(d),
    focusBox: () => { toDesk(); chatActions.current?.focusBox(); },
    toolApproved: () => chatActions.current!.toolApproved(),
    gateActive: () => chatActions.current!.gateActive(),
  };
  const [reached, setReached] = useState<LoopStep[]>([]); // Approve and Improve, once a scenario reaches them
  function startScenario(id: string) {
    const s = SCENARIOS.find((x) => x.id === id);
    if (!s) return;
    setScenario(id);
    setReached([]);
    toDesk();
    if (s.id !== "S3" && s.company !== company) setCompany(s.company); // S3 switches company as its first step
  }
  // A link can open a scenario directly (/?tour=S1), for the README and the video.
  useEffect(() => {
    const id = new URLSearchParams(window.location.search).get("tour")?.toUpperCase();
    if (id) startScenario(id);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const last = events[events.length - 1];
  const finished = last?.type === "agent_done" && last.depth === 0;
  const acting = last && !finished ? last.agent_id : null;
  const current = last && !finished ? STEP[last.type] : undefined;
  const companyEl = companies.length > 1 && (
    <label className="company-pick">
      <span className="sr-only">Company</span>
      <select aria-label="Company" value={company} onChange={(e) => { setCompany(e.target.value); setEvents([]); setRunId(null); }}>
        {companies.filter((c) => ["T01", "TNEW"].includes(c.company)).map((c) => <option key={c.company} value={c.company}>{c.name}</option>)}
      </select>
    </label>
  );
  const stripsEl = (
    <div className="strips">
      {!narrow && companyEl}
      <ol className="loop" aria-label="Closed loop">
        {LOOP.map((l) => {
          const lit = reached.includes(l.step as LoopStep);
          return (
            <li
              key={l.step}
              title={l.hint}
              className={`${current === l.step ? "on" : ""} ${l.outsideRun && !lit ? "later" : ""} ${lit ? "lit" : ""}`}
              aria-current={current === l.step ? "step" : undefined}
            >
              {l.step}{lit && <span aria-hidden> ✓</span>}
              <span className="sr-only">: {lit ? "reached in this scenario. " : ""}{l.hint}</span>
            </li>
          );
        })}
      </ol>
      <Roster acting={acting} />
    </div>
  );
  const onDesk = route.main === "desk";
  return (
    <div className="shell">
      <About open={aboutOpen} onClose={() => setAboutOpen(false)} />
      <header className="top">
        <div className="brand">
          <h1>Anubhav</h1>
          {narrow && companyEl}
          <MainNav current={route.main} narrow={narrow} />
          <LiveMeter compact={narrow} />
          <button type="button" className="aboutbtn" onClick={() => setAboutOpen(true)}><Info size={16} aria-hidden /> About</button>
          <ThemeToggle />
        </div>
        {narrow ? (
          <details className="about">
            <summary>How it works</summary>
            <ul className="facts" aria-label="Key facts"><li>Drafts only</li><li>A person approves what is learned</li></ul>
            {stripsEl}
          </details>
        ) : (
          stripsEl
        )}
      </header>
      {scenario && <ScenarioGuide key={scenario} id={scenario} actions={actions} runId={runId} onClose={() => { setScenario(null); setReached([]); }}
        onLoop={setReached} onStart={startScenario} />}
      <div className={`body ${onDesk ? "" : "full"}`} id="page">
        {/* The chat stays mounted on every tab, so a conversation and a scenario's runs survive a visit to Learning. */}
        <main className="center" hidden={!onDesk}>
          <Chat
            onEvents={(e, id) => { setEvents(e); setRunId(id); }}
            prefill={prefill}
            ask={ask}
            scenario={scenario}
            onStartScenario={startScenario}
            actionsRef={chatActions}
          />
        </main>
        {onDesk ? (
          <aside className="right" aria-label="Company data">
            <Dashboard panel={route.desk} refreshKey={events.length} runId={runId} onPlan={(text) => setPrefill((p) => ({ text, n: p.n + 1 }))} />
          </aside>
        ) : (
          <main className="page">
            <section role="tabpanel" aria-labelledby={`main-tab-${route.main}`}>
            <h2 className="sr-only">{MAIN_LABEL[route.main]}</h2>
            {route.main === "learning" && <Learning item={route.item} />}
            {route.main === "tools" && <NewTools onAsk={(label) => { go("desk"); setAsk((a) => ({ label, n: a.n + 1 })); }} />}
            {route.main === "agents" && <AgentCards />}
            {route.main === "runs" && <RunsList />}
            {route.main === "proof" && <Proof />}
            </section>
          </main>
        )}
      </div>
    </div>
  );
}
