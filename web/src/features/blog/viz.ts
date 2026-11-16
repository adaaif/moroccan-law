import { type KeyboardEvent, useEffect, useState } from 'react';
import { num, useWidth } from '@/topics/kit/viz/viz';

/** A whole number as the Bulletin prints it: «5.470», «5 470» in French. */
export const n = (v: number, lang: string) => num(v, lang);
/** A decimal with the comma both languages write: «0,80», «53,4». */
export const dec = (v: number, d = 1) => v.toFixed(d).replace('.', ',');

/** Redraws when the reader's theme changes: the phone's, or the one picked in the reading settings. */
export function useTheme(): number {
  const [tick, setTick] = useState(0);
  useEffect(() => {
    const media = window.matchMedia('(prefers-color-scheme: dark)');
    const bump = () => setTick((k) => k + 1);
    media.addEventListener('change', bump);
    const watch = new MutationObserver(bump);
    watch.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
    return () => { media.removeEventListener('change', bump); watch.disconnect(); };
  }, []);
  return tick;
}

/** Which of `count` equal columns a pointer is over, in the page's direction. */
export function columnAt(x: number, width: number, count: number, rtl: boolean): number {
  const i = Math.floor(((rtl ? width - x : x) / width) * count);
  return Math.max(0, Math.min(count - 1, i));
}

/** The arrows move along the columns in the reading direction: in Arabic, ← goes to a later year. */
export function stepFor(e: KeyboardEvent, rtl: boolean): number {
  if (e.key === 'ArrowLeft') return rtl ? 1 : -1;
  if (e.key === 'ArrowRight') return rtl ? -1 : 1;
  return 0;
}

/** The decades under seventy columns, the first and last years at the ends. */
export function decadeTicks(first: number, last: number, every = 10): Record<number, string> {
  const out: Record<number, string> = { 0: String(first), [last - first]: String(last) };
  for (let y = Math.ceil((first + 4) / every) * every; y <= last - 4; y += every) out[y - first] = String(y);
  return out;
}

/** The ticks that keep 52 px from each other, the first and last kept before the others. */
export function spaced(ticks: Record<number, string>, x: (i: number) => number): [string, string][] {
  const all = Object.entries(ticks).sort(([a], [b]) => +a - +b);
  const ends = [all[0], all[all.length - 1]].filter(Boolean);
  const kept: [string, string][] = [...ends];
  for (const t of all.slice(1, -1)) if (kept.every(([k]) => Math.abs(x(+k) - x(+t[0])) >= 52)) kept.push(t);
  return kept;
}

/** The month names as the reader's language writes them: «يناير … دجنبر» in Moroccan Arabic, «janvier …» in French. */
export function monthNames(lang: string, style: 'long' | 'short' = 'long'): string[] {
  const f = new Intl.DateTimeFormat(lang === 'fr' ? 'fr-MA' : 'ar-MA', { month: style, timeZone: 'UTC' });
  return Array.from({ length: 12 }, (_, m) => f.format(new Date(Date.UTC(2001, m, 15))));
}

export { useWidth };

/** The first period of independence (C3 of the posts-from-No.-1 review: periods by decade, a line at 1956): its index in a
 *  post's periods, -1 when the post starts later. */
export const since1956 = (periods: [number, number][]) => (periods[0]?.[0] < 1956 ? periods.findIndex(([a]) => a >= 1956) : -1);

/** Which of a row of period labels a phone can print without one touching the next: the first, the last and 1956
 *  always, others while two columns apart (`minor` hides the rest on a narrow screen). */
export function labelled(count: number, mark: number): Set<number> {
  const must = [0, mark, count - 1].filter((i) => i >= 0);
  const kept = new Set(must);
  let prev = -2;
  for (let i = 0; i < count; i += 1) {
    if (kept.has(i)) { prev = i; continue; }
    const ahead = Math.min(...must.filter((m) => m > i), Infinity);
    if (i - prev >= 2 && ahead - i >= 2) { kept.add(i); prev = i; }
  }
  return kept;
}

/** What a post's «who rose, who fell» compares (countries.py and cities.py `moves`): the mean of the first two periods
 *  against the mean of the last two, with the years each pair spans. A label prints these, never the first period and
 *  the last alone (Marrakech fell from 1913–1929 to 2010–2025, though 1913–1919 alone was below today). */
export function ends(s: number[]): [number, number] {
  const k = s.length;
  return k < 2 ? [s[0] ?? 0, s[0] ?? 0] : [(s[0] + s[1]) / 2, (s[k - 2] + s[k - 1]) / 2];
}
export function endSpans(periods: [number, number][]): [string, string] {
  const k = periods.length;
  return k < 2 ? ['', ''] : [`${periods[0][0]}–${periods[1][1]}`, `${periods[k - 2][0]}–${periods[k - 1][1]}`];
}
