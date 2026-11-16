import { useEffect, useState } from 'react';

/** Whether the screen is a desk's: the list and the open sheet sit side by side there. The answer changes once the
 *  width has settled: a passing flip (a window dragged across the line, a full-page capture) would otherwise move the
 *  open sheet from beside the list to the bottom and back, and lose what was being written in it. */
export function useWide(query = '(min-width: 1024px)') {
  const [wide, setWide] = useState(() => typeof window !== 'undefined' && window.matchMedia(query).matches);
  useEffect(() => {
    const m = window.matchMedia(query);
    let timer = 0;
    const on = () => {
      window.clearTimeout(timer);
      timer = window.setTimeout(() => setWide(m.matches), 200);
    };
    m.addEventListener('change', on);
    return () => {
      window.clearTimeout(timer);
      m.removeEventListener('change', on);
    };
  }, [query]);
  return wide;
}

/** What is typed in a list's search box, and what is asked of the server a moment after the typing stops. */
export function useSearch() {
  const [typed, setTyped] = useState('');
  const [q, setQ] = useState('');
  useEffect(() => {
    const timer = window.setTimeout(() => setQ(typed.trim()), 300);
    return () => window.clearTimeout(timer);
  }, [typed]);
  return { typed, setTyped, q };
}

export type Searched = ReturnType<typeof useSearch>;
