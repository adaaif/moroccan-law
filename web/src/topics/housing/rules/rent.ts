/** «واش الزيادة قانونية؟» (H10 of the housing plan): the earliest day a rent may go up and by how much at most, and the
 *  deposit's cap and return date, each with its article. Law 67.12 for homes and professional premises, law 07.03 for
 *  shops (kept for them by 67.12 art. 75). Computed on the phone; the rates come from rates.yaml. */
import { due } from '../../kit/dates.ts';

export type Kind = 'home' | 'professional' | 'commercial';
export type RentInput = { kind: Kind; rent: number; proposed: number; since: string; on: string };
export type Verdict = 'within' | 'tooEarly' | 'tooHigh' | 'none';
export type RentResult = {
  rate: number; earliest: string; open: boolean; max: number; small: boolean; courtMax: number;
  increase: number; verdict: Verdict; cites: string[];
};

const lease = (n: number) => `/ma/loi/67-12/art_${n}`;
const revision = (n: number) => `/ma/loi/7-03/art_${n}`;
const round2 = (x: number) => Math.round(x * 100) / 100;
export const plus = (on: string, p: { months?: number; days?: number }) => due(on, { key: '', path: '', label: '', ...p });

/** Arts 32–35 of 67.12 (07.03 arts 2–5 for shops): no rise within three years of the contract or the last revision,
 *  then at most 8% for a home and 10% for other premises; on a rent of 400 DH a month or less, a court may set more,
 *  up to 50%. `proposed` 0 asks only for the figures. */
export function rentCheck(i: RentInput, r: Record<string, number>): RentResult {
  const rate = i.kind === 'home' ? r.home : i.kind === 'professional' ? r.professional : r.commercial;
  const earliest = plus(i.since, { months: 12 * r.years });
  const open = i.on >= earliest;
  const small = i.rent > 0 && i.rent <= r.small_rent;
  const increase = i.rent > 0 && i.proposed > 0 ? round2(((i.proposed - i.rent) / i.rent) * 100) : 0;
  // No rent, no rise to measure (PX37 of the where-it-trips review: 3,000 DH on nothing read «within the law», 0 %).
  const verdict: Verdict = !i.rent || !i.proposed || i.proposed <= i.rent ? 'none' : !open ? 'tooEarly' : increase > rate ? 'tooHigh' : 'within';
  const cites = i.kind === 'commercial'
    ? ['/ma/loi/49-16/art_5', revision(2), revision(3), revision(4), ...(small ? [revision(5)] : [])]
    : [lease(32), lease(33), lease(34), ...(small ? [lease(35)] : [])];
  return { rate, earliest, open, max: round2(i.rent * (1 + rate / 100)), small, courtMax: round2(i.rent * (1 + r.small_cap / 100)),
           increase, verdict, cites };
}

export type DepositResult = { max: number; over: boolean; returnBy: string | null; cites: string[] };

/** Art. 20 of 67.12: a deposit of two months' rent at most, returned within a month of the premises' return, less what
 *  is owed and proven. */
export function depositCheck(rent: number, deposit: number, returned: string, d: Record<string, number>): DepositResult {
  return { max: round2(rent * d.max_months), over: deposit > rent * d.max_months,
           returnBy: returned ? plus(returned, { months: d.return_months }) : null, cites: [lease(20)] };
}
