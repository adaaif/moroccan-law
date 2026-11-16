/**
 * The ages the law writes (the blog's sixteenth post), pure, so the page, the picture to share and the tests read the
 * same answers: what holds at an age, what changes at the next one, where an age stands on a line of a life, and the
 * civil servant's retirement by the year of birth.
 */

export type Side = 'start' | 'end';
export type Age = { key: string; age: number; side: Side; from: number; to?: number | null; echo?: boolean; law: string };

/** What the law says holds at `age`: each rule whose span covers it (an echo, an end already named at its start, aside). */
export const holds = <T extends Age>(items: T[], age: number): T[] =>
  items.filter((a) => !a.echo && a.from <= age && (a.to == null || age < a.to));

/** The next age where something starts or ends, and what does; null past the last. */
export function next<T extends Age>(items: T[], age: number): { age: number; items: T[] } | null {
  const later = items.filter((a) => !a.echo && a.age > age).map((a) => a.age);
  if (!later.length) return null;
  const at = Math.min(...later);
  return { age: at, items: items.filter((a) => !a.echo && a.age === at) };
}

/** The ages, in order, each with what starts and ends there. */
export function byAge<T extends Age>(items: T[]): { age: number; items: T[] }[] {
  const ages = [...new Set(items.map((a) => a.age))].sort((a, b) => a - b);
  return ages.map((age) => ({ age, items: items.filter((a) => a.age === age) }));
}

/** A line of a life from 0 to 66 years where youth takes most of the width: 0–26 on 70 %, 54–66 on the last 24 %, the
 *  years between (where the law writes one age, 40) on the 6 % left. Returns a share of the width, 0 to 1. */
export function lifeX(age: number): number {
  if (age <= 26) return (age / 26) * 0.7;
  if (age >= 54) return 0.76 + ((Math.min(age, 66) - 54) / 12) * 0.24;
  return 0.7 + ((age - 26) / 28) * 0.06;
}

/** The age at a share of the width (the inverse of lifeX), rounded to a whole year. */
export function lifeAge(x: number): number {
  const s = Math.max(0, Math.min(1, x));
  if (s <= 0.7) return Math.round((s / 0.7) * 26);
  if (s >= 0.76) return Math.round(54 + ((s - 0.76) / 0.24) * 12);
  return Math.round(26 + ((s - 0.7) / 0.06) * 28);
}

export type Step = { born: number; age: number; before?: boolean; after?: boolean };

/** The civil servant's retirement age by the year of birth (law 72.14, art. 1): its step, or the first or last for
 *  years before or after them. */
export function retireAge(steps: Step[], born: number): number {
  const exact = steps.find((s) => s.born === born);
  if (exact) return exact.age;
  return born < steps[0].born ? steps[0].age : steps[steps.length - 1].age;
}

/** «60 ½», «61»: an age of whole and half years as the law writes them (in years and six months). */
export const years = (age: number) => ({ whole: Math.floor(age), half: age % 1 !== 0 });
