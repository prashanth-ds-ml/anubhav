import type { Lesson } from "../lib/api";
import { shortTime } from "../lib/text";
import { useFocusTarget } from "../lib/focus";

// The life of one lesson, from its own event history: proposed, checked, decided (and by whom), in use, and when it ends.
// Nothing here is assumed: a step only shows what the lesson's events and state say.

const WHO: Record<string, string> = { "review-rule": "a fixed review rule standing in for a person", reviewer: "a person (you, in this visit)", gate: "the evidence gate (code)" };
const who = (actor: string) => WHO[actor] ?? actor;

interface Step { title: string; text: string; state: "done" | "now" | "off" }

export function lifeSteps(x: Lesson): Step[] {
  const ev = x.events ?? [];
  const proposed = ev.find((e) => e?.action === "propose");
  const decision = [...ev].reverse().find((e) => /^(approve|reject|retire|rollback)/.test(String(e?.action ?? "")));
  const pack = String(x.source ?? "").startsWith("pack:");
  const active = String(x.state ?? "").startsWith("ACTIVE");
  const steps: Step[] = [
    { title: "Proposed", state: "done",
      text: pack ? "Arrived in a shared regional pack from another company" : `From the company's own records${proposed ? `, ${shortTime(proposed.ts)}` : ""}` },
    { title: "Evidence checked", state: "done", text: `By code: ${x.gate?.reason || "no verdict recorded"}` },
  ];
  if (x.state === "EXPIRED" && !decision) {
    steps.push({ title: "Expired on arrival", state: "now", text: x.valid_to ? `Its end date, ${x.valid_to}, had already passed` : "It was already over" });
  } else if (["CANDIDATE", "NEEDS_EVIDENCE", "CHALLENGED"].includes(x.state)) {
    steps.push({ title: "Waiting for a person", state: "now", text: "Nothing changes until a person approves or rejects it" });
  } else if (decision) {
    const verb = decision.action.startsWith("approve") ? "Approved" : decision.action === "reject" ? "Rejected" : decision.action === "retire" ? "Retired" : "Undone";
    steps.push({ title: verb, state: "done", text: `By ${who(decision.actor)}, ${shortTime(decision.ts)}${decision.action === "approve_policy" ? ", as a rule code enforces" : ""}` });
  }
  steps.push(active
    ? { title: "In use", state: "now", text: x.state === "ACTIVE_POLICY" ? "Code blocks any plan that breaks it" : "Given to the agent as advice" }
    : { title: "Not in use", state: "off", text: "Not given to the agent" });
  steps.push({ title: x.valid_to ? (x.state === "EXPIRED" ? "Ended" : "Ends") : "No end date", state: x.state === "EXPIRED" ? "done" : "off",
    text: x.valid_to ? `${x.valid_from ? `${x.valid_from} – ` : ""}${x.valid_to}` : "Kept until a person retires it or the records contradict it" });
  return steps;
}

export function LifeCycle({ lesson, target }: { lesson: Lesson; target: string | null }) {
  const ref = useFocusTarget<HTMLElement>(target, true);
  const steps = lifeSteps(lesson);
  return (
    <section ref={ref} className="life" aria-label="Life of this lesson">
      <h4>Life of this lesson</h4>
      <ol className="life-steps">
        {steps.map((s, i) => (
          <li key={i} className={`life-step ${s.state}`}>
            <span className="life-n" aria-hidden>{i + 1}</span>
            <p className="life-title">{s.title}</p>
            <p className="small muted">{s.text}</p>
          </li>
        ))}
      </ol>
    </section>
  );
}
