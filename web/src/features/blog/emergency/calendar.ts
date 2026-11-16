/** The plain arithmetic of «حالة الطوارئ الصحية» (post 27), kept apart from the drawing so it can be tested: the terms as
 *  spans of days, cut at each year's end for a calendar of one row a year, and the days the emergency lasted. */
export type Term = { key: string; from: string; to: string };

const ms = (iso: string) => Date.parse(`${iso}T00:00:00Z`);
export const days = (from: string, to: string): number => Math.round((ms(to) - ms(from)) / 86400000);

/** Where a day falls in its year, from 0 (1 January) to 1 (the next 1 January). */
export function inYear(iso: string): number {
  const y = Number(iso.slice(0, 4));
  return (ms(iso) - Date.UTC(y, 0, 1)) / (Date.UTC(y + 1, 0, 1) - Date.UTC(y, 0, 1));
}

/** A term's pieces, one per year it touches: [year, start share, end share]. */
export function pieces(t: Term): [number, number, number][] {
  const a = Number(t.from.slice(0, 4)), b = Number(t.to.slice(0, 4));
  const out: [number, number, number][] = [];
  for (let y = a; y <= b; y += 1) out.push([y, y === a ? inYear(t.from) : 0, y === b ? inYear(t.to) : 1]);
  return out;
}
