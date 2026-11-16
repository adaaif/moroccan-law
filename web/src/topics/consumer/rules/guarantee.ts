/** «الضمان ديالي باقي؟» (T2 of the consumer plan): from the day of delivery, the legal guarantee's last day (law
 *  31.08 art. 65: one year after delivery for a movable, two for an immovable, never shortened) and the shop's own
 *  guarantee, as long as its card says, lengthened by the days the shop held the thing to repair it (art. 73). What the
 *  law lets the buyer ask is the DOC's (art. 556: the sale rescinded and the price back, no reduction if kept). */
import { due } from '../../kit/dates.ts';

export type GuaranteeInput = {
  delivered: string;
  immovable?: boolean;
  /** The shop's or maker's guarantee in months, as its card says (0: none). */
  shopMonths?: number;
  /** The days the supplier held the thing for repairs under that guarantee, from its receipts (art. 73). */
  repairDays?: number;
};
export type GuaranteeResult = {
  legalLast: string;
  shopLast: string | null;
  /** The shop's last day without the repairs, to show what art. 73 adds. */
  shopBase: string | null;
  cites: string[];
};

const art = (n: string) => `/ma/loi/31-08/art_${n}`;
const none = { key: '', path: '', label: '' };

export function guarantee(g: GuaranteeInput): GuaranteeResult {
  const legalLast = due(g.delivered, { ...none, months: g.immovable ? 24 : 12 });
  const months = Math.max(0, Math.floor(g.shopMonths ?? 0));
  const shopBase = months ? due(g.delivered, { ...none, months }) : null;
  const shopLast = months ? due(g.delivered, { ...none, months, days: Math.max(0, Math.floor(g.repairDays ?? 0)) }) : null;
  const cites = [art('65'), '/ma/code/doc/art_556'];
  if (months) cites.push(art('66'), art('73'));
  return { legalLast, shopLast, shopBase, cites };
}
