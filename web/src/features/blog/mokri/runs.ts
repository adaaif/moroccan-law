/** The plain arithmetic of «محمد المقري» (post 25), kept apart from the drawing so it can be tested: the Residents General
 *  as runs of years, and a year's texts. */
export type Year = { year: number; dahir: number; order: number; other: number; resident: string | null };

export const texts = (y: Year): number => y.dahir + y.order + y.other;

/** The years each Resident General is the one most named, as runs: [key, first year, last year]. */
export function runs(years: Year[]): [string, number, number][] {
  const out: [string, number, number][] = [];
  for (const y of years) {
    if (!y.resident) continue;
    const last = out[out.length - 1];
    if (last && last[0] === y.resident && last[2] === y.year - 1) last[2] = y.year; else out.push([y.resident, y.year, y.year]);
  }
  return out;
}
