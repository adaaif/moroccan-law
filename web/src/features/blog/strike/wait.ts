/**
 * The right to strike (the blog's eighteenth post), pure: days and spans between two days, the year of a day on a line of
 * years, and the words a constitution changed from the one before it. Days are «YYYY-MM-DD».
 */

const t = (d: string) => Date.parse(`${d}T00:00:00Z`);
export const days = (a: string, b: string) => Math.round((t(b) - t(a)) / 86_400_000);

/** Whole years, months and days from one day to another, as a calendar counts them. */
export function span(a: string, b: string): { years: number; months: number; days: number } {
  const [y1, m1, d1] = a.split('-').map(Number), [y2, m2, d2] = b.split('-').map(Number);
  let years = y2 - y1, months = m2 - m1, dd = d2 - d1;
  if (dd < 0) { months -= 1; dd += new Date(Date.UTC(y2, m2 - 1, 0)).getUTCDate(); }
  if (months < 0) { years -= 1; months += 12; }
  return { years, months, days: dd };
}

/** A day as a number on a line of years: its share of the year. */
export const yearOf = (d: string) => { const [y, m, dd] = d.split('-').map(Number); return y + ((m - 1) * 30.44 + (dd - 1)) / 365.25; };

/** A word as the comparison reads it: one alif for its hamzas, one ya, no tatweel, no full stop. */
export const fold = (w: string) => w.replace(/[إأآ]/g, 'ا').replace(/ى/g, 'ي').replace(/ـ/g, '').replace(/[.،,]/g, '');

/** The words of `now`, each marked when it is not among the words it shares, in order, with `before` (a longest common
 *  run of words). The first constitution has nothing before it: none of its words is marked. */
export function changed(before: string | null, now: string): { word: string; changed: boolean }[] {
  const b = before ? before.split(' ').map(fold) : [], n = now.split(' ');
  const f = n.map(fold);
  if (!before) return n.map((word) => ({ word, changed: false }));
  const L = Array.from({ length: b.length + 1 }, () => new Array<number>(f.length + 1).fill(0));
  for (let i = b.length - 1; i >= 0; i--) for (let j = f.length - 1; j >= 0; j--) L[i][j] = b[i] === f[j] ? L[i + 1][j + 1] + 1 : Math.max(L[i + 1][j], L[i][j + 1]);
  const kept = new Set<number>();
  for (let i = 0, j = 0; i < b.length && j < f.length;) {
    if (b[i] === f[j]) { kept.add(j); i++; j++; } else if (L[i + 1][j] >= L[i][j + 1]) i++; else j++;
  }
  return n.map((word, j) => ({ word, changed: !kept.has(j) }));
}
