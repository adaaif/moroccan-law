import { ending, type Deadline } from '../../kit/dates.ts';

/** The feuille de soins' clock (S18 of the health review): the day a moment happened → the last day the law
 *  leaves. Pure; counted as the kit counts (days from the next day, months to the same date). It waits for a person's
 *  check (C4 «wait»). */
export type Moment = 'first-act' | 'end-treatment' | 'deposit' | 'refusal' | 'pregnancy';
export const MOMENTS: Moment[] = ['first-act', 'end-treatment', 'deposit', 'refusal'];

const D = (key: Moment, d: Omit<Deadline, 'key' | 'label'>): Deadline => ({ key, label: key, ...d });

export const LIMITS: Record<Exclude<Moment, 'pregnancy'>, { deadline: Deadline; journey: string }> = {
  // Two months from the first medical act to send or hand in the feuille de soins and its proofs (2.05.733 art. 12).
  'first-act': { deadline: D('first-act', { months: 2, path: '/ma/decret/2-05-733/art_12' }), journey: 'journeys/refund' },
  // Sixty days from the end of a continuous treatment (same article).
  'end-treatment': { deadline: D('end-treatment', { days: 60, path: '/ma/decret/2-05-733/art_12' }), journey: 'journeys/refund' },
  // Ninety days from the deposit for the fund to pay back, outside a dispute (2.05.733 art. 11).
  deposit: { deadline: D('deposit', { days: 90, path: '/ma/decret/2-05-733/art_11' }), journey: 'journeys/refund' },
  // A year from the refusal's notification to contest it, or the right is lost (65.00 art. 129).
  refusal: { deadline: D('refusal', { months: 12, path: '/ma/loi/65-00/art_129' }), journey: 'journeys/refused' },
};

/** The last day of a moment's limit, from the day it happened. */
export function lastDay(moment: Exclude<Moment, 'pregnancy'>, from: string) {
  const limit = LIMITS[moment];
  return { ...ending(from, limit.deadline), limit };
}

/** The share of the limit gone by `today` (0 to 1), for the bar. */
export function gone(from: string, last: string, today: string): number {
  const at = (d: string) => Date.parse(`${d}T12:00:00Z`);
  const total = at(last) - at(from);
  return total <= 0 ? 1 : Math.min(1, Math.max(0, (at(today) - at(from)) / total));
}
