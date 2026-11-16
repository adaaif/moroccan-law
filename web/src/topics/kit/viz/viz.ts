import { useEffect, useState } from 'react';

/** The topic's charts (the bill-story review, Y6, readable by
 *  Moroccans): drawn at the width they are given, never shrunk, so no word falls under 14 px; in the page's direction
 *  (in Arabic the salary grows to the left); figures as the Bulletin prints them. */
export function useWidth<T extends HTMLElement>(fallback = 640): [(el: T | null) => void, number] {
  // A callback ref: the element measured is whichever is mounted now (a placeholder gives way to the chart).
  const [el, setEl] = useState<T | null>(null);
  const [width, setWidth] = useState(fallback);
  useEffect(() => {
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setWidth(Math.round(e.contentRect.width) || fallback));
    ro.observe(el);
    setWidth(Math.round(el.getBoundingClientRect().width) || fallback);
    return () => ro.disconnect();
  }, [el, fallback]);
  return [setEl, width];
}

/** A figure as the reader's language writes it: «60.000» in Arabic (the Bulletin's), «60 000» in French. */
export function num(n: number, lang: string): string {
  const s = Math.round(n).toLocaleString('de-DE');
  return lang === 'fr' ? s.replace(/\./g, ' ') : s;
}

/** The colours every chart shares (Y6): today's law in grey, the bill in the topic's colour, the reader in ink. */
export const INK = { law: 'var(--color-ink-soft)', bill: 'var(--t)', reader: 'var(--color-ink)', grid: 'var(--color-rule)', soft: 'var(--color-ink-soft)' };

/** A linear scale over [d0, d1] to [r0, r1]. */
export const scale = (d0: number, d1: number, r0: number, r1: number) => (v: number) => r0 + ((v - d0) / (d1 - d0)) * (r1 - r0);

/** Round ticks over a range, about `count` of them. */
export function ticks(max: number, count: number): number[] {
  const raw = max / count, mag = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw) ?? raw;
  const out: number[] = [];
  for (let v = 0; v <= max + 1e-9; v += step) out.push(Math.round(v));
  return out;
}
