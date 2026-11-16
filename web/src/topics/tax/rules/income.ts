/** Income tax for a person (the tax review, T10–T12): the scale slice by slice (CGI art. 73-I), the family
 *  deduction (74-I), a salary from its gross (59: professional expenses and the worker's social contributions), a pension
 *  (57-27°, 60-I) and rent (64, 73-II, 160 bis). Every figure comes from the topic's rates.yaml row in force on the day
 *  asked; nothing here knows a year. Amounts are dirhams a year unless named monthly. Pure: `npm run test:tax`. */

export type Rates = Record<string, number>;
const round2 = (x: number) => Math.round(x * 100) / 100;

/** One slice of the scale: the income it covers, its rate, the tax it bears. */
export type Slice = { from: number; to: number | null; rate: number; base: number; tax: number };

/** The scale's slices (s1…s5 the thresholds, r1…r5 the rates above each; the first slice is exempt). */
export function slices(sc: Rates): { from: number; to: number | null; rate: number }[] {
  const edges = [0, sc.s1, sc.s2, sc.s3, sc.s4, sc.s5];
  const rates = [0, sc.r1, sc.r2, sc.r3, sc.r4, sc.r5];
  // A threshold repeated (a bill's scale with fewer slices) leaves an empty slice: none is drawn.
  return edges.map((from, i) => ({ from, to: i + 1 < edges.length ? edges[i + 1] : null, rate: rates[i] }))
    .filter((s) => s.to === null || s.to > s.from);
}

/** The scale applied to a taxable income: each slice taxed at its own rate (art. 73-I), the rate on the next dirham. */
export function scaleTax(income: number, sc: Rates): { tax: number; slices: Slice[]; marginal: number } {
  const out: Slice[] = slices(sc).map((s) => {
    const base = Math.max(0, Math.min(income, s.to ?? Infinity) - s.from);
    return { ...s, base, tax: round2((base * s.rate) / 100) };
  });
  const marginal = out.filter((s) => income > s.from).at(-1)?.rate ?? 0;
  return { tax: round2(out.reduce((a, s) => a + s.tax, 0)), slices: out, marginal };
}

/** Art. 74-I: so much off the year's tax for each dependent, at most the total, never below zero. */
export function familyOff(dependents: number, fam: Rates): number {
  return Math.min(Math.max(0, dependents) * fam.per, fam.max);
}

/** The worker's social contributions a year (decrees 2.01.2723 and 2.05.734, the work topic's rates): pension,
 *  short-term and job loss on the wage up to the ceiling, AMO on the whole; all deductible (art. 59-II and III). */
export function contributions(grossMonthly: number, cnss: Rates): { cnss: number; amo: number } {
  const capped = Math.min(grossMonthly, cnss.ceiling);
  const cnssM = (capped * (cnss.worker_long + cnss.worker_short + cnss.worker_ipe)) / 100;
  const amoM = (grossMonthly * cnss.worker_amo) / 100;
  return { cnss: round2(cnssM * 12), amo: round2(amoM * 12) };
}

/** Art. 59-I-A: professional expenses, a share of the gross taxable salary (the lower one's up to the threshold, the
 *  higher above it, the whole at that rate), at most the cap above the threshold. */
export function expenses(grossYear: number, ex: Rates): { rate: number; amount: number } {
  if (grossYear <= ex.threshold) return { rate: ex.low_rate, amount: round2((grossYear * ex.low_rate) / 100) };
  return { rate: ex.high_rate, amount: round2(Math.min((grossYear * ex.high_rate) / 100, ex.cap)) };
}

export type SalaryTax = {
  grossYear: number; cnss: number; amo: number; expenses: number; expensesRate: number; taxable: number;
  scale: number; family: number; tax: number; slices: Slice[]; marginal: number; average: number;
  monthly: { gross: number; cnss: number; amo: number; tax: number; net: number };
};

/** A salary from its gross a month (T10): the year's gross, the worker's contributions, professional expenses, the
 *  net taxable income, the scale, the family deduction; the month as a payslip prints it (the year ÷ 12). */
export function salaryTax(grossMonthly: number, dependents: number, r: { scale: Rates; family: Rates; expenses: Rates; cnss: Rates }): SalaryTax {
  const grossYear = round2(grossMonthly * 12);
  const c = contributions(grossMonthly, r.cnss);
  const ex = expenses(grossYear, r.expenses);
  const taxable = Math.max(0, round2(grossYear - ex.amount - c.cnss - c.amo));
  const s = scaleTax(taxable, r.scale);
  const family = Math.min(familyOff(dependents, r.family), s.tax);
  const tax = round2(s.tax - family);
  const m = { gross: round2(grossMonthly), cnss: round2(c.cnss / 12), amo: round2(c.amo / 12), tax: round2(tax / 12) };
  return {
    grossYear, cnss: c.cnss, amo: c.amo, expenses: ex.amount, expensesRate: ex.rate, taxable, scale: s.tax, family, tax,
    slices: s.slices, marginal: s.marginal, average: grossYear ? round2((tax / grossYear) * 100) : 0,
    monthly: { ...m, net: round2(m.gross - m.cnss - m.amo - m.tax) },
  };
}

/** What a month's allowance costs once it is taxed as salary (the 2027 bill's art. 57-1° from 2031): the month's tax with
 *  the allowance added to the gross — professional expenses on the whole, to their cap — less the tax without it. The
 *  social contributions stay those of the salary: the bill changes the tax only. */
export function allowanceCost(grossMonthly: number, allowanceMonthly: number, dependents: number, r: { scale: Rates; family: Rates; expenses: Rates; cnss: Rates }): number {
  const base = salaryTax(grossMonthly, dependents, r);
  const grossYear = round2((grossMonthly + allowanceMonthly) * 12);
  const taxable = Math.max(0, round2(grossYear - expenses(grossYear, r.expenses).amount - base.cnss - base.amo));
  const s = scaleTax(taxable, r.scale);
  const tax = round2(s.tax - Math.min(familyOff(dependents, r.family), s.tax));
  return round2((tax - base.tax) / 12);
}

/** The tax on a salary payslip's month (the work topic's payslip, T10): from the month's gross and contributions. */
export function monthTax(grossMonthly: number, dependents: number, r: { scale: Rates; family: Rates; expenses: Rates; cnss: Rates }): number {
  return salaryTax(grossMonthly, dependents, r).monthly.tax;
}

export type Scheme = 'basic' | 'cimr' | 'other' | 'foreign';
export type PensionTax = { gross: number; exempt: boolean; abatement: number; taxable: number; scale: number; family: number; reduction: number; tax: number; slices: Slice[] };

/** A pension a year (T11): a basic scheme's (CNSS, CMR, RCAR…) exempt from 2026 (57-27°), half its tax off in 2025; a
 *  CIMR group contract's exempt on the conditions of 28-III (asked as a yes); any other abated 70% to the threshold and
 *  40% above (60-I), then the scale and the family deduction; a foreign pension transferred for good in dirhams has 80%
 *  of its tax off (art. 76). */
export function pensionTax(gross: number, scheme: Scheme, dependents: number, r: { scale: Rates; family: Rates; pension: Rates }): PensionTax {
  const p = r.pension;
  const exempt = (scheme === 'basic' || scheme === 'cimr') && p.basic_exempt === 1;
  const abatement = round2((Math.min(gross, p.threshold) * p.low_rate) / 100 + (Math.max(0, gross - p.threshold) * p.high_rate) / 100);
  const taxable = exempt ? 0 : Math.max(0, round2(gross - abatement));
  const s = scaleTax(taxable, r.scale);
  const family = Math.min(familyOff(dependents, r.family), s.tax);
  const due = s.tax - family;
  const share = scheme === 'basic' ? p.basic_reduction : scheme === 'foreign' ? p.foreign_reduction : 0;
  const reduction = round2((due * share) / 100);
  return { gross, exempt, abatement, taxable, scale: s.tax, family, reduction, tax: exempt ? 0 : round2(due - reduction), slices: s.slices };
}

export type RentTax = { gross: number; abatement: number; net: number; scale: number; withheld: number; withheldRate: number; final: number };

/** Rent a year (T12): 40% off the gross (64-II), the scale on the rest as if it were the only income; what a company or
 *  administration tenant withholds (10% under the threshold, 15% above; 160 bis); the 20% final rate on option (64-IV). */
export function rentTax(gross: number, r: { scale: Rates; rent: Rates }): RentTax {
  const abatement = round2((gross * r.rent.abatement) / 100);
  const net = round2(gross - abatement);
  const withheldRate = gross < r.rent.withhold_threshold ? r.rent.withhold_low : r.rent.withhold_high;
  return {
    gross, abatement, net, scale: scaleTax(net, r.scale).tax,
    withheld: round2((gross * withheldRate) / 100), withheldRate, final: round2((gross * r.rent.final) / 100),
  };
}
