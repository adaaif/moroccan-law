import { useEffect, useState } from 'react';

/** The article under the reader's eye as the page scrolls: the one that crosses a line a third of the way down. The
 *  first article touching the upper part of the screen was the one whose last lines were leaving it, so the bar said
 *  «المادة 52» above article 53 (RD21 of the readers review, 9 Nov 2026). */
export function useCurrentArticle(eids: string[]): string {
  const [current, setCurrent] = useState(eids[0] ?? '');
  useEffect(() => {
    if (!eids.length) return;
    const seen = new Map<string, boolean>();
    const io = new IntersectionObserver(
      (entries) => {
        for (const e of entries) seen.set(e.target.id, e.isIntersecting);
        const first = eids.find((id) => seen.get(id));
        if (first) setCurrent(first);
      },
      { rootMargin: '-34% 0px -65% 0px' },
    );
    for (const id of eids) {
      const el = document.getElementById(id);
      if (el) io.observe(el);
    }
    return () => io.disconnect();
  }, [eids]);
  return current;
}
