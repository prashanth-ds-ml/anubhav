import { useEffect, useRef, useState } from "react";
import { api, modelName, startRun, voiceStatus } from "../lib/api";
import { Sample } from "./Sample";
import { useApi } from "../lib/useApi";
import { useSettings } from "../lib/ctx";
import { plainReason, Reply } from "../lib/text";
import { focusOn } from "../lib/focus";
import { PlanCard } from "./PlanCard";
import { Mic } from "./Mic";
import { closest } from "../lib/match";
import type { RunEvent } from "../types";
import { Timeline } from "./Timeline";
import { ScenarioCards, SCENARIOS, type ScenarioActions } from "./Scenarios";
import { go } from "../lib/route";
import type { MutableRefObject } from "react";

interface RunInfo { run_id: string; mode: string; bundled?: boolean }
type Msg =
  | { kind: "user"; text: string }
  | { kind: "run"; id: number; events: RunEvent[]; info?: RunInfo; ended: boolean; useLessons: boolean; live: boolean; label?: string }
  | { kind: "note"; text: string; suggestion?: string }
  | { kind: "retired"; id: string; what: string; back: boolean };

const answerOf = (events: RunEvent[]) => events.find((e) => e.type === "agent_done" && e.depth === 0);
const waitingOf = (events: RunEvent[]) => events.find((e) => e.type === "needs_person" && e.depth === 0);

/** What each saved request shows, in the order to try them. Anything not listed goes under "More requests". */
const STORIES: Record<string, { n: string; short: string; caption: string }> = {
  English: { n: "1", short: "Plan a truck", caption: "Plan a truck: the agent drafts, a person decides" },
  Nickname: { n: "2", short: "Learned nickname", caption: "A nickname the company uses, found in its own records" },
  "New tool": { n: "3", short: "Telugu question, no tool", caption: "A data question in Telugu: no tool fits, a teammate writes a query" },
};

function Starters({ compact, onPick }: { compact: boolean; onPick: (label: string) => void }) {
  const { requests } = useSettings();
  const rank = (l: string) => STORIES[l]?.n ?? "9";
  const avail = requests.filter((r) => r.on || r.off).sort((a, b) => rank(a.label).localeCompare(rank(b.label)));
  const stories = avail.filter((r) => STORIES[r.label]).sort((a, b) => STORIES[a.label].n.localeCompare(STORIES[b.label].n));
  const more = avail.filter((r) => !STORIES[r.label]);
  if (avail.length === 0) return null;
  return (
    <div className={`starters ${compact ? "compact" : ""}`} role="group" aria-label="Saved requests">
      {compact
        ? avail.map((r) => (
            <button key={r.label} className="chip" title={r.request} aria-label={`${STORIES[r.label] ? `${STORIES[r.label].n} ${STORIES[r.label].short}` : r.label}: ${r.request}`} onClick={() => onPick(r.label)}>
              {STORIES[r.label] ? `${STORIES[r.label].n} ${STORIES[r.label].short}` : r.label}
            </button>
          ))
        : (
          <>
            {stories.map((r) => (
              <button key={r.label} className="starter" onClick={() => onPick(r.label)}>
                <span className="cap">{STORIES[r.label].n} {STORIES[r.label].caption}</span>
                <span>{r.request}</span>
              </button>
            ))}
            {more.length > 0 && (
              <div className="more-requests">
                <span className="small muted">More requests, in other languages and styles:</span>
                {more.map((r) => <button key={r.label} className="chip" title={r.request} aria-label={`${r.label}: ${r.request}`} onClick={() => onPick(r.label)}>{r.label}</button>)}
              </div>
            )}
          </>
        )}
    </div>
  );
}

/** Who it is for, with its source. On short screens it moves under "Read more", so the scenario cards stay in view. */
function Impact({ className }: { className: string }) {
  return (
    <p className={`small muted ${className}`}>
      For India's small fleet operators, who plan on phone calls and memory: about 75% of truck operators own fewer than five
      trucks (<a href="https://redseer.com/articles/unlocking-growth-in-indias-fragmented-trucking-sector/" target="_blank" rel="noreferrer">Redseer, Dec 2024</a>).
    </p>
  );
}

/** During a scenario, the same saved request in its other languages: each chip plays that recording. */
function Variants({ label, lessons, onPick }: { label?: string; lessons: boolean; onPick: (label: string, lessons?: boolean) => void }) {
  const { requests } = useSettings();
  const all = SCENARIOS.find((s) => s.variants?.some((v) => v.label === label))?.variants;
  const others = all?.filter((v) => v.label !== label && requests.some((r) => r.label === v.label && (lessons ? r.on : r.off)));
  if (!others?.length) return null;
  return (
    <p className="variants small" role="group" aria-label="The same request in other languages">
      <span className="muted">Same request, also recorded in:</span>
      {others.map((v) => {
        const r = requests.find((x) => x.label === v.label)!;
        return <button key={v.label} type="button" className="chip" lang={v.label === "Telugu" ? "te" : undefined} title={r.request} onClick={() => onPick(v.label, lessons)}>{v.text}</button>;
      })}
    </p>
  );
}

/** The scenario guide lives in the App (it stays on screen across main tabs); the chat lends it the actions that need
 * the conversation (play a saved request, send a live one), through `actionsRef`. */
export function Chat({ onEvents, prefill, ask, scenario, onStartScenario, actionsRef }: {
  onEvents: (e: RunEvent[], runId: string | null) => void; prefill: { text: string; n: number }; ask: { label: string; n: number };
  scenario: string | null; onStartScenario: (id: string) => void; actionsRef: MutableRefObject<ScenarioActions | null>;
}) {
  const { company, setCompany, useLessons, setUseLessons, requests, session, ready, live, refreshSession, bumpData } = useSettings();
  const pending = useRef<{ label: string; lessons?: boolean; done: () => void } | null>(null); // a saved request a scenario asked for before the list loaded
  const waiting = useRef<string | null>(null); // text sent before the saved requests loaded
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [draft, setDraft] = useState("");
  const [banner, setBanner] = useState<string | null>(null);
  const [heard, setHeard] = useState<string | null>(null);
  const voice = useApi(voiceStatus);
  const stop = useRef<() => void>(() => {});
  const nextId = useRef(0);
  const log = useRef<HTMLDivElement>(null);
  const field = useRef<HTMLTextAreaElement>(null);
  const follow = useRef(true); // the chat follows the newest message until the person scrolls up themselves

  // Screen readers hear only the moments that matter, not every card.
  const KEY = ["retry", "handoff", "agent_done", "needs_person"];
  const lastRun = [...msgs].reverse().find((m): m is Extract<Msg, { kind: "run" }> => m.kind === "run");
  const latest = lastRun?.events.at(-1);
  const announce = latest && KEY.includes(latest.type) && (!["agent_done", "needs_person"].includes(latest.type) || latest.depth === 0)
    ? latest.type === "retry" ? `Retry ${latest.payload.attempt} of ${latest.payload.of}`
      : latest.type === "handoff" ? `Handing off to ${latest.payload.to}`
      : latest.type === "needs_person" ? `Waiting for you: ${latest.payload.question}`
      : "Answer ready"
    : "";
  useEffect(() => onEvents(lastRun?.events ?? [], lastRun?.info?.run_id ?? null), [lastRun?.events.length, lastRun?.info?.run_id]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => () => stop.current(), []);

  useEffect(() => {
    if (ready && pending.current) { const p = pending.current; pending.current = null; void pick(p.label, p.lessons).then(p.done); } // this render's list, not the one from the click
    if (!ready || waiting.current === null) return;
    const t = waiting.current;
    waiting.current = null;
    setBanner(null);
    submit(t);
  }, [ready]); // eslint-disable-line react-hooks/exhaustive-deps

  // A different company starts a fresh conversation.
  useEffect(() => { stop.current(); setMsgs([]); setBanner(null); }, [company]);

  // "Plan a truck" on an order row drops its request into the box, ready to send.
  useEffect(() => {
    if (!prefill.n) return;
    setDraft(prefill.text);
    field.current?.focus();
    field.current?.scrollIntoView({ block: "nearest" });
  }, [prefill.n]); // eslint-disable-line react-hooks/exhaustive-deps

  // The Learning tab can ask for a saved request to run (for example after a person approves a tool).
  useEffect(() => {
    if (!ask.n) return;
    log.current?.scrollIntoView({ block: "nearest" });
    pick(ask.label);
  }, [ask.n]); // eslint-disable-line react-hooks/exhaustive-deps

  // Keep the newest card (and finally the answer) in view as events arrive.
  useEffect(() => {
    const el = log.current;
    if (!el) return;
    if (msgs.length === 0) { el.scrollTop = 0; return; } // the welcome content starts at the top, never scrolled away
    follow.current = true; // something new arrived: show it
    const calm = matchMedia("(prefers-reduced-motion: reduce)").matches;
    el.scrollTo({ top: el.scrollHeight, behavior: calm ? "auto" : "smooth" });
  }, [msgs]);

  // A message can grow after it is drawn (a font arrives, text re-wraps). Keep the end in view unless the person has scrolled up.
  useEffect(() => {
    const el = log.current;
    if (!el || typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(() => { if (follow.current && msgs.length > 0) el.scrollTop = el.scrollHeight; }); // the welcome screen stays at its top
    [...el.children].forEach((c) => ro.observe(c));
    return () => ro.disconnect();
  }, [msgs]);

  const patch = (id: number, f: (m: Extract<Msg, { kind: "run" }>) => Extract<Msg, { kind: "run" }>) =>
    setMsgs((m) => m.map((x) => (x.kind === "run" && x.id === id ? f(x) : x)));

  /** Start a run; the promise settles when it ends (or is replaced, or has no recording), so a scenario step can wait for it. */
  function run(request: string, lessons: boolean, extra?: string, liveRun = false, label?: string): Promise<void> {
    stop.current();
    let finish = () => {};
    const ended = new Promise<void>((r) => { finish = r; });
    const id = nextId.current++;
    setMsgs((m) => [...m, { kind: "user", text: request }, ...(extra ? [{ kind: "note" as const, text: extra }] : []), { kind: "run", id, events: [], ended: false, useLessons: lessons, live: liveRun, label }]);
    const halt = startRun(request, { company, useLessons: lessons, team: session?.default_team ?? true, live: liveRun }, {
      onEvent: (e) => patch(id, (x) => ({ ...x, events: [...x.events, e] })),
      onRun: (info) => patch(id, (x) => ({ ...x, info, live: info.mode === "live" })),
      onNote: setBanner,
      onEnd: () => { patch(id, (x) => ({ ...x, ended: true })); if (liveRun) refreshSession(); finish(); },
      onNoReplay: (message) => {
        finish();
        setMsgs((m) => [...m.filter((x) => !(x.kind === "run" && x.id === id)), { kind: "note", text: `${message} Pick a saved request below.` }]);
      },
    });
    stop.current = () => { halt(); finish(); };
    return ended;
  }

  /** Run a saved request. If its recording only exists with the other lessons setting, switch to it and say so.
   * A scenario can ask for one setting; the toggle then shows it. */
  function pick(label: string, lessons?: boolean): Promise<void> {
    const r = requests.find((x) => x.label === label);
    if (!r) return Promise.resolve();
    if (lessons !== undefined && (lessons ? r.on : r.off)) { setUseLessons(lessons); return run(r.request, lessons, undefined, false, label); }
    const ok = useLessons ? r.on : r.off;
    if (ok) return run(r.request, useLessons, undefined, false, label);
    const flip = !useLessons;
    setUseLessons(flip);
    return run(r.request, flip, `The saved run for this request is with lessons ${flip ? "on" : "off"}, so I switched that setting.`, false, label);
  }

  function submit(text: string) {
    const t = text.trim();
    if (!t) return;
    setDraft("");
    if (!ready) { // matching now would find nothing: hold it until the saved requests arrive
      waiting.current = t;
      setBanner("Loading the saved requests…");
      return;
    }
    const m = closest(t, requests.map((r) => r.request));
    const label = requests.find((r) => r.request === m?.prompt)?.label;
    if (m?.exact && label) return pick(label);
    if (live.ok) return run(t, useLessons, undefined, true); // live mode answers anything, within this visit's live runs
    setMsgs((cur) => [
      ...cur,
      { kind: "user", text: t },
      m
        ? { kind: "note", text: "I can only replay saved requests in this mode. This one is the closest:", suggestion: m.prompt }
        : { kind: "note", text: "No saved run matches that. Replay mode answers saved requests only; pick one below. Live mode answers anything, and it is off here." },
    ]);
  }

  const gateLesson = async () => (await api.lessons(company)).find((x) => x.kind === "site_access");
  /** Retire the gate-size rule or bring it back, in this visitor's own lessons. Asking for the state it is already in
   * changes nothing: a second "undo" would otherwise undo the approval itself. Retiring leaves a card in the chat. */
  async function gateRule(decision: "retire" | "rollback") {
    const rule = await gateLesson();
    if (!rule) throw new Error("This company has no gate-size rule to change.");
    const active = rule.state.startsWith("ACTIVE");
    if (decision === "retire" && !active) return `${rule.lesson_id} is already retired.`;
    if (decision === "rollback" && active) {
      setMsgs((m) => m.map((x) => (x.kind === "retired" && x.id === rule.lesson_id ? { ...x, back: true } : x)));
      return `${rule.lesson_id} is already active.`;
    }
    await api.decideLesson(company, rule.lesson_id, decision === "retire" ? { decision: "retire", why: "Scenario S4: trying the plan without this rule." } : { decision: "rollback" });
    bumpData();
    setMsgs((m) => decision === "retire"
      ? [...m.filter((x) => !(x.kind === "retired" && x.id === rule.lesson_id)), { kind: "retired", id: rule.lesson_id, what: rule.what || rule.claim, back: false }]
      : m.map((x) => (x.kind === "retired" && x.id === rule.lesson_id ? { ...x, back: true } : x)));
    return decision === "retire" ? `Retired ${rule.lesson_id}: "${rule.what}". The agent will not see it now.` : `${rule.lesson_id} is active again.`;
  }

  const actions: ScenarioActions = {
    runSaved: (label, lessons) => (ready ? pick(label, lessons) : new Promise<void>((done) => { pending.current = { label, lessons, done }; })),
    runLive: (text) => run(text, useLessons, undefined, true),
    openTab: (slug, focus) => { go(slug); if (focus) focusOn(focus); },
    setCompany: (c) => { if (c !== company) setCompany(c); },
    gateRule: (decision) => gateRule(decision),
    gateActive: async () => !!(await gateLesson())?.state.startsWith("ACTIVE"),
    freshStart: async () => {
      stop.current();
      const s = await api.freshStart(company);
      setMsgs([]);
      bumpData();
      const v = Object.values(s.agent_versions);
      return `Started fresh: ${s.lessons} lessons · ${s.tools} tools · agents at version ${v.length && v.every((x) => x === v[0]) ? v[0] : "1"}.`;
    },
    mined: async () => !!(await api.freshStatus(company))?.mined_here,
    setAside: async () => { const r = await api.freshSetAside(company); bumpData(); return r.cancelled; },
    focusBox: () => field.current?.focus(),
    toolApproved: async () => (await api.tools(company)).some((t) => t.status === "active"),
  };
  actionsRef.current = actions; // the latest closures, for the guide in the App

  // During a scenario the company panel follows the story: a new plan opens Route plans.
  const drafted = !!lastRun?.ended && lastRun.events.some((e) => e.type === "draft_created");
  useEffect(() => { if (scenario && drafted) go("plans"); }, [drafted, lastRun?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <section className="chat" aria-label="Agent chat">
      <div
        className="chat-log"
        ref={log}
        onWheel={(e) => { if (e.deltaY < 0) follow.current = false; }} // only the person's own gestures stop the following
        onTouchMove={() => { const e = log.current!; follow.current = e.scrollHeight - e.scrollTop - e.clientHeight < 80; }}
      >
        {msgs.length === 0 && !scenario && (
          <div className="welcome">
            <section className="problem" aria-label="The problem and the idea">
              <p>
                <strong>Every business has rules nobody wrote down.</strong> Anubhav learns them from the company's own records,
                shows the evidence, and a person approves each one before it changes a plan. It never dispatches without a person.
              </p>
              <Impact className="impact" />
              <ul className="muse plain small" aria-label="Built on Meta Muse">
                <li className="muse-head">Built on Meta Muse:</li>
                <li><strong>Spark Open</strong> (open weights) · the agents plan and call tools</li>
                <li><strong>Spark 1.3</strong> · finds lessons, live runs</li>
                <li><strong>Voice Transcribe</strong> · hears Telugu</li>
              </ul>
              <details>
                <summary className="small">Read more</summary>
                <p>
                  A dispatcher near Warangal knows a 32 ft truck can't get into one Jangaon godown. No system records that, so an AI
                  connected to the company's data still sends the truck. Anubhav finds such rules in past trips, and code checks the
                  evidence before a person sees them. All companies and records here are synthetic.
                  {" "}A former FMCG logistics manager told us one truck plan can take 1–1.5 hours, with up to 10 re-plans a day in festival season.
                </p>
                <Impact className="impact-alt" />
              </details>
            </section>
            <ScenarioCards onStart={onStartScenario} />
            <h2>Or play a single saved request</h2>
            <p>You will see who acts, what they try, what fails, and what is learned. Or type your own below.</p>
            <Starters compact={false} onPick={pick} />
          </div>
        )}
        {msgs.map((m, i) => {
          if (m.kind === "user") return <div key={i} className="bubble user">{m.text}</div>;
          if (m.kind === "retired")
            return (
              <section key={i} className={`retired-card ${m.back ? "back" : ""}`} aria-label={m.back ? "You brought a lesson back" : "You retired a lesson"}>
                <div>
                  <p className="retired-head">{m.back ? "You brought the lesson back" : "You retired a lesson"}</p>
                  <p><span className="mono">{m.id}</span> · {m.what}</p>
                  <p className="small muted">{m.back ? "It is active again: the agent is told it on the next run." : "Only your own copy changed. The recorded runs stay as they were."}</p>
                </div>
                {!m.back && <button type="button" className="chip" aria-label={`Undo: bring back ${m.id}`} onClick={() => gateRule("rollback").catch((e) => setBanner((e as Error).message))}>Undo</button>}
              </section>
            );
          if (m.kind === "note")
            return (
              <div key={i} className="bubble agent" role="status">
                <p>{m.text}</p>
                {m.suggestion && (
                  <button className="chip" onClick={() => { const l = requests.find((r) => r.request === m.suggestion)?.label; if (l) pick(l); }}>Run: {m.suggestion}</button>
                )}
              </div>
            );
          const done = answerOf(m.events);
          const waiting = waitingOf(m.events);
          const first = m.events[0];
          const model = first?.payload.model as string | undefined;
          const scripted = !!model && /mock|scripted/i.test(model);
          return (
            <div key={i} className="run">
              {first && scripted && <Sample title="Scripted example." what="This run was produced by a scripted test model to show how a run is displayed. It is not a recording of a real model run." />}
              {first && !scripted && (
                <p className={m.live ? "recorded live" : "recorded"}>
                  {m.live ? "Live run, just now" : `Recorded run${first.ts ? ` · ${first.ts.slice(0, 10)}` : ""}`} · {modelName(model)} · lessons {m.useLessons ? "on" : "off"}
                </p>
              )}
              {!m.live && m.ended && <Variants label={m.label} lessons={m.useLessons} onPick={pick} />}
              <details open>
                <summary>Show how it got there ({m.events.length} steps)</summary>
                {m.events.length === 0 ? <p className="muted small">Starting…</p> : <Timeline events={m.events} />}
              </details>
              {waiting && (
                <div className="bubble agent answer" role="status">
                  <strong>Waiting for you</strong>
                  <Reply text={String(waiting.payload.question)} />
                  <span className="small muted">The run stops here until a person replies. Replying needs live mode, which is off in this demo.</span>
                </div>
              )}
              {done && !waiting ? (
                <div className="bubble agent answer">
                  <strong>Answer</strong>
                  <Reply text={String(done.payload.reply ?? "")} />
                  <span className="small muted">Plans are drafts only; nothing is dispatched without a person.</span>
                </div>
              ) : null}
              {done && !waiting && m.info?.run_id && m.events.some((e) => e.type === "draft_created") ? (
                <PlanCard runId={m.info.run_id} lessonsOn={m.useLessons} />
              ) : (
                !done && !waiting && m.events.length > 0 && !m.ended && <p className="muted small" role="status">Working…</p>
              )}
            </div>
          );
        })}
      </div>

      <p className="sr-only" role="status" aria-live="polite">{announce}</p>
      {banner && <p className="banner" role="status">{banner}</p>}

      <div className="composer">
        {msgs.length > 0 && !scenario && <Starters compact onPick={pick} />}
        <form
          onSubmit={(e) => { e.preventDefault(); submit(draft); field.current?.focus(); }}
          className="composer-form"
        >
          <label htmlFor="ask" className="label">Ask the agents</label>
          <div className="composer-row">
            <Mic
              available={voice.data?.available ?? false}
              reason={voice.loading ? "checking…" : plainReason(voice.data!.reason, "Voice")}
              onTranscript={(text, meta) => {
                refreshSession(); // a transcription counts as a live run
                setDraft((d) => (d.trim() ? `${d.trim()} ${text}` : text));
                setHeard(meta);
                field.current?.focus();
              }}
            />
            <textarea
              id="ask"
              ref={field}
              rows={2}
              value={draft}
              placeholder="Plan a truck for tomorrow's order, or ask about your data…"
              onChange={(e) => { setDraft(e.target.value); setHeard(null); }}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
                  e.preventDefault();
                  submit(draft);
                }
              }}
            />
            <button type="submit" className="send" disabled={!draft.trim()}>Send</button>
          </div>
          {heard && <p className="small" role="status">{heard}</p>}
          <label className="lessons-toggle">
            <input type="checkbox" checked={useLessons} onChange={(e) => setUseLessons(e.target.checked)} />
            <span>Use approved lessons <span className="muted small">(turn off to see what the agent does without them)</span></span>
          </label>
          {live.ok && <p className="small live-hint">Live: Muse Spark 1.3 answers any request · {session?.live_runs_left ?? 0} live runs left in this visit</p>}
          <p className="small muted">{live.ok ? "" : "Replay answers saved requests only · "}Enter sends · Shift+Enter adds a line</p>
        </form>
      </div>
    </section>
  );
}
