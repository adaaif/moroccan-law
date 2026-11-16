/** «شحال بقا ليا من نقطة؟» (R12 of the road plan): a simulator, never anyone's real balance (that is NARSA's to tell).
 *  Law 52.05: 20 points on probation (art. 23), 30 after (art. 27); points by art. 99's rows, several offences found at
 *  once capped by art. 100; at zero the licence is cancelled (arts 22, 24, 34); points come back by art. 35 (and 33 on
 *  probation). */

export type Licence = 'probation' | 'full';
export type Picked = { points: number; delit: boolean; aggravated?: boolean };

export const START: Record<Licence, number> = { probation: 20, full: 30 };

/** What one stop costs (art. 100): several délits, 16 at most when one of them is an aggravated homicide or injury
 *  (rows 1, 3, 5), else 10; several contraventions, 8; several offences with one délit among them, 14. */
export function atOnce(picked: Picked[]): { total: number; cap: number | null } {
  const sum = picked.reduce((s, p) => s + p.points, 0);
  if (picked.length < 2) return { total: sum, cap: null };
  const delits = picked.filter((p) => p.delit);
  const cap = delits.length > 1 ? (delits.some((p) => p.aggravated) ? 16 : 10) : delits.length === 1 ? 14 : 8;
  return { total: Math.min(sum, cap), cap: sum > cap ? cap : null };
}

export type Back = { years: number; balance: number; rule: 'plus4' | 'to12' | 'full' };

/** The balance after one, two and three years without an offence that takes points, counted from the last fine paid
 *  or conviction (art. 35): +4, then 12 if it is under 8, then art. 27's full 30, the probation's 20 being over by then.
 *  Only the years that change the balance: with 28 of 30 left, one year gives the 30 and the other rows said nothing
 *  new («30 · 30 · 30»). */
export function comesBack(balance: number, max: number): Back[] {
  if (balance <= 0) return [];
  const one = Math.min(max, balance + 4);
  const two = one < 8 ? Math.min(max, 12) : one;
  const rows: Back[] = [{ years: 1, balance: one, rule: 'plus4' }, { years: 2, balance: two, rule: 'to12' },
                        { years: 3, balance: START.full, rule: 'full' }];
  let last = balance;
  return rows.filter((r) => (r.balance > last ? ((last = r.balance), true) : false));
}

/** The balance a reader would have after `years` (0 to 3) without an offence that takes points (art. 35), and with
 *  the road-safety course's +4 once, never above the maximum (arts 33, 35). */
export function balanceAfter(balance: number, max: number, years: number, course = false): number {
  if (balance <= 0) return 0;
  const reached = comesBack(balance, max).filter((r) => r.years <= years).pop()?.balance ?? balance;
  const top = years >= 3 ? START.full : max;
  return Math.min(top, reached + (course ? 4 : 0));
}
