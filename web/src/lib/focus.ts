import { useEffect, useRef } from "react";

// A scenario step can point at something in a tab ("the 22 ft lesson", "the tool candidate"). The tab may not be open
// yet, so the request waits here until the matching element has its data, then scrolls to it and highlights it briefly.
let pending: string | null = null;
const EVENT = "anubhav:focus";

/** The target a step asked for that no element has answered yet (a page can use it to pick what to show). */
export const peekFocus = () => pending;
export const FOCUS_EVENT = "anubhav:focus";

export function focusOn(target: string) {
  pending = target;
  window.dispatchEvent(new CustomEvent(EVENT, { detail: target }));
}

/** Attach to the element that answers to `target`; `ready` is true once its content is drawn. */
export function useFocusTarget<T extends HTMLElement>(target: string | null, ready: boolean) {
  const ref = useRef<T>(null);
  useEffect(() => {
    const go = () => {
      if (!target || pending !== target || !ready || !ref.current) return;
      pending = null;
      const el = ref.current;
      const calm = matchMedia("(prefers-reduced-motion: reduce)").matches;
      el.scrollIntoView({ block: "center", behavior: calm ? "auto" : "smooth" });
      el.classList.remove("flash");
      void el.offsetWidth; // restart the highlight
      el.classList.add("flash");
      window.setTimeout(() => el.classList.remove("flash"), 2600);
    };
    go();
    window.addEventListener(EVENT, go);
    return () => window.removeEventListener(EVENT, go);
  }, [target, ready]);
  return ref;
}
