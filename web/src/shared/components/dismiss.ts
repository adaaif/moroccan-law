import { useEffect, useRef } from 'react';

let opened = 0;
const open = new Set<number>();

// A link followed from inside a sheet takes the sheet's entry (PX15 of the where-it-trips review): pushed on top of it,
// the page left a copy of the one under the sheet, and the second back press did nothing (the header's search, the
// printed page from an article's tools, a word's defining article).
if (typeof window !== 'undefined') {
  const push = window.history.pushState.bind(window.history);
  window.history.pushState = (data: { sheet?: number } | null, unused: string, url?: string | URL | null) => {
    const top = (window.history.state as { sheet?: number } | null)?.sheet;
    if (top !== undefined && open.has(top) && data?.sheet === undefined) window.history.replaceState(data, unused, url);
    else push(data, unused, url);
  };
}

/** What every sheet, drawer and dialog does when it opens (U5 of the Moroccan-design review): Escape closes it, the
 *  phone's back closes it and leaves the reader on the page (it adds a history entry of the same address, taken off
 *  again when it closes another way), and focus goes back where it was. */
const leaving = new Set<number>();

/** A move that replaces the address from inside an open sheet (the outline's jump on a phone): the sheet's entry is
 *  taken off first, so the move leaves no extra back step, as on a desk (PX15). `then` runs once it is off. */
export function leaveSheet(then: () => void) {
  const top = (window.history.state as { sheet?: number } | null)?.sheet;
  if (top === undefined || !open.has(top)) { then(); return; }
  leaving.add(top);
  window.addEventListener('popstate', () => window.setTimeout(then, 0), { once: true });
  window.history.back();
}

export function useDismiss(onClose: () => void, back = true) {
  const close = useRef(onClose);
  close.current = onClose;
  useEffect(() => {
    const id = ++opened;
    const before = document.activeElement as HTMLElement | null;
    const key = (e: KeyboardEvent) => { if (e.key === 'Escape') close.current(); };
    document.addEventListener('keydown', key);
    if (!back) return () => document.removeEventListener('keydown', key);
    const state = window.history.state as { sheet?: number } | null;
    // An entry whose sheet has just closed (React's second mount while developing, or a sheet opened again at once)
    // is taken over rather than stacked.
    const stale = state?.sheet !== undefined && !open.has(state.sheet);
    window.history[stale ? 'replaceState' : 'pushState']({ ...state, sheet: id }, '');
    open.add(id);
    const pop = () => { if ((window.history.state as { sheet?: number } | null)?.sheet !== id) close.current(); };
    window.addEventListener('popstate', pop);
    return () => {
      open.delete(id);
      window.removeEventListener('popstate', pop);
      document.removeEventListener('keydown', key);
      before?.focus?.({ preventScroll: true });
      // Closed by its button, a tap outside or Escape: its entry goes. Closed by a link inside it: the link's page is
      // the entry now, and stays. (Later, so a remount that opens it again keeps its own entry.)
      window.setTimeout(() => {
        if ((window.history.state as { sheet?: number } | null)?.sheet === id && !leaving.delete(id)) window.history.back();
      }, 0);
    };
  }, [back]);
}
