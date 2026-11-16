import { todayIso } from '@/shared/services/today';
import { billRow, useRateOn, useRates } from '../kit/api';
import { salaryTax, type Rates, type SalaryTax } from './rules/income';

export const BILL_YEARS = ['2027', '2028', '2029', '2030', '2031'];
type Rules = { scale: Rates; family: Rates; expenses: Rates; cnss: Rates };

/** A salary today and under the 2027 bill's five years (the finance-bill review, P6): today's law from the rates in force,
 *  each year's scale and expenses from the bill's own tables (rows `proposed`, read by `billRow` only). Shared by the
 *  bill's tool, the page's calculator and its scale through the years; undefined while the rates load. */
export function useBillYears(slug: string, gross: number, kids: number) {
  const today = todayIso();
  const now = { scale: useRateOn(slug, 'scale', today), family: useRateOn(slug, 'family', today),
                expenses: useRateOn(slug, 'expenses', today), cnss: useRateOn('work', 'cnss', today) };
  const scales = useRates(slug, 'bill-scale');
  const expenses = useRates(slug, 'bill-expenses');
  if (!now.scale || !now.family || !now.expenses || !now.cnss || !scales.data || !expenses.data) return undefined;
  const base = now as Rules;
  const rules = (y: string): Rules => {
    const day = `${y}-06-30`;
    return { ...base, scale: billRow(scales.data.rows, day)?.values ?? base.scale,
             expenses: billRow(expenses.data.rows, day)?.values ?? base.expenses };
  };
  const today_: SalaryTax = salaryTax(gross, kids, base);
  const years = BILL_YEARS.map((y) => {
    const r = salaryTax(gross, kids, rules(y));
    return { y, r, gain: Math.round((today_.monthly.tax - r.monthly.tax) * 100) / 100 };
  });
  return { today: today_, years, rules, base };
}

/** The highest gross a month on which no income tax is due under these rules, to the dirham, and its net. */
export function exemptUpTo(dependents: number, r: Rules): { gross: number; net: number } {
  let lo = 0, hi = 100_000;
  while (hi - lo > 1) {
    const mid = Math.floor((lo + hi) / 2);
    if (salaryTax(mid, dependents, r).monthly.tax > 0) hi = mid; else lo = mid;
  }
  return { gross: lo, net: salaryTax(lo, dependents, r).monthly.net };
}

export type CurvePoint = { g: number; now: number; gains: Record<string, number> };

/** The gain at every gross salary from 3,000 to 30,000 a month, 250 apart (the bill-story review, Y1): today's
 *  month's tax and each bill year's gain, for the reader's dependents. From the same rules as the tool. */
export function curvePoints(b: NonNullable<ReturnType<typeof useBillYears>>, kids: number): CurvePoint[] {
  const out: CurvePoint[] = [];
  const rules = Object.fromEntries(BILL_YEARS.map((y) => [y, b.rules(y)]));
  for (let g = 3000; g <= 30000; g += 250) {
    const now = salaryTax(g, kids, b.base).monthly.tax;
    out.push({ g, now, gains: Object.fromEntries(BILL_YEARS.map((y) => [y, Math.round((now - salaryTax(g, kids, rules[y]).monthly.tax) * 100) / 100])) });
  }
  return out;
}
