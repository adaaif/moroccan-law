import { addMonths, addYears } from './dates.ts';

/** When a sentence stops showing on card no. 3 (criminal procedure, law 22.01). Card no. 3 lists only custodial
 *  sentences for a crime or a misdemeanour, never one suspended nor one rehabilitation erased (art. 667); rehabilitation
 *  comes by law after the periods of art. 688 and 689, with no new custodial sentence meanwhile, or on a request after
 *  those of art. 692. Pure. */
export const ARTICLES = { card3: '/ma/loi/22-01/art_667', law: '/ma/loi/22-01/art_688', suspended: '/ma/loi/22-01/art_689', ask: '/ma/loi/22-01/art_692', after: '/ma/loi/22-01/art_702' } as const;

export type Kind = 'fine' | 'short' | 'two' | 'long' | 'felony' | 'other' | 'suspended';
export const KINDS: Kind[] = ['fine', 'short', 'two', 'long', 'felony', 'other', 'suspended'];

/** Rehabilitation by law, from the day the sentence ended (paid, served, or prescribed; a suspended one from the day
 *  it became final): months or years. */
const BY_LAW: Record<Kind, { months?: number; years?: number; path: string }> = {
  fine: { months: 6, path: ARTICLES.law },        // 6 months after the fine is paid
  short: { years: 2, path: ARTICLES.law },        // one imprisonment of 6 months at most
  two: { years: 4, path: ARTICLES.law },          // one of 2 years at most, or several of a year at most together
  long: { years: 5, path: ARTICLES.law },         // one over 2 years for a misdemeanour, or several over a year
  felony: { years: 10, path: ARTICLES.law },      // a criminal sentence, or several
  other: { years: 5, path: ARTICLES.law },        // a principal criminal penalty that is neither prison nor a fine
  suspended: { years: 1, path: ARTICLES.suspended }, // a year's test, from the day it became final
};

/** A request to the judge may come sooner (art. 692): two years after release, one for an unintentional misdemeanour
 *  or a principal penalty other than prison, at once for a fine paid, four for a criminal sentence. */
const BY_REQUEST: Partial<Record<Kind, { months?: number; years?: number }>> = {
  fine: { months: 0 }, short: { years: 2 }, two: { years: 2 }, long: { years: 2 }, felony: { years: 4 }, other: { years: 1 },
};

/** Whether the sentence ever shows on card no. 3 (art. 667): a fine or a suspended sentence never does. */
export const onCard3 = (k: Kind) => k !== 'fine' && k !== 'suspended' && k !== 'other';

export function byLaw(kind: Kind, ended: string): { date: string; path: string } {
  const p = BY_LAW[kind];
  return { date: p.months !== undefined ? addMonths(ended, p.months) : addYears(ended, p.years!), path: p.path };
}

export function byRequest(kind: Kind, ended: string): string | null {
  const p = BY_REQUEST[kind];
  if (!p) return null;
  return p.months !== undefined ? addMonths(ended, p.months) : addYears(ended, p.years!);
}
