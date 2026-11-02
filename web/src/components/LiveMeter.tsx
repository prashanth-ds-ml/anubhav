import { useSettings } from "../lib/ctx";

/** What the live budget looks like right now, from the server's session. Null when this host has no model key. */
export function liveBudget(session: ReturnType<typeof useSettings>["session"]) {
  if (!session) return null;
  const m = session.models["Muse Spark 1.3"];
  if (!m || (!m.available && /no `[^`]+` set/.test(m.reason ?? ""))) return null; // no key: replay only, no meter
  const perVisit = session.caps.per_session;
  const used = session.live_runs_used ?? perVisit - session.live_runs_left;
  const visitLeft = Math.max(0, perVisit - used);
  const dayLeft = session.live_runs_left_today ?? session.live_runs_left;
  return { perVisit, visitLeft, dayLeft, perDay: session.caps.per_day, left: Math.min(visitLeft, dayLeft) };
}

/** Always on screen in the header when live mode exists: how many live runs this visit has left, and why none when none. */
export function LiveMeter({ compact = false }: { compact?: boolean }) {
  const { session } = useSettings();
  const b = liveBudget(session);
  if (!b) {
    return (
      <p className="mode-pill" title="No model key on this host, so answers replay runs recorded earlier on Muse Spark Open. Nothing is simulated.">
        Replay mode: recorded runs
      </p>
    );
  }
  const label = b.dayLeft === 0
    ? `Today's ${b.perDay} live runs for this demo are used up. Recorded scenarios still work.`
    : b.visitLeft === 0
      ? "No live runs left in this visit. Recorded scenarios still work."
      : `${b.visitLeft} of ${b.perVisit} live runs left in this visit`;
  return (
    <div className={`live-meter ${b.left === 0 ? "empty" : ""}`} role="status" aria-live="polite" aria-label={`Live mode, Muse Spark 1.3. ${label}`}>
      <span className="live-badge"><span className="live-dot" aria-hidden /> LIVE · Muse Spark 1.3</span>
      {b.left > 0 && (
        <span className="live-blocks" aria-hidden>
          {Array.from({ length: b.perVisit }, (_, i) => <span key={i} className={i < b.perVisit - b.visitLeft ? "used" : "left"} />)}
        </span>
      )}
      {b.left === 0 ? <span className="live-text">{label}</span> : (
        <>
          {!compact && <span className="live-text long">{label}</span>}
          <span className={`live-text short ${compact ? "always" : ""}`}>{b.visitLeft} of {b.perVisit} left</span>
        </>
      )}
    </div>
  );
}
