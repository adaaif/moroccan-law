/** Citations in the numbers of the book a case is counted by (IR27 of the inheritance review). The engine's come
 *  that way already. The screens write theirs in today's numbers: `inBook` says them in the book's, so a death of
 *  1990 never shows an article of 2004 under the 1958 code's name. Pure. */
import { RULES, citeIn, type Cite, type Rules } from './engine.ts';

/** The 1958 code's books 5 and 6 are today's articles 277 to 395; an article from elsewhere (art. 49 on what a couple
 *  acquired) has no place in it and is left out. */
export function inBook(code: Rules['code'], today: Cite[]): Cite[] {
  const rules = RULES.find((r) => r.code === code);
  if (!rules || rules.code !== '1958') return today;
  return today.filter((c) => (typeof c === 'number' ? c : c[0]) >= 277).map((c) => citeIn(rules, c));
}

/** Where the rest goes when no heir takes it: art. 349 §6 today; in the 1958 book the agnates' list ends at the
 *  uncles (art. 246) and what the code does not say follows the Maliki rite (art. 297). */
export const treasuryCites = (code: Rules['code']): Cite[] => (code === '1958' ? [246, 297] : [[349, 6]]);
