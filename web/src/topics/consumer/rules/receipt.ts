/** «فاتورة حقوقي» (the consumer-receipt review, 26 Oct 2026): one purchase in — where, what, its price, its day — and
 *  the rights it gives out, each a line of a till receipt with its date when it has one and its articles. It adds no
 *  rule of its own: the dates are the other tools' (withdrawal.ts, guarantee.ts, delivery.ts), the other lines the
 *  articles the journeys rest on. Law 31.08 as the SGG consolidated it; the DOC for the guarantee's remedies. */
import { canReturn, type Channel } from './withdrawal.ts';
import { guarantee } from './guarantee.ts';
import { dateRequired } from './delivery.ts';

export type Purchase = {
  channel: Channel;
  /** Goods, or a service (a service bought at a distance runs its period from the acceptance; it has no guarantee). */
  service?: boolean;
  /** The day that starts the purchase's periods: delivery (a shop, goods online), order (a door sale), acceptance
   *  (a service online, a credit). */
  day: string;
  price: number;
  /** Online: a written confirmation of the offer's information arrived (art. 32). */
  confirmed?: boolean;
  /** Online: one of art. 38's cases (made to measure, perishable, opened software, newspapers, a service begun). */
  excluded?: boolean;
  /** The shop's own guarantee in months, as its card says (0: none). */
  shopMonths?: number;
};

export type LineKey = 'withdraw' | 'noWithdraw' | 'excluded' | 'refund' | 'linkedSale' | 'guarantee' | 'shopGuarantee'
  | 'noReturnStamp' | 'invoice' | 'price' | 'writtenDate' | 'earlyRepayment' | 'defaultCap' | 'court';
/** A line of the receipt: a right, the day it runs to when it has one, its articles. `days` and `months` say the
 *  period for the line's words. */
export type Line = { key: LineKey; last?: string; days?: number; months?: number; cites: string[] };

const art = (n: string) => `/ma/loi/31-08/art_${n}`;

export function receipt(p: Purchase): Line[] {
  const lines: Line[] = [];
  const r = canReturn({ channel: p.channel, day: p.day, confirmed: p.confirmed, service: p.service, excluded: p.excluded });
  if (r.kind === 'window') {
    lines.push({ key: 'withdraw', last: r.last, days: r.days, cites: r.cites });
    if (p.channel === 'credit') lines.push({ key: 'linkedSale', cites: [art('97')] });
    else lines.push({ key: 'refund', days: 15, cites: p.channel === 'door' ? [art('50')] : [art('37')] });
  } else if (r.kind === 'excluded') {
    lines.push({ key: 'excluded', cites: r.cites });
  } else {
    lines.push({ key: 'noWithdraw', cites: [art('36'), art('49')] });
  }
  // Goods carry the legal guarantee from delivery, whatever the channel; a credit buys goods too.
  if (!p.service) {
    const g = guarantee({ delivered: p.day, shopMonths: p.shopMonths });
    lines.push({ key: 'guarantee', last: g.legalLast, months: 12, cites: [art('65'), '/ma/code/doc/art_556'] });
    if (g.shopLast) lines.push({ key: 'shopGuarantee', last: g.shopLast, months: p.shopMonths, cites: [art('66'), art('73')] });
    lines.push({ key: 'noReturnStamp', cites: [art('65'), '/ma/code/doc/art_571'] });
  }
  lines.push({ key: 'invoice', cites: [art('4'), '/ma/decret/2-12-503/art_25'] });
  lines.push({ key: 'price', cites: [art('5')] });
  if (p.channel !== 'credit' && dateRequired(p.price)) lines.push({ key: 'writtenDate', cites: [art('12'), '/ma/decret/2-12-503/art_28'] });
  if (p.channel === 'credit') {
    lines.push({ key: 'earlyRepayment', cites: [art('103')] });
    lines.push({ key: 'defaultCap', cites: [art('104'), art('105')] });
  }
  lines.push({ key: 'court', cites: [art('202')] });
  return lines;
}

/** The soonest day still ahead among the lines that have one (on `today`, a line ending today still counts). */
export function nextLast(lines: Line[], today: string): Line | null {
  return lines.filter((l) => l.last && l.last >= today).sort((a, b) => (a.last! < b.last! ? -1 : 1))[0] ?? null;
}
