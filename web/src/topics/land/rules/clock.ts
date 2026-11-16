import { ending, type Deadline } from '../../kit/dates.ts';

/** The land's clock (the land review, M11): the papers that start a limit, each with what it is for, the day it
 *  counts from and its articles. Pure; the page asks the day, this says the last one. Counted as the kit counts: days
 *  from the next day, months to the same date. Where a law calls its periods «كاملة» (law 7.81, ch. 48: neither the
 *  day it starts nor the one it ends) the limit is `complete` and a last day off moves to the next working day. The
 *  tool waits for a person's check (C3 «wait») before readers see it. */
export type Paper = 'oppose' | 'inquiry' | 'preempt' | 'preempt-year' | 'share' | 'fraud';
export const PAPERS: Paper[] = ['oppose', 'inquiry', 'preempt', 'preempt-year', 'share', 'fraud'];

export type Limit = { paper: Paper; deadline: Deadline; journey: string; after?: { path: string } };

const L = (paper: Paper, d: Omit<Deadline, 'key' | 'label'>, journey: string, after?: string): Limit =>
  ({ paper, deadline: { key: paper, label: paper, ...d }, journey, after: after ? { path: after } : undefined });

export const LIMITS: Record<Paper, Limit> = {
  // Two months from the BO's notice that the bornage is over; after them, a late opposition only at the registrar's
  // discretion while the file has not gone to court (ch. 24, 27, 29).
  oppose: L('oppose', { months: 2, path: '/ma/code/land-registration/art_27' }, 'journeys/oppose', '/ma/code/land-registration/art_29'),
  // Two months from the draft cessibility act's publication in the BO to write in the commune's register (7.81 ch. 10);
  // its periods are complete (ch. 48).
  inquiry: L('inquiry', { months: 2, complete: true, path: '/ma/loi/7-81/art_10' }, 'journeys/expropriation'),
  // Thirty full days from the buyer's notice, received in person (39.08 art. 304).
  preempt: L('preempt', { days: 30, path: '/ma/loi/39-08/art_304' }, 'journeys/preempt'),
  // Without a notice, a year from the sale's registration on the title, or its deposit on a requisition (art. 304).
  'preempt-year': L('preempt-year', { months: 12, path: '/ma/loi/39-08/art_304' }, 'journeys/preempt'),
  // Thirty days from the notice of the jemâa des naibs' decision on the use of collective land (62.17 art. 16).
  share: L('share', { days: 30, path: '/ma/loi/62-17/art_16' }, 'journeys/collective'),
  // Four years from the entry on the title that fraud or forgery harmed (39.08 art. 2).
  fraud: L('fraud', { months: 48, path: '/ma/loi/39-08/art_2' }, 'journeys/fraud'),
};

/** The last day of a paper's limit, from the day it counts from, with the holidays a complete limit was moved past. */
export function lastDay(paper: Paper, from: string) {
  const limit = LIMITS[paper];
  const end = ending(from, limit.deadline);
  return { ...end, limit };
}

/** The share of the limit gone by `today` (0 to 1), for the bar. */
export function gone(from: string, last: string, today: string): number {
  const at = (d: string) => Date.parse(`${d}T12:00:00Z`);
  const total = at(last) - at(from);
  return total <= 0 ? 1 : Math.min(1, Math.max(0, (at(today) - at(from)) / total));
}
