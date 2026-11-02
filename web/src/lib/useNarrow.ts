import { useEffect, useState } from "react";

/** True on phone-width screens (the same 860 px breakpoint the CSS uses). */
export function useNarrow(px = 860) {
  const q = `(max-width: ${px}px)`;
  const [narrow, setNarrow] = useState(() => matchMedia(q).matches);
  useEffect(() => {
    const m = matchMedia(q);
    const on = () => setNarrow(m.matches);
    m.addEventListener("change", on);
    return () => m.removeEventListener("change", on);
  }, [q]);
  return narrow;
}
