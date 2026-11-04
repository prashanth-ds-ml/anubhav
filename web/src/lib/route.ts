import { useEffect, useState } from "react";

// Every main tab, and every panel of the Dispatch Desk, has an address, so a link can open it directly.
// #learning, #runs … open a main tab; #plans, #ledger … open the Desk on that panel (the older single-level addresses).
// Anything after a "/" is the item inside the tab (#learning/L-T01-002), kept for the page to read.
export const MAIN = ["desk", "learning", "tools", "agents", "runs", "data", "proof"] as const;
export const DESK = ["orders", "plans", "fleet", "company", "ledger"] as const;
export type Main = (typeof MAIN)[number];
export type Desk = (typeof DESK)[number];

export interface Route { main: Main; desk: Desk; item: string | null }

export function parse(hash: string, lastDesk: Desk = "orders"): Route {
  const [head, ...rest] = hash.replace(/^#/, "").split("/");
  const item = rest.length ? rest.join("/") : null;
  if ((MAIN as readonly string[]).includes(head)) return { main: head as Main, desk: lastDesk, item };
  if ((DESK as readonly string[]).includes(head)) return { main: "desk", desk: head as Desk, item };
  return { main: "desk", desk: "orders", item: null };
}

/** The current address, followed as it changes (links, the back button, scenario steps). */
export function useRoute() {
  const [route, setRoute] = useState<Route>(() => parse(window.location.hash));
  useEffect(() => {
    const on = () => setRoute((r) => parse(window.location.hash, r.desk));
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  return route;
}

/** Go to a main tab or a Desk panel. Replaces the address, so the back button isn't flooded by tab clicks. */
export function go(slug: string) {
  if (window.location.hash === `#${slug}`) return;
  window.history.replaceState(null, "", `#${slug}`);
  window.dispatchEvent(new HashChangeEvent("hashchange"));
}
