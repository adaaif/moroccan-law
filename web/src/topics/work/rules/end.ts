/** What the law gives at the end of a contract of indefinite duration (T8 of the work plan), computed on the phone.
 *  Each line names its articles; a sum the law leaves to a judge (damages) is shown apart, as the formula art. 41 sets
 *  if a court finds the dismissal abusive. Three choices are the site's, said on the page until a professional checks them:
 *  a month counts 191 hours (as the CNSS turns the hourly minimum into a monthly one; art. 184's 2,288 a year give
 *  190.67), 208 on a farm (2,496 ÷ 12); a fraction of a year counts by its months; a day of notice or of leave is paid
 *  as a working day (a month ÷ 26). The ministry's own simulator (miepeec.gov.ma/simulation) does the same: 191 hours,
 *  ÷ 26; the tests hold its published formulas beside these. */
export const HOURS_MONTH = 191;
export const FARM_HOURS_MONTH = 208;
export const LEAVE_DAYS_MONTH = 26;

export type Category = 'cadre' | 'employee' | 'worker';
export type Ending = 'dismissed' | 'seriousFault' | 'resigned' | 'retired';
export type EndInput = {
  start: string; end: string; category: Category; farm: boolean; monthly: number;
  noticeGiven: boolean; leaveDays: number; delegate: boolean; ending: Ending;
};
/** The decrees' figures on the day the contract ends: the notice table (decree 2.04.469), the hourly and daily minimum. */
export type EndRates = { notice: Record<string, number>; smigHour: number; smagDay: number };
export type LineKey = 'notice' | 'severance' | 'leave' | 'damages';
export type Line = {
  key: LineKey; amount: number; applies: boolean; why?: string; conditional?: boolean;
  detail: Record<string, number | string>; cites: string[];
};

const code = (n: number) => `/ma/loi/65-99/art_${n}`;
const round2 = (x: number) => Math.round(x * 100) / 100;

/** Whole months worked, the last day included: 2019-03-15 → 2026-03-14 is 84 (seven years), 1 Jan → 31 Dec is 12. */
export function months(start: string, end: string): number {
  const [y1, m1, d1] = start.split('-').map(Number);
  const [ye, me, de] = end.split('-').map(Number);
  const after = new Date(Date.UTC(ye, me - 1, de) + 86_400_000);
  const [y2, m2, d2] = [after.getUTCFullYear(), after.getUTCMonth() + 1, after.getUTCDate()];
  const n = (y2 - y1) * 12 + (m2 - m1) - (d2 < d1 ? 1 : 0);
  return Math.max(0, n);
}

/** The first day of a service of `n` whole months ending on `end` (the last day worked): `months(startFor(end, n), end)`
 *  is `n`. The tool asks the years and months, as a reader says them, and counts from the contract's last day. */
export function startFor(end: string, n: number): string {
  const [y, m, d] = end.split('-').map(Number);
  const after = new Date(Date.UTC(y, m - 1, d) + 86_400_000);
  const first = new Date(Date.UTC(after.getUTCFullYear(), after.getUTCMonth() - n, 1));
  // The same day of the month, or the month's last when it is shorter (31 March − 1 month → 28 or 29 February).
  const last = new Date(Date.UTC(first.getUTCFullYear(), first.getUTCMonth() + 1, 0)).getUTCDate();
  first.setUTCDate(Math.min(after.getUTCDate(), last));
  return first.toISOString().slice(0, 10);
}

/** Art. 53's staircase for a service of `service` months: one step a year begun, its band's hours a year, the months of
 *  it worked, and the hours it gives (the band × months ÷ 12). */
export type Stair = { year: number; band: number; months: number; hours: number };
export function stairs(service: number): Stair[] {
  const out: Stair[] = [];
  for (let year = 1; (year - 1) * 12 < service; year++) {
    const band = year <= 5 ? 96 : year <= 10 ? 144 : year <= 15 ? 192 : 240;
    const months = Math.min(12, service - (year - 1) * 12);
    out.push({ year, band, months, hours: round2((band * months) / 12) });
  }
  return out;
}
export const bandOf = (year: number) => (year <= 5 ? 96 : year <= 10 ? 144 : year <= 15 ? 192 : 240);

/** Art. 53: 96 hours of wage a year for the first five years, 144 for the sixth to the tenth, 192 for the eleventh to
 *  the fifteenth, 240 beyond, each year or fraction of a year counted by its months. */
export function severanceHours(service: number): number {
  let hours = 0;
  for (let m = 0; m < service; m++) {
    const year = Math.floor(m / 12) + 1;
    hours += (year <= 5 ? 96 : year <= 10 ? 144 : year <= 15 ? 192 : 240) / 12;
  }
  return round2(hours);
}

/** Decree 2.04.469: managers 1, 2 or 3 months; employees and workers 8 days, 1 month or 2, by seniority under a
 *  year, from one to five, over five. */
export function noticeOf(category: Category, service: number, n: Record<string, number>): { months?: number; days?: number } {
  const years = service / 12;
  if (category === 'cadre') return { months: years < 1 ? n.cadre_under1_months : years <= 5 ? n.cadre_1to5_months : n.cadre_over5_months };
  return years < 1 ? { days: n.worker_under1_days } : { months: years <= 5 ? n.worker_1to5_months : n.worker_over5_months };
}

export function endOfContract(i: EndInput, r: EndRates): Line[] {
  const service = months(i.start, i.end);
  // The hour of wage the indemnity is counted on: the 52 weeks' average, never under the minimum of the day (art. 56).
  const own = i.monthly / (i.farm ? FARM_HOURS_MONTH : HOURS_MONTH);
  const floor = i.farm ? r.smagDay / 8 : r.smigHour;
  const hourly = Math.max(own, floor);
  const dismissed = i.ending === 'dismissed';
  const notice = noticeOf(i.category, service, r.notice);
  const noticeAmount = notice.months ? notice.months * i.monthly : ((notice.days ?? 0) * i.monthly) / LEAVE_DAYS_MONTH;
  const hours = severanceHours(service) * (i.delegate ? 2 : 1);
  const years = service / 12;
  const damages = Math.min(1.5 * i.monthly * years, 36 * i.monthly);
  return [
    { key: 'notice', amount: round2(noticeAmount), applies: dismissed && !i.noticeGiven,
      why: i.ending === 'seriousFault' ? 'seriousFault' : i.ending === 'resigned' ? 'resignedOwes' : i.noticeGiven ? 'noticeGiven' : i.ending === 'retired' ? 'retired' : undefined,
      detail: { months: notice.months ?? 0, days: notice.days ?? 0 }, cites: [code(43), code(51), '/ma/decret/2-04-469/art_1'] },
    { key: 'severance', amount: round2(hours * hourly), applies: dismissed && service >= 6,
      why: i.ending === 'seriousFault' ? 'seriousFault' : i.ending === 'resigned' ? 'resigned' : i.ending === 'retired' ? 'retired' : service < 6 ? 'underSix' : undefined,
      detail: { hours, hourly: round2(hourly), floored: hourly > own ? 1 : 0, delegate: i.delegate ? 1 : 0 },
      cites: [code(52), code(53), code(55), code(56), ...(i.delegate ? [code(58)] : [])] },
    { key: 'leave', amount: round2((i.leaveDays * i.monthly) / LEAVE_DAYS_MONTH), applies: service >= 6 && i.leaveDays > 0,
      why: service < 6 ? 'underSix' : i.leaveDays <= 0 ? 'noLeave' : undefined, detail: { days: i.leaveDays }, cites: [code(251)] },
    { key: 'damages', amount: round2(damages), applies: dismissed, conditional: true,
      why: i.ending === 'seriousFault' ? 'seriousFault' : i.ending === 'resigned' ? 'resigned' : i.ending === 'retired' ? 'retired' : undefined,
      detail: { years: round2(years), capped: damages >= 36 * i.monthly ? 1 : 0 }, cites: [code(41), code(59), code(61)] },
  ];
}
