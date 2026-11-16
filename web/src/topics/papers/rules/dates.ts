/** Days and years on ISO dates, at noon UTC so no clock change moves a day. Pure. */
const at = (d: string) => new Date(`${d}T12:00:00Z`);
const iso = (x: Date) => x.toISOString().slice(0, 10);

/** The same day `n` years on; 29 February falls to the 28th in a year without it. */
export function addYears(day: string, n: number): string {
  const [y, m, d] = day.split('-').map(Number);
  const last = new Date(Date.UTC(y + n, m, 0)).getUTCDate();
  return iso(new Date(Date.UTC(y + n, m - 1, Math.min(d, last), 12)));
}

/** The same day `n` months on, or that month's last day. */
export function addMonths(day: string, n: number): string {
  const [y, m, d] = day.split('-').map(Number);
  const last = new Date(Date.UTC(y, m - 1 + n + 1, 0)).getUTCDate();
  return iso(new Date(Date.UTC(y, m - 1 + n, Math.min(d, last), 12)));
}

export function addDays(day: string, n: number): string {
  return iso(new Date(at(day).getTime() + n * 864e5));
}

/** Full solar years from `birth` to `on`. */
export function age(birth: string, on: string): number {
  const [by, bm, bd] = birth.split('-').map(Number);
  const [y, m, d] = on.split('-').map(Number);
  return y - by - (m < bm || (m === bm && d < bd) ? 1 : 0);
}

export const before = (a: string, b: string) => a < b;
