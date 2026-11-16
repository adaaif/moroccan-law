/** Dirhams as people say them: «421,3 مليار درهم», «643 مليون درهم». Western digits, the decimal comma. */
export function money(amount: string | number, lang: string, t: (key: string, o?: Record<string, unknown>) => string): string {
  const value = Math.abs(Number(amount));
  const locale = lang === 'fr' ? 'fr-MA' : 'ar-MA';
  const fmt = (n: number, digits: number) =>
    new Intl.NumberFormat(locale, { maximumFractionDigits: digits, minimumFractionDigits: 0 }).format(n);
  if (value >= 1e9) return t('budget.bn', { n: fmt(value / 1e9, value >= 1e10 ? 1 : 2) });
  if (value >= 1e6) return t('budget.mn', { n: fmt(value / 1e6, value >= 1e8 ? 0 : 1) });
  return t('budget.dh', { n: fmt(value, 0) });
}

/** A count with its group separator: «36.895» as the BO prints it. */
export function count(n: number, lang: string): string {
  return new Intl.NumberFormat(lang === 'fr' ? 'fr-MA' : 'ar-MA').format(n);
}

/** Shares of 100 that add up to exactly 100 (largest remainders), for the 100-dirham grid. */
export function hundred(values: number[]): number[] {
  const total = values.reduce((a, b) => a + b, 0);
  if (!total) return values.map(() => 0);
  const raw = values.map((v) => (v / total) * 100);
  const out = raw.map(Math.floor);
  let left = 100 - out.reduce((a, b) => a + b, 0);
  const order = raw.map((r, i) => [r - Math.floor(r), i] as const).sort((a, b) => b[0] - a[0]);
  for (const [, i] of order) {
    if (left-- <= 0) break;
    out[i] += 1;
  }
  return out;
}
