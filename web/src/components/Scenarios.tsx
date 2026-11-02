import { CheckCircle2, ChevronDown, ChevronUp, Circle, Film, Play, X } from "lucide-react";
import { useEffect, useState } from "react";
import { useSettings } from "../lib/ctx";
import { plainReason } from "../lib/text";
import { liveBudget } from "./LiveMeter";
import { ComparePair } from "./PlanCard";

// The demo script for judges. These are the demo world's saved requests and steps, written for people to follow; the
// agent never reads this file. Recorded scenarios replay real runs and cost nothing; live ones run Muse Spark 1.3 now.

const REPO = "https://github.com/prashanth-ds-ml/anubhav/blob/main/";
const JANGAON = "Roman Telugu"; // the saved request "Repu Jangaon Lakshmi Agencies load ki bandi pettu. ..."
const JANGAON_TEXT = "Repu Jangaon Lakshmi Agencies load ki bandi pettu. Dispatch confirm cheyyaku.";

export interface ScenarioActions {
  /** Play a saved request; settles when the run has ended. */
  runSaved: (label: string, lessons?: boolean) => Promise<void>;
  /** Send a request live; settles when the run has ended. */
  runLive: (text: string) => Promise<void>;
  /** Open a tab; with a focus target, scroll to that item there and highlight it. */
  openTab: (slug: string, focus?: string) => void;
  setCompany: (c: string) => void;
  /** Retire the gate-size rule, or undo that, in this visitor's own lesson store. Returns what happened, in words. */
  gateRule: (decision: "retire" | "rollback") => Promise<string>;
  focusBox: () => void;
  /** True once this visitor has an approved tool. */
  toolApproved: () => Promise<boolean>;
  /** True while this visitor's gate-size rule is active. */
  gateActive: () => Promise<boolean>;
}

/** The two loop steps that happen outside a run; a scenario lights them when it reaches them. */
export type LoopStep = "Approve" | "Improve";

interface Step {
  label: string; caption: string; live?: boolean; act: (a: ScenarioActions) => void | Promise<string | void>;
  /** A step done somewhere else (in a tab) ticks only when this says so, not when its button is pressed. */
  until?: (a: ScenarioActions) => Promise<boolean>;
  /** With `until`: the step also ticks without its button, once it is next and `until` says so (an Undo in the chat). */
  auto?: boolean;
  /** The loop step this one reaches. */
  loop?: LoopStep;
}
export interface Scenario {
  id: string; title: string; kind: "recorded" | "live"; minutes: number; proves: string; company: string;
  /** The card's one line: what you will see. `proves` is what it shows, said in the guide. */
  blurb: string;
  /** The card's badge, when "Recorded · watch it" isn't quite right (S6 explores recorded data, not a recorded run). */
  badge?: string;
  steps: Step[]; evidence: { label: string; href: string }[]; honest?: string;
  /** A saved request whose before and after the guide shows once every step is done, with the sentence that frames it. */
  finale?: string;
  finaleLine?: string;
  /** The same request recorded in other languages (saved-request label, and how its chip reads). */
  variants?: { label: string; text: string }[];
}

export const SCENARIOS: Scenario[] = [
  {
    id: "S1", title: "The rule nobody wrote down", kind: "recorded", minutes: 1, company: "T01", blurb: "Asked in Telugu, Roman Telugu or English: 32 ft, then 22 ft after one lesson.",
    proves: "It learns a rule from the company's own records, a person approves it, and the next plan changes.",
    steps: [
      { label: "Play the request without lessons", caption: "A recorded run. The agent drafts a 32 ft truck: nothing in the data says this gate is too small for it.", act: (a) => a.runSaved(JANGAON, false) },
      { label: "See what it learned", caption: "In Learning: \"Lakshmi Agencies, Jangaon: vehicles longer than 22 ft cannot enter\", with the trips that were turned back as evidence. Plain code checked the evidence before a person approved it.", act: (a) => a.openTab("learning", "lesson:site_access") },
      { label: "Undo and redo the approval yourself", caption: "Use the buttons on that lesson. This runs real code on your own copy of the lessons; no model is called and nothing is recorded.", act: (a) => a.openTab("learning", "lesson:site_access"), loop: "Approve" },
      { label: "Play the same request with lessons", caption: "Same model, same request: it now drafts a 22 ft truck and says which rule it followed.", act: (a) => a.runSaved(JANGAON, true), loop: "Improve" },
    ],
    evidence: [
      { label: "The recorded runs (demo/replay_runs.jsonl)", href: `${REPO}demo/replay_runs.jsonl` },
      { label: "EXP-008 report: what was learned for this company", href: `${REPO}artifacts/learning/exp008_20261029_170351_report_T01.md` },
    ],
    finale: JANGAON_TEXT,
    finaleLine: "Same model, same request. The only difference is one lesson it learned from the company's own records, checked by code and approved.",
    variants: [{ label: "Telugu", text: "తెలుగు" }, { label: "English", text: "English" }, { label: "Mixed", text: "Mixed" }, { label: JANGAON, text: "Roman Telugu" }],
  },
  {
    id: "S2", title: "It builds its own tool", kind: "recorded", minutes: 2, company: "T01", blurb: "5 tool calls, then 1 once you approve the tool it wrote.",
    proves: "Work it keeps repeating becomes a checked tool, but only after a person approves it.",
    steps: [
      { label: "Ask the Telugu data question", caption: "A recorded run. No tool fits, so the Planner hands the question to Tool Forge, which writes its own read-only queries to answer it. It takes many steps.", act: (a) => a.runSaved("New tool") },
      { label: "Check and approve the query as a tool", caption: "In New tools: Check this query runs it in code on the original questions and on values it never saw. Then Approve as a tool. A tool that fails its checks cannot be approved.", act: (a) => a.openTab("tools", "tool:story"), until: (a) => a.toolApproved(), loop: "Approve" },
      { label: "Ask the same question again", caption: "Now the agent calls the approved tool once and answers directly (Saturday). New tools shows the recorded before and after: 5 tool calls against 1.", act: (a) => a.runSaved("New tool"), loop: "Improve" },
    ],
    evidence: [
      { label: "EXP-012b: learned tools used in 14 of 16 cases", href: `${REPO}artifacts/benchmark/exp012b_20261030_233756.json` },
      { label: "The recorded runs (demo/replay_runs.jsonl)", href: `${REPO}demo/replay_runs.jsonl` },
    ],
  },
  {
    id: "S3", title: "A new company on day 1", kind: "recorded", minutes: 1, company: "TNEW", blurb: "Shared regional lessons: 33% to 100% on new-company cases.",
    proves: "A new customer gets the region's safe lessons from the first day; private rules stay private.",
    steps: [
      { label: "Switch to the new company", caption: "Bhadrakali Transport Co has no history with Anubhav.", act: (a) => a.setCompany("TNEW") },
      { label: "Play the request without shared lessons", caption: "A recorded run: a 32 ft truck again.", act: (a) => a.runSaved(JANGAON, false) },
      { label: "Play it with shared lessons", caption: "The regional lesson about this gate arrives with the shared pack, so it drafts a 22 ft truck on day 1.", act: (a) => a.runSaved(JANGAON, true), loop: "Improve" },
      { label: "See the measured result", caption: "In Proof: on new-company cases the score went from 33% to 100%, with no private rule leaking across companies.", act: (a) => a.openTab("proof/claims", "proof:transfer") },
    ],
    evidence: [
      { label: "EXP-011R: the benchmark, 3 repeats", href: `${REPO}artifacts/benchmark/exp011r_20261030_230811.json` },
      { label: "EXP-008 report for the new company", href: `${REPO}artifacts/learning/exp008_20261029_170351_report_TNEW.md` },
    ],
    finale: JANGAON_TEXT,
    finaleLine: "Same model, same request, a company with no history. The only difference is the region's shared lessons, there from day 1.",
  },
  {
    id: "S6", title: "Roads change: the Kazipet bridge", kind: "recorded", badge: "Recorded data · explore it", minutes: 1, company: "T01", blurb: "Drivers' notes become route knowledge that expires.",
    proves: "Route knowledge comes from drivers, can be shared with the region, and ends when the road reopens.",
    steps: [
      { label: "Open the road story", caption: "A bridge at Kazipet closed for two months. No system recorded it; the drivers did, in their own words.", act: (a) => a.openTab("learning", "lesson:closure") },
      { label: "Read what the drivers wrote", caption: "Notes in Telugu, Roman Telugu and English, on the trips the closure delayed, linked by trip and stop in the records.", act: (a) => a.openTab("learning", "lesson:closure/notes") },
      { label: "See the delays start and stop", caption: "Closure delays by week: every one inside the closure, none after the road reopened.", act: (a) => a.openTab("learning", "lesson:closure/chart") },
      { label: "See why it is no longer used", caption: "It was learned after the road reopened, so it was stored as expired and is not given to the agent. Road lessons can travel in a regional pack to other companies.", act: (a) => a.openTab("learning", "lesson:closure/life") },
    ],
    evidence: [
      { label: "How the gate checks a closure (learning/gate.py)", href: `${REPO}src/anubhav/learning/gate.py` },
      { label: "Which lesson kinds can be shared (learning/pack.py)", href: `${REPO}src/anubhav/learning/pack.py` },
    ],
  },
  {
    id: "S4", title: "Your lessons, your call", kind: "live", minutes: 2, company: "T01", blurb: "Switch the rule off and on, and watch the plan follow.",
    proves: "The lesson causes the change: you switch it off and on, and the plan follows.",
    honest: "Live on Muse Spark 1.3. In our own test each step behaved as described once; a model can answer differently, so you may see something else.",
    steps: [
      { label: "Retire the 22 ft gate rule", caption: "This changes your own copy of the lessons only.", act: (a) => a.gateRule("retire") },
      { label: "Send the request live", caption: "Without the rule the agent has no reason to avoid a 32 ft truck. In our test it drafted a 32 ft truck (V11).", live: true, act: (a) => a.runLive(JANGAON_TEXT) },
      { label: "Bring the rule back", caption: "Undo the retirement, here or with Undo on the card in the chat: the rule is active again.", act: (a) => a.gateRule("rollback"),
        until: (a) => a.gateActive(), auto: true, loop: "Approve" },
      { label: "Send the same request live again", caption: "With the rule it should pick a 22 ft truck and name the rule. In our test it chose V08 (22 ft).", live: true, act: (a) => a.runLive(JANGAON_TEXT), loop: "Improve" },
    ],
    evidence: [{ label: "Our test runs of this scenario (run log)", href: `${REPO}docs/trackers/run_logs.md` }],
  },
  {
    id: "S5", title: "Try to break it", kind: "live", minutes: 3, company: "T01", blurb: "Dispatch now, overload, wrong time, nicknames, or your own.",
    proves: "The model proposes; plain code enforces the limits; a person decides. Try any of these, or write your own.",
    honest: "Live on Muse Spark 1.3. Each challenge behaved as described once in our test; a model can answer differently.",
    steps: [
      { label: "\"Confirm the dispatch now\"", caption: "It should only make a draft: dispatching is a person's job, and code holds that line.", live: true, act: (a) => a.runLive("Lakshmi Agencies Jangaon order ki bandi pettu, dispatch ippude confirm cheyyi.") },
      { label: "Overload one truck", caption: "Three orders, about 27 t, on one 9 t truck. The load check refuses it and says why.", live: true, act: (a) => a.runLive("Put all three Jangaon orders (Sri Rama Warehousing, Lakshmi Agencies, Sri Venkateswara Traders) on vehicle V08 tomorrow.") },
      { label: "Deliver at the wrong time", caption: "This site only receives at night, a rule it learned. A 9 am delivery should be refused, with a night slot offered.", live: true, act: (a) => a.runLive("Sri Rama Warehousing Jangaon order ki bandi pettu, repu morning 9 ki deliver avvali.") },
      { label: "Use the company's nicknames", caption: "\"Nalla lorry\" and \"pedda godown\" are in no system; it learned them from the records.", live: true, act: (a) => a.runLive("Nalla lorry lo pedda godown load pettu, repu.") },
      { label: "Write your own", caption: "Type or speak any request in Telugu or English below. Every plan is a draft and is checked by code.", act: (a) => a.focusBox() },
    ],
    evidence: [{ label: "Our test runs of these challenges (run log)", href: `${REPO}docs/trackers/run_logs.md` }],
  },
];

export function ScenarioCards({ onStart }: { onStart: (id: string) => void }) {
  const { live, session } = useSettings();
  const budget = liveBudget(session);
  return (
    <section className="scenarios" aria-labelledby="sc-title">
      <h2 id="sc-title">Try it: six scenarios</h2>
      <p className="small muted sc-sub">Four replay real recordings and cost nothing. Two run the model live, so you can test what we claim.</p>
      <ul className="sc-grid">
        {SCENARIOS.map((s) => {
          const off = s.kind === "live" && !live.ok;
          return (
            <li key={s.id} className={`sc-card is-${s.kind}`}>
              <article aria-label={`${s.id} ${s.title}`}>
                <p className={`sc-badge is-${s.kind}`}>
                  {s.kind === "recorded" ? <><Film size={14} aria-hidden /> {s.badge ?? "Recorded · watch it"}</> : <><Play size={14} aria-hidden /> Live · you run it</>}
                </p>
                <h3><span className="sc-id">{s.id}</span> {s.title}</h3>
                <p className="small">{s.blurb}</p>
                <p className="small muted">
                  About {s.minutes} min · {s.kind === "recorded" ? "free" : `uses up to ${s.steps.filter((x) => x.live).length} live runs`}
                  {s.kind === "live" && budget && <strong className="runs-left"> · {budget.left} of {budget.perVisit} left</strong>}
                </p>
                {off ? (
                  <p className="small sc-off">{plainReason(live.reason)} Try S1 to S3, which replay the same kinds of runs.</p>
                ) : null}
                <button type="button" className="sc-start" disabled={off} onClick={() => onStart(s.id)}>Start {s.id}</button>
              </article>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

/** At the end of a scenario, the next one in the order of the cards (live ones only when live mode is on). */
function NextScenario({ id, onStart }: { id: string; onStart?: (id: string) => void }) {
  const { live } = useSettings();
  const n = SCENARIOS.slice(SCENARIOS.findIndex((x) => x.id === id) + 1).find((x) => x.kind === "recorded" || live.ok);
  if (!n || !onStart) return null;
  return <button type="button" className="link-btn sc-next" onClick={() => onStart(n.id)}>Next scenario: {n.id}, {n.title} →</button>;
}

export function ScenarioGuide({ id, actions, runId, onClose, onLoop, onStart }: {
  id: string; actions: ScenarioActions; runId: string | null; onClose: () => void; onLoop?: (reached: LoopStep[]) => void; onStart?: (id: string) => void;
}) {
  const s = SCENARIOS.find((x) => x.id === id)!;
  const { live, session, dataVersion } = useSettings();
  const [done, setDone] = useState<Set<number>>(new Set());
  const [waiting, setWaiting] = useState<Set<number>>(new Set()); // pressed, but finished elsewhere (see Step.until)
  const [note, setNote] = useState<string | null>(null);
  const [busy, setBusy] = useState<number | null>(null);
  const [open, setOpen] = useState(false);
  const next = s.steps.findIndex((_, j) => !done.has(j));
  const allDone = next === -1;

  // A step finished in a tab (approving a tool) ticks when the visitor's data says so. An `auto` step after one that is
  // done ticks the same way without its button being pressed (the rule brought back with Undo on the chat card).
  useEffect(() => {
    const check = new Set(waiting);
    const first = Math.min(...done); // an auto step counts once the scenario has started before it
    s.steps.forEach((st, i) => { if (st.auto && !done.has(i) && i > first) check.add(i); });
    check.forEach((i) => s.steps[i].until?.(actions).then((ok) => {
      if (!ok) return;
      setDone((d) => new Set(d).add(i));
      setWaiting((w) => { const x = new Set(w); x.delete(i); return x; });
    }));
  }, [dataVersion, waiting, done]); // eslint-disable-line react-hooks/exhaustive-deps

  // The loop strip lights Approve and Improve once the scenario has reached them.
  useEffect(() => {
    onLoop?.([...new Set(s.steps.filter((st, i) => done.has(i) && st.loop).map((st) => st.loop!))]);
  }, [done]); // eslint-disable-line react-hooks/exhaustive-deps

  async function go(i: number) {
    setBusy(i);
    setNote(null);
    try {
      // A step that plays a run ticks when the run has ended, not when its button is pressed (at most 5 minutes).
      const msg = await Promise.race([s.steps[i].act(actions), new Promise<void>((r) => setTimeout(r, 300_000))]);
      if (msg) setNote(msg);
      if (s.steps[i].until) setWaiting((w) => new Set(w).add(i));
      else setDone((d) => new Set(d).add(i));
    } catch (e) {
      setNote((e as Error).message);
    } finally {
      setBusy(null);
    }
  }

  const stepButton = (i: number, big = false) => {
    const st = s.steps[i];
    const off = busy !== null || (!!st.live && !live.ok);
    return (
      <button type="button" className={`sc-step ${big ? "big" : ""}`} disabled={off} onClick={() => go(i)}>
        {st.label}{st.live ? " (live)" : ""}
      </button>
    );
  };

  return (
    <section className={`sc-guide ${open ? "open" : ""}`} aria-label={`Scenario ${s.id}: ${s.title}`}>
      <header className="sc-guide-head">
        <p className={`sc-badge is-${s.kind}`}>{s.kind === "recorded" ? <><Film size={14} aria-hidden /> Recorded</> : <><Play size={14} aria-hidden /> Live</>}</p>
        <h2><span className="sc-id">{s.id}</span> {s.title}</h2>
        <ol className="sc-dots" aria-label="Progress">
          {s.steps.map((st, i) => (
            <li key={st.label} className={done.has(i) ? "done" : i === next ? "now" : ""} title={st.label}>
              {done.has(i) ? <CheckCircle2 size={16} aria-label={`Step ${i + 1} done`} /> : <span aria-label={`Step ${i + 1}${i === next ? ", next" : ""}`}>{i + 1}</span>}
            </li>
          ))}
        </ol>
        <button type="button" className="sc-more" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
          {open ? <ChevronUp size={16} aria-hidden /> : <ChevronDown size={16} aria-hidden />} {open ? "Less" : "All steps"}
        </button>
        <button type="button" className="sc-close" onClick={onClose} aria-label="Close the scenario"><X size={18} aria-hidden /></button>
      </header>

      {!open && (
        allDone ? (
          <div className="sc-now">
            {s.finaleLine ? <p className="sc-finale"><strong>All {s.steps.length} steps done.</strong> {s.finaleLine}</p> : <p className="small"><strong>Done.</strong> {s.proves}</p>}
            {s.finale && <ComparePair request={s.finale} />}
            <NextScenario id={s.id} onStart={onStart} />
          </div>
        ) : (
          <div className="sc-now">
            {stepButton(next, true)}
            <p className="small muted">{waiting.has(next) ? "Waiting for you to approve a tool in New tools. " : ""}{s.steps[next].caption}</p>
          </div>
        )
      )}
      {s.honest && <p className="small sc-honest">{s.honest}{session ? ` ${session.live_runs_left} live runs left in this visit.` : ""}</p>}
      {note && <p className="small" role="status">{note}</p>}

      {open && (
        <>
          <p className="small">{s.proves}</p>
          <ol className="sc-steps">
            {s.steps.map((st, i) => (
              <li key={st.label} className={done.has(i) ? "done" : ""}>
                {done.has(i) ? <CheckCircle2 size={18} aria-label="Done" className="sc-tick" /> : <Circle size={18} aria-hidden className="sc-tick muted" />}
                <div>
                  {stepButton(i)}
                  <p className="small muted">{st.caption}</p>
                </div>
              </li>
            ))}
          </ol>
          {allDone && s.finale && <ComparePair request={s.finale} />}
          <details className="sc-evidence" open>
            <summary>Check it yourself</summary>
            <ul className="plain small">
              {runId && <li><a href={`/api/runs/${encodeURIComponent(runId)}`} target="_blank" rel="noreferrer">The full record of the run on screen (JSON)</a></li>}
              {s.evidence.map((e) => <li key={e.href}><a href={e.href} target="_blank" rel="noreferrer">{e.label}</a></li>)}
            </ul>
          </details>
        </>
      )}
    </section>
  );
}
