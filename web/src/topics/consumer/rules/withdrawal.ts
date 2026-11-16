/** «واش نقدر نرجعها؟» (T1 of the consumer plan): by where it was bought, the last day to withdraw and what follows.
 *  Law 31.08 as the SGG consolidated it: art. 36 (seven full days from receipt, thirty without written confirmation;
 *  from the offer's acceptance for a service), 37 (refund within fifteen days), 38 (the exceptions), 49–50 (door sales:
 *  seven days from the order, nothing paid before), 85 (credit: seven days from acceptance), 97 (the linked sale ended),
 *  65 (in a shop, the guarantee only). Every period of the law is a full one (art. 203): the day of the event does not
 *  count, so the last day is the event's day plus the period. */
import { due } from '../../kit/dates.ts';

export type Channel = 'online' | 'door' | 'credit' | 'shop';
export type ReturnInput = {
  channel: Channel;
  /** The day that starts the period: receipt (online goods), acceptance (online service, credit), order (door). */
  day: string;
  /** Online: did a written confirmation of the offer's information arrive (arts 29, 32)? */
  confirmed?: boolean;
  /** Online: a service rather than goods (the period runs from acceptance). */
  service?: boolean;
  /** Online: one of art. 38's cases (made to measure, perishable, opened software, newspapers, a service begun). */
  excluded?: boolean;
};
export type ReturnResult =
  | { kind: 'window'; days: number; last: string; from: 'receipt' | 'acceptance' | 'order'; refundDays?: number; cites: string[] }
  | { kind: 'excluded'; cites: string[] }
  | { kind: 'shop'; guaranteeLast: string; cites: string[] };

const art = (n: string) => `/ma/loi/31-08/art_${n}`;

export function canReturn(r: ReturnInput): ReturnResult {
  const full = art('203');
  if (r.channel === 'shop') {
    // No withdrawal in a shop: the legal guarantee, a year after delivery for a movable (art. 65).
    return { kind: 'shop', guaranteeLast: due(r.day, { key: '', path: '', label: '', months: 12 }), cites: [art('36'), art('65')] };
  }
  if (r.channel === 'online' && r.excluded) return { kind: 'excluded', cites: [art('38'), art('42')] };
  if (r.channel === 'online') {
    const days = r.confirmed === false ? 30 : 7;
    return { kind: 'window', days, last: due(r.day, { key: '', path: '', label: '', days }), from: r.service ? 'acceptance' : 'receipt',
      refundDays: 15, cites: [art('36'), art('37'), art('32'), full] };
  }
  if (r.channel === 'door') {
    return { kind: 'window', days: 7, last: due(r.day, { key: '', path: '', label: '', days: 7 }), from: 'order', refundDays: 15,
      cites: [art('49'), art('50'), art('47'), full] };
  }
  return { kind: 'window', days: 7, last: due(r.day, { key: '', path: '', label: '', days: 7 }), from: 'acceptance',
    cites: [art('85'), art('97'), art('87'), full] };
}

/** The days of the period one by one, for the strip under the answer: from the first counted day to the last. */
export function windowDays(start: string, days: number): string[] {
  return Array.from({ length: days }, (_, i) => due(start, { key: '', path: '', label: '', days: i + 1 }));
}
