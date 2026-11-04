import { api } from "./api";
import { useApi } from "./useApi";
import { useSettings } from "./ctx";

/** This visitor's workspace right now: Fresh start or After learning, and how many approved lessons it has.
 * Re-read whenever data changes (an approval, a reset, the workspace switch). If the server can't be reached, the
 * page behaves as After learning, so its bundled recorded examples still play. */
export function useWorkspace() {
  const { company, dataVersion } = useSettings();
  const s = useApi(() => api.freshStatus(company).then((d) => d ?? { unreachable: true as const }), [company, dataVersion], { keep: true });
  const d = s.data;
  const st = d && !("unreachable" in d) ? d : null;
  return { loaded: !!d, unreachable: !!d && !st, fresh: !!st?.fresh, activeLessons: st?.active_lessons ?? 0, lessons: st?.lessons ?? 0 };
}
