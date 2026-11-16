/** The CNSS (T11 of the work plan): the old-age pension from the days and wages the CNSS shows, and whether the
 *  job-loss allowance is open, each from the dahir 1.72.184 and decree 2.25.265. */
const round2 = (x: number) => Math.round(x * 100) / 100;

export type Pension = { eligible: boolean; rate: number; formula: number; floor: number; amount: number; base: number };

/** From 1,320 to 3,239 days: 50% × days ÷ 3,240, kept to two decimals, of the 96 months' average (decree 2.25.265,
 *  art. 1); from 3,240: 50% plus 1% per 216 days beyond, at most 70% (dahir, arts 55–56). Wages count up to the
 *  ceiling. Never under the floor for the days (art. 2). Under 1,320 days: the contributions are refunded (art. 53). */
export function pension(days: number, average: number, r: Record<string, number>): Pension {
  const base = Math.min(average, r.ceiling);
  if (days < r.min_days) return { eligible: false, rate: 0, formula: 0, floor: 0, amount: 0, base };
  const rate = days < r.full_days
    ? Math.floor(((r.base_rate * days) / r.full_days) * 100) / 100
    : Math.min(r.max_rate, r.base_rate + r.step_rate * Math.floor((days - r.full_days) / r.step_days));
  const formula = round2((base * rate) / 100);
  const floor = days >= 2857 ? r.floor_2857 : days >= 2473 ? r.floor_2473 : days >= 2089 ? r.floor_2089 : days >= 1705 ? r.floor_1705 : r.floor_1320;
  return { eligible: true, rate, formula, floor, amount: Math.max(formula, floor), base };
}

export type Allowance = { open: boolean; missing36: number; missing12: number; amount: number; months: number };

/** Dahir, arts 46 bis–quater: 780 days in the 36 months before, 260 of them in the last 12, the job lost against your
 *  will, registered with ANAPEC; 70% of the 36 months' average, at most the minimum wage, for six months. */
export function allowance(days36: number, days12: number, involuntary: boolean, registered: boolean, average: number,
                          minimumMonthly: number, r: Record<string, number>): Allowance {
  const missing36 = Math.max(0, r.days_36_months - days36);
  const missing12 = Math.max(0, r.days_12_months - days12);
  return {
    open: !missing36 && !missing12 && involuntary && registered, missing36, missing12,
    amount: round2(Math.min((average * r.rate) / 100, minimumMonthly)), months: r.months,
  };
}
