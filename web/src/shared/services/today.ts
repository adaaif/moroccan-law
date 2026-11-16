/** Today as the law counts it: the day in Morocco, asked of its time zone, never read from UTC (A1 of
 *  the road-signposted review). While Morocco was an hour ahead of UTC, `toISOString()` gave every deadline a day too early from
 *  midnight to one in the morning. Since 20 September 2026 Morocco is on Greenwich's time (decree 2.26.530), and the
 *  zone's own rules, not this file, know it: the browser's time zone data must be from mid-2026 or later. */
export const ZONE = 'Africa/Casablanca';

/** The calendar day a moment falls on in a time zone, as YYYY-MM-DD. */
export function dayIn(at: Date, zone = ZONE): string {
  const parts = new Intl.DateTimeFormat('en-CA', { timeZone: zone, year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(at);
  const get = (type: string) => parts.find((p) => p.type === type)?.value ?? '';
  return `${get('year')}-${get('month')}-${get('day')}`;
}

/** Today in Morocco. */
export const todayIso = (): string => dayIn(new Date());

/** A day `n` days before (or after, when negative) another, counted on the calendar. */
export function shiftDay(day: string, n: number): string {
  const [y, m, d] = day.split('-').map(Number);
  return new Date(Date.UTC(y, m - 1, d - n)).toISOString().slice(0, 10);
}

/** The day `n` days ago in Morocco. */
export const daysAgo = (n: number): string => shiftDay(todayIso(), n);

/** The same day `n` years ago in Morocco (29 February falls back to the 28th). */
export function yearsAgo(n: number): string {
  const [y, m, d] = todayIso().split('-').map(Number);
  const last = new Date(Date.UTC(y - n, m, 0)).getUTCDate();
  return `${y - n}-${String(m).padStart(2, '0')}-${String(Math.min(d, last)).padStart(2, '0')}`;
}
