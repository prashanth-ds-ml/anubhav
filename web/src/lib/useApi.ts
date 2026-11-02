import { useEffect, useState } from "react";

/** Load once; `loading` drives the skeleton, `data` is null until the first answer. With `keep`, a reload keeps the
 * last answer on screen until the new one arrives, so a panel doesn't collapse and lose its scroll after an action. */
export function useApi<T>(load: () => Promise<T>, deps: unknown[] = [], opts: { keep?: boolean } = {}) {
  const [data, setData] = useState<T | null>(null);
  useEffect(() => {
    let live = true;
    if (!opts.keep) setData(null);
    load().then((d) => live && setData(d));
    return () => { live = false; };
  }, deps); // eslint-disable-line react-hooks/exhaustive-deps
  return { data, loading: data === null };
}
