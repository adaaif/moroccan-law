/** «شريت على التصميم» (H12 of the housing plan): the most a buyer may have paid at each stage, and what a late
 *  delivery gives, from the DOC's arts 618-1 to 618-20. The three works stages share 60% of the price as the contract
 *  splits them, so the tool knows only their sum. Computed on the phone; the rates come from rates.yaml. */
import { plus } from './rent.ts';

export type Stage = 'reservation' | 'preliminary' | 'start' | 'works' | 'keys';
export const STAGES: Stage[] = ['reservation', 'preliminary', 'start', 'works', 'keys'];
export type OffplanInput = {
  price: number; reserved: boolean; stage: Stage; paid: number; delivery: string; extended: boolean; notice: string; on: string;
};

const doc = (n: string) => `/ma/code/doc/art_618-${n}`;
const round2 = (x: number) => Math.round(x * 100) / 100;

/** 618-6: 5% at the reservation; 5% at the preliminary contract, or 10% without a reservation; 10% at the start of
 *  works; 60% over the three works stages; 20% at the final deed and the keys. The share of the price paid at most
 *  once a stage is reached. */
export function capAt(stage: Stage, reserved: boolean, r: Record<string, number>): number {
  const steps = [reserved ? r.reservation : 0, reserved ? r.preliminary : r.preliminary_alone, r.start, r.works, r.keys];
  return steps.slice(0, STAGES.indexOf(stage) + 1).reduce((a, b) => a + b, 0);
}

/** 618-12: one percent of the sums paid for each month of delay, at most ten percent a year, running a month after a
 *  formal notice. Months are whole months from that day to `on`. */
export function delayPenalty(paid: number, notice: string, on: string, r: Record<string, number>): { months: number; amount: number } {
  if (!notice) return { months: 0, amount: 0 };
  const from = plus(notice, { months: 1 });
  let months = 0;
  while (plus(from, { months: months + 1 }) <= on) months++;
  const full = Math.floor(months / 12) * Math.min(12 * r.penalty_month, r.penalty_year);
  const rest = Math.min((months % 12) * r.penalty_month, r.penalty_year);
  return { months, amount: round2((paid * (full + rest)) / 100) };
}

export type OffplanResult = {
  cap: number; capAmount: number; over: boolean; late: boolean; due: string; penalty: { months: number; amount: number };
  rescission: number; register: boolean; cites: Record<string, string[]>;
};

export function offplan(i: OffplanInput, r: Record<string, number>): OffplanResult {
  const cap = capAt(i.stage, i.reserved, r);
  // 618-7: the seller may push delivery back six months at most, telling the buyer a month before the date.
  const due = i.delivery ? (i.extended ? plus(i.delivery, { months: r.extension_months }) : i.delivery) : '';
  const late = Boolean(due) && i.on > due;
  return {
    cap, capAmount: round2((i.price * cap) / 100), over: i.paid > (i.price * cap) / 100 + 0.005, late, due,
    penalty: late ? delayPenalty(i.paid, i.notice, i.on, r) : { months: 0, amount: 0 },
    rescission: round2((i.paid * r.rescission) / 100),
    register: i.price > 0 && i.paid > (i.price * r.register_above) / 100,
    cites: { cap: [doc('6'), doc('8')], delay: [doc('7'), doc('12')], rescission: [doc('14')], register: [doc('10')],
             reservation: [doc('3-quater')] },
  };
}
