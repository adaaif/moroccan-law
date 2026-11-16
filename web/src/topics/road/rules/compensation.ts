/** The permanent-incapacity indemnity under the 2026 table (R13 of the road plan, kept back until a lawyer has
 *  reviewed it, Q5): dahir 1.84.177 as law 70.24 changed it, for accidents from 29 January 2026 (70.24 art. 7). The
 *  capital is read in the table by the victim's age and yearly earnings, between two rows by art. 5's formula; the
 *  indemnity is that capital times the rate the doctor sets (art. 9), and a point is worth at least a fifth of the
 *  minimum earnings (art. 5). The table is BO 7478's as read here, its misprints kept as printed. */

export type Table = {
  earnings: number[]; ages: number[]; capital: Record<string, number[]>; page: Record<string, (number | null)[]>;
  misprints: { earnings: number; age: number; printed: number; steps: number; page: number }[];
  minimum: { from: string; earnings: number; capital: number[] }[];
};

export type Result = {
  minimum: number; earnings: number; capital: number; pointFloor: number; indemnity: number;
  rows: { earnings: number; capital: number; page: number | null }[];
  misprint: Table['misprints'][number] | null;
};

/** The table in force on the accident's day: the annex's rows above, and the minimum row of art. 5's year below. */
function rowsOn(t: Table, day: string): { earnings: number; capital: number[]; page: (number | null)[] }[] {
  const step = [...t.minimum].reverse().find((m) => m.from <= day);
  const annex = t.earnings.map((e) => ({ earnings: e, capital: t.capital[String(e)], page: t.page[String(e)] }));
  if (!step) return annex;
  return [{ earnings: step.earnings, capital: step.capital, page: step.capital.map(() => 848) },
          ...annex.filter((r) => r.earnings > step.earnings)];
}

export function compensate(t: Table, day: string, age: number, earnings: number, rate: number): Result {
  const rows = rowsOn(t, day);
  const col = t.ages.indexOf(Math.min(Math.max(age, t.ages[0]), t.ages[t.ages.length - 1]));
  const minimum = rows[0].earnings;
  const e = Math.min(Math.max(earnings || minimum, minimum), rows[rows.length - 1].earnings);
  const upper = rows.findIndex((r) => r.earnings >= e);
  const hi = rows[upper];
  const lo = hi.earnings === e ? hi : rows[upper - 1];
  const c1 = lo.capital[col], c2 = hi.capital[col];
  const capital = lo === hi ? c1 : Math.round(c1 + ((e - lo.earnings) / (hi.earnings - lo.earnings)) * (c2 - c1));
  const pointFloor = minimum / 5;
  const point = Math.max(capital / 100, pointFloor);
  const used = lo === hi ? [lo] : [lo, hi];
  const misprint = t.misprints.find((m) => m.age === t.ages[col] && used.some((r) => r.earnings === m.earnings)) ?? null;
  return {
    minimum, earnings: e, capital, pointFloor, indemnity: Math.round(point * rate),
    rows: used.map((r) => ({ earnings: r.earnings, capital: r.capital[col], page: r.page[col] })), misprint,
  };
}
