import type { RunEvent } from "../types";
import plain from "../../fixtures/plain_plan.jsonl?raw";
import handoff from "../../fixtures/handoff_analyst.jsonl?raw";
import retry from "../../fixtures/retry_tool_missing.jsonl?raw";
import needs from "../../fixtures/needs_person.jsonl?raw";

export const parseJsonl = (s: string): RunEvent[] => s.split("\n").filter(Boolean).map((l) => JSON.parse(l));

/**
 * Event streams bundled with the app. They play only when the server cannot be reached. Each is labelled by the model
 * named in its first event: runs from the scripted test model say so. The request text is the first event's request.
 */
export const BUNDLED: { events: RunEvent[]; request: string }[] = [plain, handoff, retry, needs].map((s) => {
  const events = parseJsonl(s);
  return { events, request: events[0].payload.request as string };
});
