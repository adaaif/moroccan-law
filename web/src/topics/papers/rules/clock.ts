import { ending, type Deadline } from '../../kit/dates.ts';

/** The civil-status clock (law 36.21, decree 2.22.04): the day something happened → the last day the texts leave. A
 *  birth's or a death's declaration counts from the next day, a year abroad, from the first airport or port after a
 *  journey, and its last day off moves to the next working day (2.22.04 art. 40). Pure. */
export type Moment = 'birth' | 'death' | 'birth-abroad' | 'death-abroad' | 'travel' | 'error' | 'late';
export const MOMENTS: Moment[] = ['birth', 'death', 'birth-abroad', 'death-abroad', 'travel', 'error', 'late'];

const D = (key: Moment, d: Omit<Deadline, 'key' | 'label'>): Deadline => ({ key, label: key, ...d });

export const LIMITS: Record<Moment, { deadline: Deadline; journey: string }> = {
  // Thirty days from the next day to complete a birth's or a death's declaration (2.22.04 art. 40).
  birth: { deadline: D('birth', { days: 30, rolls: true, path: '/ma/decret/2-22-04/art_40' }), journey: 'family:journeys/birth' },
  death: { deadline: D('death', { days: 30, rolls: true, path: '/ma/decret/2-22-04/art_40' }), journey: 'family:journeys/heirs' },
  // A year for Moroccans living abroad (same article).
  'birth-abroad': { deadline: D('birth-abroad', { months: 12, rolls: true, path: '/ma/decret/2-22-04/art_40' }), journey: 'family:journeys/birth' },
  'death-abroad': { deadline: D('death-abroad', { months: 12, rolls: true, path: '/ma/decret/2-22-04/art_40' }), journey: 'family:journeys/heirs' },
  // Born or died at sea or in the air: thirty days from the day after the first airport or port (same article).
  travel: { deadline: D('travel', { days: 30, rolls: true, path: '/ma/decret/2-22-04/art_40' }), journey: 'family:journeys/birth' },
  // The central authority answers a material error's correction within fifteen days of receiving it (36.21 art. 51).
  error: { deadline: D('error', { days: 15, path: '/ma/loi/36-21/art_51' }), journey: 'journeys/correct' },
  // And a late inscription or a third person's copy within sixty days of the request (2.22.04 art. 41).
  late: { deadline: D('late', { days: 60, path: '/ma/decret/2-22-04/art_41' }), journey: 'family:journeys/birth' },
};

export function lastDay(moment: Moment, from: string) {
  const limit = LIMITS[moment];
  return { ...ending(from, limit.deadline), limit };
}

/** The share of the limit gone by `today` (0 to 1). */
export function gone(from: string, last: string, today: string): number {
  const at = (d: string) => Date.parse(`${d}T12:00:00Z`);
  const total = at(last) - at(from);
  return total <= 0 ? 1 : Math.min(1, Math.max(0, (at(today) - at(from)) / total));
}
