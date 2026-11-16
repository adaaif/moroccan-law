/** The plain arithmetic of «نزع الملكية» (post 24), kept apart from the drawing so it can be tested: a year's total, the
 *  sums of a span by purpose, a share in whole percent, and how many a year a span holds. */
export type Year = { year: number } & Record<string, number>;

export const total = (y: Year): number => Object.entries(y).reduce((s, [k, v]) => (k === 'year' ? s : s + v), 0);

export function sums(years: Year[], from: number, to: number): Record<string, number> {
  const out: Record<string, number> = {};
  for (const y of years) {
    if (y.year < from || y.year > to) continue;
    for (const [k, v] of Object.entries(y)) if (k !== 'year') out[k] = (out[k] ?? 0) + v;
  }
  return out;
}

export const percent = (part: number, whole: number): number => (whole ? Math.round((part / whole) * 100) : 0);

/** The declarations a year in a span of whole years (the last year counts as `lastShare` of a year when it is under way). */
export const perYear = (n: number, years: number): number => Math.round(n / years);
