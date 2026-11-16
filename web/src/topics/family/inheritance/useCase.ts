import { useCallback, useEffect, useRef, useState } from 'react';
import { EMPTY, decode, encode, older, type Case } from './case';

/** The family's case, kept in the address after «#» (IR16): a reload, the way back from an article and a shared link
 *  all open the same family, and nothing of it is sent, since a browser keeps that part to itself. The case is held in
 *  the component too, so a tap reads what the last tap set. `stale`: the link was made by an older engine (IR12). */
export function useCase(start = '') {
  const read = () => (typeof window === 'undefined' ? null : decode(window.location.hash));
  // An address that names a family (IR28) opens on it, unless a case came after «#».
  const [first] = useState(() => read() ?? (start ? decode(start) : null));
  const [c, setC] = useState<Case>(first?.case ?? EMPTY);
  const [stale, setStale] = useState(Boolean(first && older(first.version)));
  const latest = useRef(c);
  const write = (next: Case) => {
    latest.current = next;
    setC(next);
    const code = encode(next);
    const url = window.location.pathname + window.location.search + (code ? `#${code}` : '');
    // The router's own state stays as it is: only the part after «#» changes, without a step in the history.
    window.history.replaceState(window.history.state, '', url);
  };
  const set = useCallback((patch: Partial<Case>) => { setStale(false); write({ ...latest.current, ...patch }); }, []);
  const reset = useCallback(() => { setStale(false); write(EMPTY); }, []);
  /** Opens a kept family. */
  const load = useCallback((code: string) => {
    const d = decode(code);
    if (d) { setStale(older(d.version)); write(d.case); }
  }, []);
  useEffect(() => {
    // A link pasted in the bar, or the back button between two families.
    const on = () => {
      const d = read();
      if (!d || encode(d.case) === encode(latest.current)) return;
      latest.current = d.case;
      setC(d.case);
      setStale(older(d.version));
    };
    window.addEventListener('hashchange', on);
    return () => window.removeEventListener('hashchange', on);
  }, []);
  return { c, set, reset, load, code: encode(c), stale };
}
