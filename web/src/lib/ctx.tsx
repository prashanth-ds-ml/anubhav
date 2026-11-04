import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, MODEL_LABEL, type ModelKey } from "./api";
import { BUNDLED } from "./fixtures";
import type { CompanyRow, Session, Suggestion } from "../types";

export interface Settings {
  company: string; setCompany: (c: string) => void;
  useLessons: boolean; setUseLessons: (v: boolean) => void;
  companies: CompanyRow[]; session: Session | null;
  /** Every saved request, with whether a recording exists with lessons on and with lessons off. */
  requests: { label: string; request: string; on: boolean; off: boolean }[];
  /** False until the saved requests have arrived: matching a typed request before then would wrongly find nothing. */
  ready: boolean;
  /** The model live runs use (header picker), and its name. */
  model: ModelKey; setModel: (m: ModelKey) => void; modelLabel: string;
  /** The chosen model can run here now, and why not when it can't. */
  live: { ok: boolean; reason: string | null };
  refreshSession: () => void;
  /** Bumped when something outside a tab changes this visitor's data (a scenario step retiring a lesson, say). */
  dataVersion: number; bumpData: () => void;
}

const Ctx = createContext<Settings | null>(null);
export const useSettings = () => useContext(Ctx)!;

export function SettingsProvider({ children }: { children: ReactNode }) {
  const [company, setCompany] = useState("T01");
  const [useLessons, setUseLessons] = useState(true);
  const [companies, setCompanies] = useState<CompanyRow[]>([]);
  const [session, setSession] = useState<Session | null>(null);
  const [onList, setOn] = useState<Suggestion[]>([]);
  const [offList, setOff] = useState<Suggestion[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [dataVersion, setDataVersion] = useState(0);
  const [picked, setPicked] = useState<ModelKey | null>(() => {
    try { const v = sessionStorage.getItem("anubhav-model"); return v === "spark" || v === "open" ? v : null; } catch { return null; }
  });
  // Until the visitor picks one: the host's default if it can run here, else any model that can, else the default.
  const model: ModelKey = useMemo(() => {
    if (picked) return picked;
    const ms = Object.values(session?.models ?? {});
    const def = (session?.default_model ?? "spark") as ModelKey;
    if (ms.some((m) => m.key === def && m.available)) return def;
    return (ms.find((m) => m.available)?.key as ModelKey | undefined) ?? def;
  }, [picked, session]);
  const setModel = (m: ModelKey) => { setPicked(m); try { sessionStorage.setItem("anubhav-model", m); } catch { /* kept for this page */ } };

  useEffect(() => { api.companies().then(setCompanies); api.session().then(setSession); }, []);
  useEffect(() => {
    let live = true;
    setLoaded(false);
    Promise.all([api.suggestions(company, true), api.suggestions(company, false)]).then(([a, b]) => { if (live) { setOn(a); setOff(b); setLoaded(true); } });
    return () => { live = false; };
  }, [company]);

  const requests = useMemo(() => {
    if (loaded && onList.length === 0 && offList.length === 0) {
      // The server cannot be reached: offer the bundled examples, which play without it.
      const names: Record<string, string> = { "Warangal load ki bandi pettu.": "Ambiguous", "Hanamkonda lo ae weekday lo manam ekkuva deliveries chestham?": "New tool" };
      const seen = new Set<string>();
      return BUNDLED.filter((b) => !seen.has(b.request) && !!seen.add(b.request))
        .map((b, i) => ({ label: names[b.request] ?? (i === 0 ? "Roman Telugu" : b.request), request: b.request, on: true, off: true }));
    }
    const off = new Map(offList.map((s) => [s.label, s.has_replay]));
    return onList.map((s) => ({ label: s.label, request: s.request, on: s.has_replay, off: off.get(s.label) ?? false }));
  }, [loaded, onList, offList]);

  const live = useMemo(() => {
    const m = session?.models?.[MODEL_LABEL[model]];
    if (!m) return { ok: false, reason: "Live mode is off here." };
    if (!m.available) return { ok: false, reason: m.reason };
    if (session!.live_runs_left <= 0) return { ok: false, reason: "This visit has used its live runs." };
    return { ok: true, reason: null };
  }, [session, model]);
  const refreshSession = () => { api.session().then(setSession); };
  const bumpData = () => setDataVersion((v) => v + 1);

  const value = useMemo(() => ({ company, setCompany, useLessons, setUseLessons, companies, session, requests, ready: loaded, live, refreshSession, dataVersion, bumpData,
    model, setModel, modelLabel: MODEL_LABEL[model] }),
    [company, useLessons, companies, session, requests, loaded, live, dataVersion, model]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}
