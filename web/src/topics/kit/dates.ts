import { holiday, type Holiday } from './holidays.ts';

/** The dates a topic's texts set (F7 of the family plan, T10 of the work plan): a limit counted from the day of an
 *  event, each with its article. Days from the next day (the event day + n), months to the same date; hours as the
 *  days they run into. A «complete» limit (law 58.25, art. 602: the courts') counts neither the first nor the last day,
 *  and one that ends on a Saturday, a Sunday or a public holiday (holidays.ts, U12 of the Moroccan-design review)
 *  moves to the next working day. Any other limit that ends on a holiday says so, and stays. A limit the law counts
 *  otherwise is said in words, never as a date. */
export type Deadline = {
  key: string; days?: number; months?: number; extraDays?: number; hours?: number; complete?: boolean;
  /** Its last day, off (a weekend or a public holiday), moves to the next working day, the first counted (decree
   *  2.22.04, art. 40: the births' and deaths' declarations). */
  rolls?: boolean;
  path: string; label: string; note?: string;
};
export type Event = { key: string; deadlines: Deadline[]; words?: string[] };

const DAY = 86_400_000;

/** The date a limit ends, as ISO: «2026-10-19» + 30 days is «2026-11-18»; + 6 months is «2027-04-19». A month without
 *  that day ends on its last day (31 Aug + 6 months is 28 Feb). */
export function due(event: string, d: Deadline): string {
  return ending(event, d).date;
}

/** `due`, with the holidays a complete limit was moved past (`moved`), or the one an ordinary limit ends on (`on`). */
export function ending(event: string, d: Deadline): { date: string; moved: Holiday[]; on: Holiday | null } {
  const [y, m, day] = event.split('-').map(Number);
  let date = new Date(Date.UTC(y, m - 1, day));
  if (d.months) {
    const target = new Date(Date.UTC(y, m - 1 + d.months, 1));
    const last = new Date(Date.UTC(target.getUTCFullYear(), target.getUTCMonth() + 1, 0)).getUTCDate();
    date = new Date(Date.UTC(target.getUTCFullYear(), target.getUTCMonth(), Math.min(day, last)));
  }
  date = new Date(date.getTime() + ((d.days ?? 0) + (d.extraDays ?? 0) + Math.ceil((d.hours ?? 0) / 24)) * DAY);
  const iso = (x: Date) => x.toISOString().slice(0, 10);
  const moved: Holiday[] = [];
  if (d.complete) date = new Date(date.getTime() + DAY);     // the last day is not counted either
  if (d.complete || d.rolls) {
    for (;;) {
      const off = holiday(iso(date));
      if (off) moved.push(off);
      else if (![0, 6].includes(date.getUTCDay())) break;
      date = new Date(date.getTime() + DAY);
    }
  }
  return { date: iso(date), moved, on: d.complete || d.rolls ? null : holiday(iso(date)) };
}
