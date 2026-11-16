/** Is my pay legal? (T9 of the work plan): the minimum on a date, the seniority bonus, overtime, the days of leave,
 *  and the payslip's CNSS and AMO lines, each from its article or decree. Income tax is left out until the tax code is
 *  on the site. */
import { HOURS_MONTH } from './end.ts';

export type Sector = 'nonfarm' | 'farm' | 'home';
const round2 = (x: number) => Math.round(x * 100) / 100;

/** The monthly minimum: the hourly one × 191 for 44 hours a week (in proportion for fewer), the farm day × 26, and in a
 *  home 60% of the industry minimum (law 19.12, art. 19). */
export function minimumMonthly(sector: Sector, smigHour: number, smagDay: number, hoursWeek = 44, homeShare = 60): number {
  if (sector === 'farm') return round2(smagDay * 26);
  if (sector === 'home') return round2((smigHour * HOURS_MONTH * homeShare) / 100);
  return round2((smigHour * HOURS_MONTH * Math.min(hoursWeek, 44)) / 44);
}

/** Art. 350: 5% after two years, 10% after five, 15% after twelve, 20% after twenty, 25% after twenty-five. */
export function seniorityRate(years: number): number {
  return years >= 25 ? 25 : years >= 20 ? 20 : years >= 12 ? 15 : years >= 5 ? 10 : years >= 2 ? 5 : 0;
}

/** Art. 201: +25% by day (6:00–21:00; on a farm 5:00–20:00), +50% by night; +50% and +100% on the weekly rest day. */
export function overtimeRate(night: boolean, restDay: boolean): number {
  return (night ? 50 : 25) * (restDay ? 2 : 1);
}
export const overtimePay = (hourly: number, hours: number, night: boolean, restDay: boolean) =>
  round2(hours * hourly * (1 + overtimeRate(night, restDay) / 100));

/** Arts 231–232: after six months, 1.5 working days a month (2 under 18) — 18 days a year, 24 under 18 — and 1.5 more
 *  per five years of service, never past 30. */
export function leaveDays(serviceMonths: number, under18: boolean): number {
  if (serviceMonths < 6) return 0;
  const perMonth = under18 ? 2 : 1.5;
  const base = serviceMonths < 12 ? serviceMonths * perMonth : 12 * perMonth;
  return Math.min(30, base + 1.5 * Math.floor(serviceMonths / 60));
}

/** The worker's shares on a payslip (decrees 2.01.2723 and 2.05.734): pension, short-term and job-loss on wages up to
 *  the ceiling, AMO on the whole wage. */
export function workerShares(gross: number, r: Record<string, number>) {
  const capped = Math.min(gross, r.ceiling);
  const lines = {
    long: round2((capped * r.worker_long) / 100), short: round2((capped * r.worker_short) / 100),
    ipe: round2((capped * r.worker_ipe) / 100), amo: round2((gross * r.worker_amo) / 100),
  };
  return { ...lines, total: round2(lines.long + lines.short + lines.ipe + lines.amo) };
}

/** The payslip the law writes (E14 of the work-counted review): the base for the hours, the seniority bonus on it (art. 350),
 *  overtime at the hour of the base (art. 201; a farm month counts 208 hours; none at home, where 19.12 sets 48 hours),
 *  the gross; the worker's CNSS shares (pension, short-term, job loss: up to the ceiling) and AMO (the whole wage);
 *  the net before income tax, which the tool does not compute. The minimum for the hours is beside the base. */
export type OvertimeKind = 'day' | 'night' | 'restDay' | 'restNight';
export type PayslipInput = { sector: Sector; hoursWeek: number; base: number; years: number; overtime: number; kind: OvertimeKind };
export type Payslip = {
  base: number; seniorityRate: number; seniority: number; hourly: number; overtimeRate: number; overtime: number; gross: number;
  cnssRate: number; cnss: number; amoRate: number; amo: number; net: number; minimum: number; gap: number;
};
export function payslip(i: PayslipInput, r: { smigHour: number; smagDay: number; homeShare: number; cnss: Record<string, number> }): Payslip {
  const minimum = minimumMonthly(i.sector, r.smigHour, r.smagDay, i.hoursWeek, r.homeShare);
  const seniorityRate_ = seniorityRate(i.years);
  const seniority = round2((i.base * seniorityRate_) / 100);
  const hourly = i.base / (i.sector === 'farm' ? 208 : HOURS_MONTH);
  const rate = i.sector === 'home' ? 0 : overtimeRate(i.kind === 'night' || i.kind === 'restNight', i.kind === 'restDay' || i.kind === 'restNight');
  const overtime = i.sector === 'home' ? 0 : round2(i.overtime * hourly * (1 + rate / 100));
  const gross = round2(i.base + seniority + overtime);
  // One CNSS line, as a payslip prints it: the three shares' rate on the wage up to the ceiling; AMO on the whole wage.
  const cnssRate = round2(r.cnss.worker_long + r.cnss.worker_short + r.cnss.worker_ipe);
  const cnss = round2((Math.min(gross, r.cnss.ceiling) * cnssRate) / 100);
  const amo = round2((gross * r.cnss.worker_amo) / 100);
  return {
    base: i.base, seniorityRate: seniorityRate_, seniority, hourly: round2(hourly), overtimeRate: rate, overtime, gross,
    cnssRate, cnss, amoRate: r.cnss.worker_amo, amo, net: round2(gross - cnss - amo), minimum, gap: round2(minimum - i.base),
  };
}
