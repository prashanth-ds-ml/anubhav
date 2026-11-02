import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api } from "./api";
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
  /** Muse Spark 1.3 can run here now, and why not when it can't. */
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
    const m = session?.models["Muse Spark 1.3"];
    if (!m) return { ok: false, reason: "Live mode is off here." };
    if (!m.available) return { ok: false, reason: m.reason };
    if (session!.live_runs_left <= 0) return { ok: false, reason: "This visit has used its live runs." };
    return { ok: true, reason: null };
  }, [session]);
  const refreshSession = () => { api.session().then(setSession); };
  const bumpData = () => setDataVersion((v) => v + 1);

  const value = useMemo(() => ({ company, setCompany, useLessons, setUseLessons, companies, session, requests, ready: loaded, live, refreshSession, dataVersion, bumpData }),
    [company, useLessons, companies, session, requests, loaded, live, dataVersion]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}
