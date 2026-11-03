import { useSettings } from "../lib/ctx";
import { MODEL_LABEL, type ModelKey } from "../lib/api";

// The model live runs use (owner, Nov 3). A model this host can't run is listed but disabled, with the reason as its
// title; recorded runs keep the model they were recorded on, and every run, draft and lesson says which one.
export function ModelPicker() {
  const { session, model, setModel } = useSettings();
  if (!session) return null;
  const rows = (Object.keys(MODEL_LABEL) as ModelKey[]).map((k) => ({ k, m: session.models[MODEL_LABEL[k]] }));
  if (!rows.some((r) => r.m?.available)) return null;      // no model can run here: replay only, nothing to choose
  return (
    <label className="model-pick">
      <span className="small muted">Model</span>
      <select aria-label="Model for live runs" value={model} onChange={(e) => setModel(e.target.value as ModelKey)}>
        {rows.map(({ k, m }) => (
          <option key={k} value={k} disabled={!m?.available} title={m?.reason ?? undefined}>
            {MODEL_LABEL[k]}{m?.available ? "" : " (not on this host)"}
          </option>
        ))}
      </select>
    </label>
  );
}
