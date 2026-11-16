import { ending } from '../../kit/dates.ts';

/** The request a person sends a company about their data (law 09.08): the rights it asks, each with its article, and,
 *  for a correction, the ten full days the company has (art. 8: neither the day of receipt nor the last day counts, a day
 *  off at the end moves it). The words of the letter live in the locales; this gives what they say. Pure. */
export type Right = 'access' | 'rectify' | 'erase' | 'oppose' | 'prospect';
export const RIGHTS: Right[] = ['access', 'rectify', 'erase', 'oppose', 'prospect'];
export const PATHS: Record<Right, string> = {
  access: '/ma/loi/9-08/art_7', rectify: '/ma/loi/9-08/art_8', erase: '/ma/loi/9-08/art_8',
  oppose: '/ma/loi/9-08/art_9', prospect: '/ma/loi/9-08/art_10',
};
export const REFUSAL = { cndp: '/ma/loi/9-08/art_28', fine: '/ma/loi/9-08/art_53' } as const;

/** The last day to correct or erase, from the day the company received the request. */
export function correctBy(received: string): string {
  return ending(received, { key: 'rectify', path: PATHS.rectify, label: '', days: 10, complete: true }).date;
}

/** The articles a letter asking these rights names, in the law's order. */
export function articles(rights: Right[]): string[] {
  return [...new Set(RIGHTS.filter((r) => rights.includes(r)).map((r) => PATHS[r]))];
}
