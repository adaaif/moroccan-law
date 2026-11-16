/** The alternative sentence (the penal code arts 35-1 to 35-15, added by law 43.22): for a délit whose prison term is at
 *  most five years, not in a repeat offence nor among the offences art. 35-3 names, a court may set instead community
 *  work (three hours a day of the term, 40 to 3,600 hours, from fifteen years of age), electronic monitoring, restricted
 *  rights or measures, or a day-fine (100 to 2,000 DH a day of the term, only after a settlement, a withdrawal or the
 *  harm repaired). It says what the code opens; the court decides. Pure. */
export const ARTICLES = {
  scope: '/ma/dahir/1-59-413/art_35-1', kinds: '/ma/dahir/1-59-413/art_35-2', excluded: '/ma/dahir/1-59-413/art_35-3',
  age: '/ma/dahir/1-59-413/art_35-5', hours: '/ma/dahir/1-59-413/art_35-6', within: '/ma/dahir/1-59-413/art_35-7',
  fine: '/ma/dahir/1-59-413/art_35-14', amount: '/ma/dahir/1-59-413/art_35-15',
} as const;

/** Five years of prison, in days of 365. */
export const MAX_DAYS = 5 * 365;
export const HOURS_PER_DAY = 3;
export const HOURS = { min: 40, max: 3600 } as const;
export const DAY_FINE = { min: 100, max: 2000 } as const;

/** Art. 35-3's offences, for which no alternative is set. */
export const EXCLUDED = ['state', 'graft', 'laundering', 'military', 'drugs', 'psychotropic', 'organs', 'minors'] as const;
export type Excluded = (typeof EXCLUDED)[number];

export type Why = 'repeat' | 'excluded' | 'term';
export type Alternatives = {
  open: boolean; why: Why | null;
  /** Community work: the hours for the term, held between 40 and 3,600; open from fifteen. */
  work: { hours: number; capped: 'min' | 'max' | null; open: boolean };
  /** The day-fine's range for the term, and whether its condition is met. */
  dayFine: { min: number; max: number; open: boolean };
};

export function alternatives(days: number, repeat: boolean, excluded: boolean, age: number, settled: boolean): Alternatives {
  const why: Why | null = repeat ? 'repeat' : excluded ? 'excluded' : days > MAX_DAYS ? 'term' : null;
  const raw = days * HOURS_PER_DAY;
  const hours = Math.min(HOURS.max, Math.max(HOURS.min, raw));
  return {
    open: why === null, why,
    work: { hours, capped: raw < HOURS.min ? 'min' : raw > HOURS.max ? 'max' : null, open: why === null && age >= 15 },
    dayFine: { min: days * DAY_FINE.min, max: days * DAY_FINE.max, open: why === null && settled },
  };
}
