/** «شحال كنتي كتسوق؟» (A2 of the road tools review): a measured speed against the limit, as law 52.05 classes it.
 *  Art. 195: a speed a device records is no offence within a margin of ten per cent, not above 7 km/h. This tool reads
 *  the ten per cent on the limit, capped at 7, and the speed kept as the recorded one less that margin: one reading of
 *  the article, call K1, for the reviewer to confirm. Then the bands of arts 185 (from +20 to under +30:
 *  2nd class, 2 points, row 28 of art. 99), 184 (from +30 to under +50: 1st class, 4 points, row 20) and 175 (+50 and
 *  over: a délit, 6 points, row 15). Under +20 the articles the tool reads name no class (call K4): it says so. */
export type Band = 'within' | 'margin' | 'under20' | 'c2' | 'c1' | 'delit';

export type SpeedResult = {
  limit: number; measured: number; margin: number; kept: number; over: number; band: Band;
  /** The fine tool's offence for the band, when there is one. */
  offence: 'speed20' | 'speed30' | null; points: number; cites: string[];
};

const code = (n: string) => `/ma/loi/52-05/art_${n}`;

export function marginFor(limit: number): number {
  return Math.min(Math.round(limit * 0.1), 7);
}

export function classify(limit: number, measured: number, radar = true): SpeedResult {
  const margin = radar ? marginFor(limit) : 0;
  const kept = measured - margin;
  const over = kept - limit;
  const base = { limit, measured, margin, kept, over };
  if (measured <= limit) return { ...base, band: 'within', offence: null, points: 0, cites: [code('195')] };
  if (over <= 0) return { ...base, band: 'margin', offence: null, points: 0, cites: [code('195')] };
  if (over < 20) return { ...base, band: 'under20', offence: null, points: 0, cites: [code('185'), code('184')] };
  if (over < 30) return { ...base, band: 'c2', offence: 'speed20', points: 2, cites: [code('185'), code('99'), code('219')] };
  if (over < 50) return { ...base, band: 'c1', offence: 'speed30', points: 4, cites: [code('184'), code('99'), code('219')] };
  return { ...base, band: 'delit', offence: null, points: 6, cites: [code('175'), code('99')] };
}

/** The limits a sign can show, and the code's own: 60 in a town, 100 outside, 120 on a motorway, 90 on probation
 *  (decree 2.10.420 arts 15 to 17), 40 and 60 for a moped (art. 19). */
export const LIMITS = [40, 60, 80, 90, 100, 120] as const;

/** Where each band starts, in recorded km/h, for the dial's colours. */
export function bandEdges(limit: number, radar = true) {
  const m = radar ? marginFor(limit) : 0;
  return { limit, margin: limit + m, c2: limit + m + 20, c1: limit + m + 30, delit: limit + m + 50 };
}
