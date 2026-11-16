/** The direct support's amounts (F10 of the family plan), as the annex of decree 2.23.1067 fixes them, amended by
 *  decree 2.24.706: by period, for an eligible family. Eligibility is the state's (the unified social register and
 *  its threshold); the site computes the amount only. */
export type Period = '2023' | '2025' | '2026';
export const PERIODS: { key: Period; from: string }[] = [
  { key: '2023', from: '2023-12-01' }, { key: '2025', from: '2025-01-01' }, { key: '2026', from: '2026-01-01' },
];
export const periodOn = (iso: string): Period => [...PERIODS].reverse().find((p) => iso >= p.from)?.key ?? '2023';

/** Monthly, per child, by rank and schooling; the supplement per disabled or fatherless child (at most three); the
 *  September grant per schooled child; the floor per family; the flat aid. In dirhams. */
export const AMOUNTS: Record<Period, { first: { schooled: number; notSchooled: number }; later: { schooled: number; notSchooled: number }; supplement: number }> = {
  '2023': { first: { schooled: 200, notSchooled: 150 }, later: { schooled: 36, notSchooled: 24 }, supplement: 150 },
  '2025': { first: { schooled: 250, notSchooled: 175 }, later: { schooled: 36, notSchooled: 24 }, supplement: 125 },
  '2026': { first: { schooled: 300, notSchooled: 200 }, later: { schooled: 36, notSchooled: 24 }, supplement: 100 },
};
export const SEPTEMBER = { primary: 200, upper: 300 };
export const FLOOR = 500;
export const FLAT = 500;
export const MAX_CHILDREN = 6;
export const MAX_SUPPLEMENT = 3;
export const SOURCES = {
  annex: { path: '/ma/decret/2-23-1067/art_12', label: 'المرسوم 2.23.1067، الملحق' },
  floor: { path: '/ma/decret/2-23-1067/art_2', label: 'المرسوم 2.23.1067، المادة 2' },
  law: { path: '/ma/loi/58-23/art_2', label: 'القانون 58.23، المادة 2' },
  cumul: { path: '/ma/loi/58-23/art_5', label: 'القانون 58.23، المادة 5' },
};

export type Child = { status: 'schooled' | 'notSchooled'; level: 'none' | 'primary' | 'upper'; disabled: boolean; orphan: boolean };

export type Support = {
  first: { schooled: number; notSchooled: number }; later: { schooled: number; notSchooled: number };
  supplement: number; monthly: number; raised: boolean; flat: boolean; september: { primary: number; upper: number; total: number };
};

/** The monthly amount for children listed from the eldest: the first three at the higher rate, the fourth to the sixth
 *  at the lower; a supplement for each disabled or fatherless child under 6 or studying, three at most; never under
 *  the floor; the flat aid when there is no child under 21. */
export function support(children: Child[], period: Period): Support {
  const a = AMOUNTS[period];
  const kids = children.slice(0, MAX_CHILDREN);
  const first = { schooled: 0, notSchooled: 0 }, later = { schooled: 0, notSchooled: 0 };
  kids.forEach((c, i) => { (i < 3 ? first : later)[c.status] += 1; });
  const supplement = Math.min(MAX_SUPPLEMENT, kids.filter((c) => (c.disabled || c.orphan) && c.status === 'schooled').length);
  let monthly = first.schooled * a.first.schooled + first.notSchooled * a.first.notSchooled
    + later.schooled * a.later.schooled + later.notSchooled * a.later.notSchooled + supplement * a.supplement;
  const flat = kids.length === 0;
  if (flat) monthly = FLAT;
  const raised = !flat && monthly < FLOOR;
  if (raised) monthly = FLOOR;
  const primary = kids.filter((c) => c.level === 'primary').length, upper = kids.filter((c) => c.level === 'upper').length;
  return { first, later, supplement, monthly, raised, flat,
           september: { primary, upper, total: primary * SEPTEMBER.primary + upper * SEPTEMBER.upper } };
}
