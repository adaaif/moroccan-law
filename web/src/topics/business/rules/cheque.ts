import { addDays, addMonths, addYears } from '../../papers/rules/dates.ts';

/** The cheque's dates and sums (the commerce code as law 71.24 left it, BO 7478, 29 Jan 2026). Pure. */
export const ARTICLES = {
  present: '/ma/loi/15-95/art_268',
  injunction: '/ma/loi/15-95/art_313',
  fine: '/ma/loi/15-95/art_314',
  prescription: '/ma/loi/15-95/art_295',
  penalty: '/ma/loi/15-95/art_316',
  notice: '/ma/loi/15-95/art_325',
} as const;

export type Where = 'morocco' | 'abroad';
/** 20 days to present a cheque issued in Morocco, 60 one issued abroad, from the date written on it (art. 268). */
export const PRESENT: Record<Where, number> = { morocco: 20, abroad: 60 };

export function presentBy(written: string, where: Where): string {
  return addDays(written, PRESENT[where]);
}

export type Stop = { key: 'written' | 'present' | 'rejected' | 'injunction' | 'free' | 'recover' | 'drawer' | 'bank'; date: string; path: string };

/** The cheque's road. The bank's injunction comes within two days of the rejection (art. 313); the three months
 *  without a fine run from the injunction (art. 314), so from the rejection at the soonest; cheques come back to one
 *  who pays within two years of the presentation's end (art. 313); the holder's actions lapse a year after it against
 *  the drawer, two against the bank (art. 295). */
export function road(written: string, where: Where, rejected: string | null): Stop[] {
  const end = presentBy(written, where);
  const out: Stop[] = [{ key: 'written', date: written, path: ARTICLES.present }, { key: 'present', date: end, path: ARTICLES.present }];
  if (rejected) {
    out.push({ key: 'rejected', date: rejected, path: ARTICLES.injunction });
    out.push({ key: 'injunction', date: addDays(rejected, 2), path: ARTICLES.injunction });
    out.push({ key: 'free', date: addMonths(rejected, 3), path: ARTICLES.fine });
  }
  out.push({ key: 'recover', date: addYears(end, 2), path: ARTICLES.injunction });
  out.push({ key: 'drawer', date: addYears(end, 1), path: ARTICLES.prescription });
  out.push({ key: 'bank', date: addYears(end, 2), path: ARTICLES.prescription });
  return out.sort((a, b) => (a.date < b.date ? -1 : a.date > b.date ? 1 : 0));
}

/** The fine to issue cheques again (art. 314): 0.5 % of the unpaid sum for the first injunction, 1 % the second, 1.5 %
 *  the third and after; on the shortfall alone; 500 DH at least, 50,000 at most; nothing when paid within three months
 *  of the injunction. */
export const RATE = [0.005, 0.01, 0.015] as const;
export function recoveryFine(shortfall: number, injunction: 1 | 2 | 3, withinThreeMonths: boolean): number {
  if (withinThreeMonths || shortfall <= 0) return 0;
  return Math.min(50_000, Math.max(500, Math.round(shortfall * RATE[injunction - 1] * 100) / 100));
}

/** What ends a prosecution once paid (art. 325): 2 % of the cheque or the shortfall. */
export const settleFine = (shortfall: number) => Math.round(shortfall * 0.02 * 100) / 100;
