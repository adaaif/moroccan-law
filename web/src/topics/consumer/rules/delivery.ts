/** «الطلبية تعطلات» (T3 of the consumer plan): law 31.08 as the SGG consolidated it. With a written date (art. 12;
 *  above 3,000 dirhams, decree 2.12.503 art. 28): seven full days past it without force majeure, the consumer may end
 *  the contract without a court, within the five days after those seven (art. 13); the supplier refunds within seven
 *  days of receiving the notice, interest from the eighth (art. 14). At a distance: the order within thirty days of its
 *  confirmation (art. 39), and when the thing is not available, the money back within fifteen days of payment (art. 40).
 *  Full periods (art. 203): the starting day does not count. */
import { due } from '../../kit/dates.ts';

const none = { key: '', path: '', label: '' };
const add = (day: string, days: number) => due(day, { ...none, days });
const art = (n: string) => `/ma/loi/31-08/art_${n}`;

export const WRITTEN_DATE_ABOVE = 3000;

export type LateDated = {
  /** The first day the consumer may end the contract (the seven days past). */
  from: string;
  /** The last day to do so (five days after the seven). */
  until: string;
  /** If the supplier receives the notice on `notice`: the refund's last day, and the day interest starts. */
  refundBy: string;
  interestFrom: string;
  cites: string[];
};

export function lateDated(promised: string, notice?: string): LateDated {
  const sevenEnd = add(promised, 7);
  const from = add(sevenEnd, 1);
  const until = add(sevenEnd, 5);
  const received = notice ?? from;
  return { from, until, refundBy: add(received, 7), interestFrom: add(received, 8),
    cites: [art('12'), art('13'), art('14'), art('203'), '/ma/decret/2-12-503/art_28'] };
}

export type LateDistance = { executeBy: string; refundBy: string | null; cites: string[] };

/** At a distance: the order's last day from its confirmation, and the refund's from the payment when it is unavailable. */
export function lateDistance(confirmed: string, paid?: string): LateDistance {
  return { executeBy: add(confirmed, 30), refundBy: paid ? add(paid, 15) : null, cites: [art('39'), art('40'), art('203')] };
}

/** Whether art. 12 obliges the supplier to write the date: a price above the decree's threshold, a delivery not at once. */
export const dateRequired = (price: number) => price > WRITTEN_DATE_ABOVE;
