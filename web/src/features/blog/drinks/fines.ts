/** The order's fines (the blog's seventeenth post), pure: the articles grouped by their range, the widest first, and a
 *  sum in hours of work at the minimum wage of a day. */
export type Fine = { art: number; lo: number; hi: number; prison?: [number, number]; or?: boolean };
export type Group = { lo: number; hi: number; arts: number[]; prison: [number, number] | null };

export function groups(fines: Fine[]): Group[] {
  const out: Group[] = [];
  for (const f of fines) {
    const g = out.find((x) => x.lo === f.lo && x.hi === f.hi);
    if (g) {
      g.arts.push(f.art);
      if (f.prison && (!g.prison || f.prison[1] > g.prison[1])) g.prison = f.prison;
    } else out.push({ lo: f.lo, hi: f.hi, arts: [f.art], prison: f.prison ?? null });
  }
  return out.sort((a, b) => b.hi - a.hi || b.lo - a.lo);
}

export type Wage = { from: string; hourly: number };
export const hourlyOn = (wage: Wage[], day: string) => wage.filter((w) => w.from <= day).pop()?.hourly ?? null;
/** Dirhams in whole hours of work at the minimum wage of a day. */
export const hoursOf = (dh: number, wage: Wage[], day: string) => { const h = hourlyOn(wage, day); return h ? Math.round(dh / h) : null; };
