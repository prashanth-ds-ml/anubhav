import { api, type Lesson } from "../lib/api";
import { useApi } from "../lib/useApi";
import { useSettings } from "../lib/ctx";

export interface TruckRow { label?: string; vehicle: string; length_ft: number }

/** How many trucks the gate turned back, from the lesson's own evidence (null until it arrives, or if it has none). */
export function useTurnedBack(lesson: Lesson | undefined): number | null {
  const { company } = useSettings();
  const e = useApi(() => (lesson ? api.evidence(company, lesson.lesson_id) : Promise.resolve(null)), [company, lesson?.lesson_id]);
  return e.data?.kind === "trips" ? (e.data.rows ?? []).filter((r) => r.status === "returned").length : null;
}

/** Trucks drawn to scale against a gate's learned length limit. The bars are a picture of the same facts the words say:
 * every bar carries its length and ✓ fits or ✕ too long, so colour is never the only signal. */
export function TruckScale({ rows, limit, lesson, small }: { rows: TruckRow[]; limit: number; lesson?: Lesson; small?: boolean }) {
  const back = useTurnedBack(lesson);
  const top = Math.max(limit, ...rows.map((r) => r.length_ft)) * 1.15; // a little room past the longest
  const pct = (ft: number) => `${(100 * ft) / top}%`;
  const said = rows.map((r) => `${r.label ? `${r.label}: ` : ""}${r.vehicle}, ${r.length_ft} ft, ${r.length_ft <= limit ? "fits" : "too long"}`).join("; ");
  return (
    <figure className={`truck-scale ${small ? "small" : ""}`} aria-label={`Truck lengths against the gate limit of ${limit} ft. ${said}.`}>
      <ul className="plain ts-rows">
        {rows.map((r) => {
          const ok = r.length_ft <= limit;
          return (
            <li key={`${r.label}-${r.vehicle}`} className="ts-row">
              {r.label && <span className="ts-label small">{r.label}</span>}
              <span className="ts-track">
                <span className={`ts-bar ${ok ? "ok" : "bad"}`} style={{ width: pct(r.length_ft) }}>
                  {r.length_ft} ft · {r.vehicle} · {ok ? "✓ fits" : "✕ too long"}
                </span>
                <span className="ts-limit" style={{ left: pct(limit) }} aria-hidden />
              </span>
            </li>
          );
        })}
      </ul>
      <figcaption className="small muted">
        <span aria-hidden>↑ </span>The gate takes at most {limit} ft{lesson ? `: lesson ${lesson.lesson_id}` : ""}{back ? `, learned from ${back} turned-back truck${back === 1 ? "" : "s"}` : ""}.
      </figcaption>
    </figure>
  );
}
