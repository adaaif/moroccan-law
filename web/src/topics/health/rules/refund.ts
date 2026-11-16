/** «شحال غادي يرجع ليك؟» (S17 of the health review): what the AMO pays back on a care and what stays with the
 *  insured, from the rates of the reader's fund (the topic's rates.yaml: decree 2.05.737 for the CNSS, 2.05.736 for the
 *  CNOPS). The reference is a medicine's public price (law 65.00, art. 12), or the national reference tariff for other
 *  care: when the price paid is above that tariff, the fund pays its rate on the tariff, so less. Pure: `npm run
 *  test:health`. */

export type Fund = 'cnss' | 'cnops';
export type Kind = 'medicine' | 'care' | 'hospital';
export type Place = 'public' | 'private';
/** No long illness; a serious or long-term one (the order 2518-05 list); a particularly costly treatment (its art. 2). */
export type Long = 'no' | 'long' | 'costly';
export type Rates = { care: number; medicine: number; hospital: number; public_hospital: number; long_public: number; long_private: number; share_cap: number };

export type Refund = { rate: number; back: number; left: number; why: 'base' | 'public' | 'long-public' | 'cap' | 'costly' };

const round2 = (x: number) => Math.round(x * 100) / 100;

/** The rate that applies and the two amounts. A long illness raises the CNSS's rate in a public hospital (2.05.737 art. 2)
 *  and caps the CNOPS insured's share at 10 % (2.05.736 art. 2, waived entirely for costly treatment). */
export function refund(price: number, fund: Fund, kind: Kind, place: Place, long: Long, r: Rates): Refund {
  let rate = kind === 'medicine' ? r.medicine : kind === 'hospital' ? (place === 'public' ? r.public_hospital : r.hospital) : r.care;
  let why: Refund['why'] = kind === 'hospital' && place === 'public' && fund === 'cnops' ? 'public' : 'base';
  if (long !== 'no') {
    if (fund === 'cnss' && place === 'public' && kind !== 'medicine') { rate = Math.max(rate, r.long_public); why = 'long-public'; }
    if (fund === 'cnops') {
      if (long === 'costly') { rate = 100; why = 'costly'; } else if (100 - rate > r.share_cap) { rate = 100 - r.share_cap; why = 'cap'; }
    }
  }
  const p = Math.max(0, price);
  const back = round2((p * rate) / 100);
  return { rate, back, left: round2(p - back), why };
}

/** The fund of a reader's answer to the topic's question: the civil servants' CNOPS, every other regime at the CNSS. */
export const fundOf = (answer: string | null): Fund => (answer === 'cnops' ? 'cnops' : 'cnss');
