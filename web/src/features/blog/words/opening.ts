import type { WordCount } from '../blog.api';

/** Where a word's story starts, for the grid's hover: its first mention, else the first text on the subject; for a word
 *  already there in the first year, nothing (its first counted text says only where the reading starts). */
export function opening(w: WordCount, from: number): { date: string; path: string; kind: 'first' | 'subject' } | null {
  const stop = w.stops?.find((s) => s.kind === 'first') ?? w.stops?.find((s) => s.kind === 'subject');
  if (stop) return { date: stop.date, path: stop.path, kind: stop.kind === 'first' ? 'first' : 'subject' };
  return w.first && Number(w.first.date.slice(0, 4)) > from ? { date: w.first.date, path: w.first.path, kind: 'first' } : null;
}
