/**
 * The price of a pack of Marquise, order by order, and what it cost in work at the minimum wage (the blog's fourteenth
 * post): pure, so the chart, the sentences, the instrument and the tests read the same numbers. Days are «YYYY-MM-DD».
 */

export type Price = { date: string; price: number; unit: 'franc' | 'dirham'; name: string; company?: number; palestine?: number };
export type Wage = { from: string; hourly: number };

/** A price in dirhams: the francs of 1956–1960 at a hundred to the dirham (its value when it was created in 1959). */
export const dirhams = (p: Price) => (p.unit === 'franc' ? p.price / 100 : p.price);

/** The value in force on a day in a list of steps sorted by their first day, or null before the first. */
function inForce<T extends { from: string }>(steps: T[], day: string): T | null {
  let found: T | null = null;
  for (const s of steps) { if (s.from <= day) found = s; else break; }
  return found;
}

export function priceOn(prices: Price[], day: string, gap?: { from: string; to: string }): Price | null {
  if (gap && day > gap.from && day < gap.to) return null;
  return inForce(prices.map((p) => ({ ...p, from: p.date })), day);
}

export const wageOn = (wage: Wage[], day: string) => inForce(wage, day)?.hourly ?? null;

/** `gap`: the stretch after an order where the Bulletin printed no other until `to` (drawn dashed to the next price). */
export type Segment = { from: string; to: string; dh: number | null; hourly: number | null; hours: number | null; price: Price | null; gap?: boolean };

/** The stretches where neither the price nor the wage changed, from the first price to `end`: each with the price in
 *  dirhams and in hours of work at the minimum wage (null where the Bulletin printed no price, or no wage yet). */
export function segments(prices: Price[], wage: Wage[], end: string, gap?: { from: string; to: string }): Segment[] {
  const marks = [...new Set([...prices.map((p) => p.date), ...wage.map((w) => w.from).filter((d) => d > prices[0].date), ...(gap ? [gap.from, gap.to] : [])])]
    .filter((d) => d <= end).sort();
  return marks.map((from, i) => {
    const to = marks[i + 1] ?? end;
    const p = priceOn(prices, from, gap);
    const dh = p ? dirhams(p) : null;
    const hourly = wageOn(wage, from);
    return { from, to, dh, hourly, hours: dh !== null && hourly ? dh / hourly : null, price: p, ...(gap && from === gap.from ? { gap: true } : {}) };
  });
}

/** «1 h 44»: hours as hours and whole minutes. */
export function hm(hours: number): { h: number; m: number } {
  let h = Math.floor(hours), m = Math.round((hours - h) * 60);
  if (m === 60) { h += 1; m = 0; }
  return { h, m };
}

/** A year as a number on the chart's axis: its day's share of the year. */
export const yearOf = (day: string) => {
  const [y, m, d] = day.split('-').map(Number);
  return y + ((m - 1) * 30.44 + (d - 1)) / 365.25;
};

/** What the reader drew against what the orders printed: the price in force on 1 July of each year the reader drew and
 *  the Bulletin printed one. */
export type Miss = { year: number; guess: number; truth: number };
export function compare(guess: (number | null)[], first: number, prices: Price[], gap?: { from: string; to: string }): Miss[] {
  const out: Miss[] = [];
  guess.forEach((g, i) => {
    if (g === null) return;
    const p = priceOn(prices, `${first + i}-07-01`, gap);
    if (p) out.push({ year: first + i, guess: g, truth: dirhams(p) });
  });
  return out;
}

/** A pack or more a day for a month (a twelfth of a year's days), in dirhams and in hours at the minimum wage. */
export function month(packs: number, dh: number, hourly: number) {
  const cost = packs * dh * (365.25 / 12);
  return { cost, hours: cost / hourly };
}
