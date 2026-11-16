import { addDays, addYears } from '../../papers/rules/dates.ts';

/** How long a work is protected (law 2.00 arts 25–29): an author's work his life and seventy years after his death (art.
 *  25), a joint work the last surviving author's (art. 26); an anonymous or pseudonymous, collective, audiovisual work, or
 *  a work of applied art, seventy years from the end of the calendar year of its first lawful publication (arts 27–29).
 *  The day after, its commercial use still needs the copyright office's licence and fee (art. 7-1, law 13.26). Pure. */
export type Kind = 'author' | 'joint' | 'anonymous' | 'collective' | 'applied';
export const KINDS: Kind[] = ['author', 'joint', 'anonymous', 'collective', 'applied'];
export const PATHS: Record<Kind, string> = {
  author: '/ma/loi/2-00/art_25', joint: '/ma/loi/2-00/art_26', anonymous: '/ma/loi/2-00/art_27',
  collective: '/ma/loi/2-00/art_28', applied: '/ma/loi/2-00/art_29',
};
export const AFTER = '/ma/loi/2-00/art_1-7';
/** Whether the term runs from a death (a day) or from a publication (a year). */
export const FROM_DEATH: Record<Kind, boolean> = { author: true, joint: true, anonymous: false, collective: false, applied: false };

export type Term = { until: string; free: string; path: string };

/** `from` is the day of the death (YYYY-MM-DD) or the year of the first publication (YYYY). */
export function term(kind: Kind, from: string): Term {
  const until = FROM_DEATH[kind] ? addYears(from, 70) : `${Number(from.slice(0, 4)) + 70}-12-31`;
  return { until, free: addDays(until, 1), path: PATHS[kind] };
}
