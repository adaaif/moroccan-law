import { addDays, addYears, age } from './dates.ts';

/** The national identity card (law 04.20, decree 2.20.521): when it must be had, how long it lasts, when it must be
 *  renewed, what it costs, what a delay may cost. Pure; every figure with its article. */
export const ARTICLES = {
  duty: '/ma/loi/4-20/art_2',
  validity: '/ma/decret/2-20-521/art_1',
  renew: '/ma/loi/4-20/art_13',
  fines: '/ma/loi/4-20/art_15',
  stamp: '/ma/code/cgi/art_252',
  prints: '/ma/decret/2-20-521/art_10',
  first: '/ma/decret/2-20-521/art_3',
  again: '/ma/decret/2-20-521/art_5',
  spares: '/ma/loi/4-20/art_11',
} as const;

/** The day a Moroccan must hold the card: 16 full solar years (04.20 art. 2). */
export const dutyDay = (birth: string) => addYears(birth, 16);

/** The end of a card issued on `issued` (2.20.521 art. 1): ten years past 12 full years; before, seven years at most
 *  and never past the day before the twelfth birthday. The card prints its own date; this is the decree's rule. */
export function lastValid(birth: string, issued: string): string {
  if (age(birth, issued) >= 12) return addYears(issued, 10);
  const seven = addYears(issued, 7);
  const twelve = addDays(addYears(birth, 12), -1);
  return seven < twelve ? seven : twelve;
}

/** What the card costs on a day (tax code art. 252): 75 DH, 50 under 12 full years. */
export const stamp = (birth: string, on: string) => (age(birth, on) < 12 ? 50 : 75);

/** The events of 04.20 art. 13 that oblige a renewal, as the reader names them. */
export const EVENTS = ['moved', 'name', 'birthday', 'marital', 'lost', 'expired', 'twelve'] as const;
export type Event = (typeof EVENTS)[number];

/** The fines of 04.20 art. 15, in dirhams. */
export const FINES = { never: [300, 400], renew: [200, 300], show: [100, 150] } as const;

export type Card =
  | { state: 'none-young'; duty: string; fee: number }           // under 16, no card: possible, not yet due
  | { state: 'none-due'; duty: string; fee: number }             // 16 or more, no card: due, the fine for never asking
  | { state: 'valid'; last: string; fee: number; twelve: string | null }
  | { state: 'renew'; last: string; why: Event[]; fee: number };  // an event of art. 13, or its date passed

/** The reader's card on `today`: none (born `birth`), or one valid until `last` with the events they named. */
export function card(birth: string, today: string, last: string | null, events: Event[] = []): Card {
  const fee = stamp(birth, today);
  if (!last) return age(birth, today) >= 16 ? { state: 'none-due', duty: dutyDay(birth), fee } : { state: 'none-young', duty: dutyDay(birth), fee };
  const why: Event[] = [...events];
  if (last < today && !why.includes('expired')) why.push('expired');
  // A child's card ends the day before the twelfth birthday: renewed then, with the fingerprints (art. 13, 2.20.521 art. 10).
  const twelve = age(birth, today) < 12 ? addYears(birth, 12) : null;
  if (twelve && last >= addDays(twelve, -1) && today >= twelve && !why.includes('twelve')) why.push('twelve');
  if (why.length) return { state: 'renew', last, why, fee };
  return { state: 'valid', last, fee, twelve };
}

/** The card one would get if it were issued today. */
export const ifIssuedToday = (birth: string, today: string) => lastValid(birth, today);
