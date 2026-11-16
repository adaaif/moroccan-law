import { addDays, addMonths, addYears } from '../../papers/rules/dates.ts';

/** The company's year: from its creation, the register, the tax declaration and the capital's balance; from the close
 *  of its financial year, the tax return and the assembly. Pure. */
export const ARTICLES = {
  register: '/ma/loi/15-95/art_75',
  declare: '/ma/code/cgi/art_148',
  capital: '/ma/loi/5-96/art_51',
  taxReturn: '/ma/code/cgi/art_20',
  assembly: '/ma/loi/5-96/art_70',
  losses: '/ma/loi/5-96/art_86',
} as const;

export type Stop = { key: 'created' | 'declare' | 'register' | 'capital' | 'close' | 'taxReturn' | 'papers' | 'assembly'; date: string; path: string };

/** A creation's limits: the tax declaration within 30 days (tax code art. 148), the register within three months
 *  (15.95 art. 75); once registered, the rest of the cash contributions within five years (5.96 art. 51). */
export function fromCreation(created: string, registered: string | null): Stop[] {
  const out: Stop[] = [
    { key: 'created', date: created, path: ARTICLES.register },
    { key: 'declare', date: addDays(created, 30), path: ARTICLES.declare },
    { key: 'register', date: addMonths(created, 3), path: ARTICLES.register },
  ];
  if (registered) out.push({ key: 'capital', date: addYears(registered, 5), path: ARTICLES.capital });
  return out;
}

/** A year's close: the tax return within three months (tax code art. 20), the assembly within six (5.96 art. 70), the
 *  papers sent to the partners fifteen days before it at least, here before its last day. */
export function fromClose(close: string): Stop[] {
  const assembly = addMonths(close, 6);
  return [
    { key: 'close', date: close, path: ARTICLES.assembly },
    { key: 'taxReturn', date: addMonths(close, 3), path: ARTICLES.taxReturn },
    { key: 'papers', date: addDays(assembly, -15), path: ARTICLES.assembly },
    { key: 'assembly', date: assembly, path: ARTICLES.assembly },
  ];
}
