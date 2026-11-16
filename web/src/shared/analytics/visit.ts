import type { Props } from './measures';

/** Readers who come back, from one date kept on the phone (the analytics review's choice of 15 Nov 2026):
 *  the Moroccan day this device last opened the site, and nothing else. A visit's first page says how long ago that
 *  was and which periods it is the device's first in; the server counts those, and no row says which phone it was.
 *  Days are YYYY-MM-DD in Morocco (shared/services/today.ts), compared as calendar days; pure, with no import
 *  (tests/measure.visit.test.ts). */

type Shown = Props['page.shown'];
export type Back = NonNullable<Shown['back']>;
export type Fresh = NonNullable<Shown['fresh']>;

const DAY = /^\d{4}-\d{2}-\d{2}$/;

/** A calendar day as a count of days since 1970, for differences. */
function number(day: string): number {
  const [y, m, d] = day.split('-').map(Number);
  return Date.UTC(y, m - 1, d) / 86_400_000;
}

/** How long since the stored day: 'first' when the phone kept none, then today, a day, a week (2–7 days), a month
 *  (8–30), more; 'unknown' for a stored day after today (the phone's clock was moved back). */
export function backOf(stored: string | null, today: string): Back {
  if (!stored || !DAY.test(stored)) return 'first';
  const days = number(today) - number(stored);
  if (days < 0) return 'unknown';
  return days === 0 ? 'today' : days === 1 ? 'day' : days <= 7 ? 'week' : days <= 30 ? 'month' : 'more';
}

/** The periods this visit is the phone's first in: d(ay), w(eek: the stored day is before this week's Monday),
 *  m(onth: before the 1st of this month); 'none' on a day the phone already came. */
export function freshOf(stored: string | null, today: string): Fresh {
  if (!stored || !DAY.test(stored)) return 'dwm';
  const was = number(stored);
  const now = number(today);
  if (was >= now) return 'none';
  // 1 January 1970 was a Thursday: day n's place in its week, Monday 0 … Sunday 6, is (n + 3) mod 7.
  const monday = now - ((now + 3) % 7);
  const first = number(`${today.slice(0, 8)}01`);
  return `d${was < monday ? 'w' : ''}${was < first ? 'm' : ''}` as Fresh;
}
