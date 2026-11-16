/** The plain arithmetic of «القانون يعرف البرقية، ولا يعرف واتساب» (post 19), kept apart from the drawing so it can be
 *  tested: a share as each language writes it, the word «نص» after a number as Arabic agrees it, a decade's name, the
 *  year a way of writing to the Mediator first passed another, and where a bar of decades peaks. */

/** «⁦61,7٪⁩» on an Arabic page (the sign right of the number, the pair kept left to right), «61,7 %» in French. */
export function share(v: string, lang: string): string {
  const shown = String(Number(v)).replace('.', ',');
  return lang === 'fr' ? `${shown}\u202f%` : `\u2066${shown}٪\u2069`;
}

/** The noun after a count of texts: «نص واحد», «نصان», «3 نصوص», «11 نصا», «0 نص»; French by its plural. */
export function textsKey(n: number): 'zero' | 'one' | 'two' | 'few' | 'many' {
  if (n === 0) return 'zero';
  if (n === 1) return 'one';
  if (n === 2) return 'two';
  const r = n % 100;
  return r >= 3 && r <= 10 ? 'few' : 'many';
}

/** The first year the second way passed the first (WhatsApp over the fax): null when it never did. */
export function passed(years: { year: number; a: number; b?: number }[]): number | null {
  return years.find((y) => (y.b ?? 0) > y.a)?.year ?? null;
}

/** The decade a bar of decades peaks at, and its count; the first of equal peaks. */
export function peak(decades: number[], counts: number[]): { decade: number; n: number } {
  let at = 0;
  counts.forEach((c, i) => { if (c > counts[at]) at = i; });
  return { decade: decades[at], n: counts[at] };
}

/** The last decade a word was written in, null when never. */
export function lastDecade(decades: number[], counts: number[]): number | null {
  for (let i = counts.length - 1; i >= 0; i -= 1) if (counts[i] > 0) return decades[i];
  return null;
}
