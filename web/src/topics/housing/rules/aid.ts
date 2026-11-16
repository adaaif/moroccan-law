/** «دعم السكن» (H13 of the housing plan): the direct aid's conditions read one by one, the amount by the price, and the
 *  dates that follow the purchase. Finance law 50.22 art. 8 as amended by the finance laws for 2024 and 2026, decree
 *  2.23.350 as amended by decree 2.26.578. Computed on the phone; the figures come from rates.yaml. */
import { plus } from './rent.ts';

export type Owns = 'no' | 'indivision' | 'yes';
export type AidInput = {
  moroccan: boolean; before: boolean; owns: Owns; price: number; permit: string; rooms: number; firstSale: boolean;
  deed: string; on: string;
};
export type Condition = { key: string; met: boolean; cites: string[] };
export type AidResult = { conditions: Condition[]; eligible: boolean; amount: number; band: 'low' | 'high' | 'over';
  until: string | null; deedDays: number; cites: string[] };

// Art. 8 of the 2023 finance law as the site shows it (first published), and the articles of the 2024 and 2026 finance laws
// that amended it, which the machine could not place into it.
const LAW = '/ma/loi/50-22/art_8';
const LF2024 = '/ma/loi/55-23/art_10';
const LF2026 = '/ma/loi/50-25/art_8';
const DECREE = (n: string) => `/ma/decret/2-23-350/art_${n}`;
export const PERMIT_FROM = '2023-01-01';
export const INDIVISION_FROM = '2026-01-01';

export function aid(i: AidInput, r: Record<string, number>): AidResult {
  const band = i.price <= r.low_price ? 'low' : i.price <= r.high_price ? 'high' : 'over';
  const conditions: Condition[] = [
    { key: 'moroccan', met: i.moroccan, cites: [LAW] },
    { key: 'never', met: !i.before, cites: [LAW] },
    // Owning a share in indivision no longer bars the aid since the 2026 finance law.
    { key: 'noHome', met: i.owns === 'no' || (i.owns === 'indivision' && i.on >= INDIVISION_FROM), cites: [LAW, LF2026] },
    { key: 'price', met: i.price > 0 && band !== 'over', cites: [DECREE('2')] },
    { key: 'permit', met: Boolean(i.permit) && i.permit >= PERMIT_FROM, cites: [LAW, LF2024] },
    { key: 'rooms', met: i.rooms >= 2, cites: [LAW, LF2024] },
    { key: 'firstSale', met: i.firstSale, cites: [LAW, LF2024] },
  ];
  const eligible = conditions.every((c) => c.met);
  return {
    conditions, eligible, band, amount: eligible ? (band === 'low' ? r.low_aid : r.high_aid) : 0,
    // Five years as the main home from the final deed; then the mortgage may be lifted.
    until: i.deed ? plus(i.deed, { months: 12 * r.years }) : null,
    deedDays: r.deed_days, cites: [LAW, LF2024, LF2026, DECREE('2'), DECREE('6')],
  };
}
