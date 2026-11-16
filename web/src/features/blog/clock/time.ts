/**
 * Morocco's legal time as the Bulletin's texts set it (the blog's thirteenth post): pure, so the grid, the finder, the
 * counts and the tests read the same answer. An instant is local legal time written «YYYY-MM-DDTHH:MM», as the texts word
 * it («عند حلول الساعة الثانية صباحا من يوم الأحد 20 سبتمبر 2026»): strings of one shape compare in time order.
 */

export type Move = { at: string; to: 0 | 60; text: string; rule?: boolean };
export type Span = { from: string; to: string };
export type Clock = { legal_from: string; moves: Move[]; unknown: Span[] };
/** none: before the legal time (26 October 1913); unknown: ahead, then back on a day no text found tells. */
export type State = 'none' | 'gmt' | 'ahead' | 'unknown';

export type Moment = {
  state: State;
  /** The move that set the clock as it then was (null: the 1913 dahir's Greenwich, before any move). */
  since: Move | null;
  /** The next move after it (null: none yet). */
  until: Move | null;
};

/** The legal time at an instant. */
export function at(c: Clock, instant: string): Moment {
  if (instant < `${c.legal_from}T00:00`) return { state: 'none', since: null, until: c.moves[0] ?? null };
  // The last move at or before the instant: a binary search over the moves, in time order.
  let lo = 0, hi = c.moves.length;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (c.moves[mid].at <= instant) lo = mid + 1; else hi = mid;
  }
  const since = lo > 0 ? c.moves[lo - 1] : null;
  const until = c.moves[lo] ?? null;
  if (c.unknown.some((u) => instant >= u.from && instant < u.to)) return { state: 'unknown', since, until };
  return { state: since?.to === 60 ? 'ahead' : 'gmt', since, until };
}

const pad = (n: number) => String(n).padStart(2, '0');
export const iso = (y: number, m: number, d: number) => `${y}-${pad(m)}-${pad(d)}`;
export const isLeap = (y: number) => (y % 4 === 0 && y % 100 !== 0) || y % 400 === 0;
const MONTH_DAYS = [31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
/** The slot of each month's first day in a 366-day row: every row keeps a 29 February, so the months line up. */
export const MONTH_START = MONTH_DAYS.reduce<number[]>((acc, d, i) => [...acc, (acc[i] ?? 0) + d], [0]).slice(0, 12);

/** The day a slot of a year's row stands for, or null for 29 February in a common year. */
export function slotDay(year: number, slot: number): string | null {
  let m = 0;
  while (m < 11 && slot >= MONTH_START[m + 1]) m += 1;
  const d = slot - MONTH_START[m] + 1;
  if (m === 1 && d === 29 && !isLeap(year)) return null;
  return iso(year, m + 1, d);
}

export function slotOf(day: string): number {
  const [, m, d] = day.split('-').map(Number);
  return MONTH_START[m - 1] + d - 1;
}

/** Codes a row is drawn from. */
export const CODE: Record<State, number> = { none: 0, gmt: 1, ahead: 2, unknown: 3 };
export const NO_DAY = 255;

/** A year's 366 slots, each day read at noon (3 June 1967, moved at noon, counts as ahead). */
export function row(c: Clock, year: number): Uint8Array {
  const out = new Uint8Array(366);
  for (let s = 0; s < 366; s += 1) {
    const day = slotDay(year, s);
    out[s] = day ? CODE[at(c, `${day}T12:00`).state] : NO_DAY;
  }
  return out;
}

const DAY_MS = 86_400_000;
const ms = (instant: string) => Date.parse(`${instant.length === 10 ? `${instant}T00:00` : instant}:00Z`);
/** Whole days from one day (or instant) to another. */
export const daysBetween = (a: string, b: string) => Math.round((ms(b.slice(0, 10)) - ms(a.slice(0, 10))) / DAY_MS);

export type Stretch = { from: Move | null; to: Move | null; state: 'gmt' | 'ahead'; days: number };

/** The clock's stretches from the legal time to `end`: each a state and its length in days (the unknown left out). */
export function stretches(c: Clock, end: string): Stretch[] {
  const out: Stretch[] = [];
  const marks: (Move | null)[] = [null, ...c.moves];
  for (let i = 0; i < marks.length; i += 1) {
    const from = marks[i], to = c.moves[i] ?? null;
    const start = from?.at ?? `${c.legal_from}T00:00`;
    const stop = to?.at ?? `${end}T00:00`;
    if (c.unknown.some((u) => start >= u.from && start < u.to)) continue;
    out.push({ from, to, state: from?.to === 60 ? 'ahead' : 'gmt', days: (ms(stop) - ms(start)) / DAY_MS });
  }
  return out;
}

export type Summary = {
  moves: number;
  texts: number;
  /** Days the legal time stood an hour ahead, unknown windows left out. */
  aheadDays: number;
  longestAhead: Stretch;
  shortestAhead: Stretch;
  longestGmt: Stretch;
};

export function summary(c: Clock, textCount: number, end: string): Summary {
  const s = stretches(c, end);
  const ahead = s.filter((x) => x.state === 'ahead' && x.to);
  const gmt = s.filter((x) => x.state === 'gmt' && x.to);
  const by = (f: (a: Stretch, b: Stretch) => number) => (xs: Stretch[]) => [...xs].sort(f)[0];
  return {
    moves: c.moves.length,
    texts: textCount,
    aheadDays: Math.round(s.filter((x) => x.state === 'ahead').reduce((t, x) => t + x.days, 0)),
    longestAhead: by((a, b) => b.days - a.days)(ahead),
    shortestAhead: by((a, b) => a.days - b.days)(ahead),
    longestGmt: by((a, b) => b.days - a.days)(gmt),
  };
}

export type Printed = { published: string; also?: { published: string } };
export type Notice = { move: Move; printed: string; days: number };

/** How many days before a move the Bulletin first printed the text that names it (negative: after the clock had
 *  moved). The moves of a yearly rule are left out: their text was printed in an earlier year. */
export function notices(c: Clock, texts: Record<string, Printed>): Notice[] {
  return c.moves.filter((m) => !m.rule && texts[m.text]).map((m) => {
    const t = texts[m.text];
    const printed = t.also && t.also.published < t.published ? t.also.published : t.published;
    return { move: m, printed, days: daysBetween(printed, m.at) };
  });
}

export type RamadanYear = { year: number; first: string; back: Move; before: number; ahead?: Move; after?: number };

/** The years the clock went back in the week before the first day of Ramadan as the Bulletin's own Hijri dates set it
 *  (no text on the clock names Ramadan), with the move that set it ahead again after the first of Shawwal. */
export function beforeRamadan(c: Clock, hijri: { ramadan: Record<string, string>; shawwal: Record<string, string> }, days = 7): RamadanYear[] {
  const out: RamadanYear[] = [];
  for (const [y, first] of Object.entries(hijri.ramadan)) {
    const back = c.moves.find((m) => m.to === 0 && daysBetween(m.at, first) >= 0 && daysBetween(m.at, first) <= days);
    if (!back) continue;
    const shawwal = hijri.shawwal[y];
    const ahead = shawwal ? c.moves.find((m) => m.to === 60 && m.at > back.at && daysBetween(shawwal, m.at) >= 0 && daysBetween(shawwal, m.at) <= days) : undefined;
    out.push({ year: Number(y), first, back, before: daysBetween(back.at, first), ahead, after: ahead && shawwal ? daysBetween(shawwal, ahead.at) : undefined });
  }
  return out.sort((a, b) => a.year - b.year);
}

/** The longest run of consecutive years in a list. */
export function longestRun(years: number[]): [number, number] {
  let best: [number, number] = [years[0], years[0]], start = years[0];
  for (let i = 1; i <= years.length; i += 1) {
    if (years[i] === years[i - 1] + 1) continue;
    if (years[i - 1] - start > best[1] - best[0]) best = [start, years[i - 1]];
    start = years[i];
  }
  return best;
}

export type Hands = { hour: number; minute: number; second?: number };

/** The hands' angles for a time of day. */
export function hands(h: number, m: number, s = 0): Hands {
  return { hour: ((h % 12) + m / 60 + s / 3600) * 30, minute: (m + s / 60) * 6, second: s * 6 };
}
