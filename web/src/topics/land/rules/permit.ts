/** The permit's road (the land review, M12): from the day a permit's file was filed at the commune, each stop the
 *  texts date, with its article. Pure. Working days («أيام مفتوحة», decree 2.18.577) skip Saturdays, Sundays and the
 *  public holidays of decree 2.77.169 (kit/holidays.ts). The tacit permit comes two months after the filing (law 12.90,
 *  art. 48); a permit, express or tacit, lapses a year after it was given or after those two months if the foundations
 *  have not begun (art. 49). The dates are what the texts set, never a promise of the commune's answer. */
import { holiday } from '../../kit/holidays.ts';

export type Stop = { key: 'filed' | 'committee' | 'study' | 'tacit' | 'lapse'; date: string; cites: string[] };

const DAY = 86_400_000;
const iso = (d: Date) => d.toISOString().slice(0, 10);
const at = (day: string) => new Date(`${day}T00:00:00Z`);

/** `n` working days after `day`: neither a Saturday, a Sunday nor a public holiday counts. */
export function workingDays(day: string, n: number): string {
  let d = at(day);
  let left = n;
  while (left > 0) {
    d = new Date(d.getTime() + DAY);
    if (![0, 6].includes(d.getUTCDay()) && !holiday(iso(d))) left--;
  }
  return iso(d);
}

/** The same date `months` later (the last day of a shorter month). */
export function addMonths(day: string, months: number): string {
  const [y, m, dd] = day.split('-').map(Number);
  const target = new Date(Date.UTC(y, m - 1 + months, 1));
  const last = new Date(Date.UTC(target.getUTCFullYear(), target.getUTCMonth() + 1, 0)).getUTCDate();
  return iso(new Date(Date.UTC(target.getUTCFullYear(), target.getUTCMonth(), Math.min(dd, last))));
}

/** The road from a filing day, or from the day the permit was given when the commune answered (`given`). */
export function road(filed: string, given?: string): Stop[] {
  const toCommittee = workingDays(filed, 3);           // the commune sends the file to the committee (decree art. 18)
  const study = workingDays(filed, 15);                // the committee decides within 15 working days of the filing
  const tacit = addMonths(filed, 2);                   // silence for two months is a permit (law 12.90, art. 48)
  const from = given && given < tacit ? given : tacit;
  return [
    { key: 'filed', date: filed, cites: ['/ma/decret/2-18-577/art_18'] },
    { key: 'committee', date: toCommittee, cites: ['/ma/decret/2-18-577/art_18', '/ma/decret/2-18-577/art_21'] },
    { key: 'study', date: study, cites: ['/ma/decret/2-18-577/art_18', '/ma/decret/2-18-577/art_38'] },
    { key: 'tacit', date: tacit, cites: ['/ma/loi/12-90/art_48'] },
    { key: 'lapse', date: addMonths(from, 12), cites: ['/ma/loi/12-90/art_49'] },
  ];
}
