/** The fines' figures as rates.yaml holds them, shipped with the tools (F8 of the road tools review): the fine works
 *  with no network at the roadside, then takes the server's row when it answers. back/apps/topics/tests/test_road.py
 *  fails when this copy and rates.yaml's newest row part ways. */
import { useRates, inForce } from '../../kit/api';

export const FINES_FROM = '2016-08-11';
export const FINES: Record<string, number> = {
  c1_day: 400, c1_15: 500, c1_30: 700, c1_min: 700, c1_max: 1400,
  c2_day: 300, c2_15: 350, c2_30: 500, c2_min: 500, c2_max: 1000,
  c3_day: 150, c3_15: 200, c3_30: 300, c3_min: 300, c3_max: 600,
  walk_30: 25, walk_min: 20, walk_max: 50,
};

/** The fines in force on a day: the server's row once it has answered, this copy before and without it. */
export function useFines(slug: string, day: string): { values: Record<string, number>; from: string } {
  const q = useRates(slug, 'fines');
  const row = q.data ? inForce(q.data.rows, day) : undefined;
  return row ? { values: row.values, from: row.from } : { values: FINES, from: FINES_FROM };
}
