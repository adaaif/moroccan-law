import { useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { noteUse } from '../use';

/** A tool's inputs kept in its address (F6 of the road tools review): a shared link, or a door from another tool,
 *  opens the same answer. Only the keys given here, each a short string; anything else in the query is left alone.
 *  The inputs are held in the component too, so a tap reads the value the last tap set (E13 of the work-counted review: ten
 *  quick taps on a stepper counted eight while the address caught up); the address follows, and a change to it from
 *  outside (the back button, a link) is read back. */
export function useToolState<T extends Record<string, string>>(defaults: T, pin: (keyof T)[] = []): [T, (patch: Partial<T>) => void] {
  const [params, setParams] = useSearchParams();
  // An input whose default moves stays in the address even at its default (PX12 of the where-it-trips review): a date
  // (today, a day and hour), or one taken from the reader's answer (`pin`). Left out, a link kept or shared reopened
  // another answer: an appeal «notified today» three days later, a shop receipt as an online purchase.
  const pinned = (k: keyof T) => pin.includes(k) || /^\d{4}-\d{2}-\d{2}/.test(defaults[k]);
  const read = (p: URLSearchParams) => Object.fromEntries(Object.entries(defaults).map(([k, v]) => [k, p.get(k) ?? v])) as T;
  const [state, setState] = useState<T>(() => read(params));
  // The inputs as last set, so two changes in one handler both count.
  const latest = useRef(state);
  // The addresses this hook wrote that the router has not reported yet, oldest first.
  const pending = useRef<string[]>([]);
  const query = params.toString();
  useEffect(() => {
    // Our own writes come back here once the router has them, an earlier one possibly after a later was made: those
    // are dropped; only another change to the address (the back button, a link) is read back.
    const mine = pending.current.indexOf(query);
    if (mine >= 0) { pending.current = pending.current.slice(mine + 1); return; }
    pending.current = [];
    latest.current = read(new URLSearchParams(query));
    setState(latest.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query]);
  // Written once at the start, so the address carries them before any input is touched.
  useEffect(() => {
    const url = new URLSearchParams(params);
    const missing = (Object.keys(defaults) as (keyof T & string)[]).filter((k) => pinned(k) && !url.has(k) && state[k]);
    if (!missing.length) return;
    for (const k of missing) url.set(k, state[k]);
    pending.current.push(url.toString());
    setParams(url, { replace: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const set = (patch: Partial<T>) => {
    // Only the reader changes a tool's inputs (no tool sets them from an effect): its first answer, for the measures.
    noteUse('answered');
    const next = { ...latest.current, ...patch } as T;
    latest.current = next;
    setState(next);
    const url = new URLSearchParams(params);
    for (const [k, v] of Object.entries(next)) {
      if (v === undefined || (v === defaults[k] && !pinned(k))) url.delete(k);
      else url.set(k, String(v));
    }
    pending.current.push(url.toString());
    setParams(url, { replace: true });
  };
  return [state, set];
}

/** A link to another tool with its inputs set: `toolLink('/topics/road/tools/points', {o: 'speed20'})`. */
export const toolLink = (path: string, state: Record<string, string>) => `${path}?${new URLSearchParams(state)}`;
