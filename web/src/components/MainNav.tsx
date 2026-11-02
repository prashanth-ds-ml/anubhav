import { go, MAIN, type Main } from "../lib/route";

export const MAIN_LABEL: Record<Main, string> = {
  desk: "Dispatch Desk", learning: "Learning", tools: "Tools", agents: "Agents", runs: "Runs", proof: "Proof & audit",
};

/** The six main tabs. On a phone they become a section menu. */
export function MainNav({ current, narrow }: { current: Main; narrow: boolean }) {
  if (narrow) {
    return (
      <label className="section-pick">
        <span className="sr-only">Section</span>
        <select aria-label="Section" value={current} onChange={(e) => go(e.target.value)}>
          {MAIN.map((m) => <option key={m} value={m}>{MAIN_LABEL[m]}</option>)}
        </select>
      </label>
    );
  }
  // Arrow keys, Home and End move between tabs, as people expect from a tab list.
  function onKey(e: React.KeyboardEvent) {
    const i = MAIN.indexOf(current);
    const to = { ArrowRight: (i + 1) % MAIN.length, ArrowLeft: (i + MAIN.length - 1) % MAIN.length, Home: 0, End: MAIN.length - 1 }[e.key as string];
    if (to === undefined) return;
    e.preventDefault();
    go(MAIN[to]);
    document.getElementById(`main-tab-${MAIN[to]}`)?.focus();
  }
  return (
    <div role="tablist" aria-label="Main" className="main-nav" onKeyDown={onKey}>
      {MAIN.map((m) => (
        <button
          key={m}
          id={`main-tab-${m}`}
          role="tab"
          type="button"
          aria-selected={current === m}
          aria-controls="page"
          tabIndex={current === m ? 0 : -1}
          onClick={() => go(m)}
        >
          {MAIN_LABEL[m]}
        </button>
      ))}
    </div>
  );
}
