import { addDays } from './dates.ts';

/** The administration's clock (law 55.19): the day a complete file was deposited, or a refusal received → the day it
 *  must answer, the last day to appeal, the day the appeal must be answered. Its limits are complete (art. 31): neither
 *  the day it starts from nor its last day counts, so `n` days end on the start + n + 1. Pure. */
export const ARTICLES = {
  receipt: '/ma/loi/55-19/art_10',
  limit: '/ma/loi/55-19/art_16',
  appeal: '/ma/loi/55-19/art_21',
  silence: '/ma/loi/55-19/art_19',
  deliver: '/ma/loi/55-19/art_20',
  complete: '/ma/loi/55-19/art_31',
} as const;

const complete = (from: string, days: number) => addDays(from, days + 1);

export type Kind = 'general' | 'investment' | 'own';
/** The most the law allows (art. 16): 60 days, 30 for the investment decisions a decree lists; an administration may
 *  publish less for a decision (`own`, at most 60). */
export const MAX: Record<Kind, number> = { general: 60, investment: 30, own: 60 };

export type Stop = { key: 'deposit' | 'refused' | 'answer' | 'appeal' | 'reply'; date: string; path: string };

/** The stops of a request. `refused` is the day a refusal was received, if one was. */
export function stops(deposit: string, kind: Kind, own: number, refused: string | null): Stop[] {
  const days = kind === 'own' ? Math.min(Math.max(own, 1), MAX.own) : MAX[kind];
  const answer = complete(deposit, days);
  const out: Stop[] = [{ key: 'deposit', date: deposit, path: ARTICLES.receipt }, { key: 'answer', date: answer, path: ARTICLES.limit }];
  // Thirty days to appeal from the limit's end or from the refusal (art. 21); fifteen for the one who hears it.
  const from = refused ?? answer;
  if (refused) out.push({ key: 'refused', date: refused, path: ARTICLES.appeal });
  const appeal = complete(from, 30);
  out.push({ key: 'appeal', date: appeal, path: ARTICLES.appeal });
  out.push({ key: 'reply', date: complete(appeal, 15), path: ARTICLES.appeal });
  return out.sort((a, b) => (a.date < b.date ? -1 : a.date > b.date ? 1 : 0));
}

/** Where the reader stands on `today` among the stops: waiting for the answer, in the appeal's window, or past it. */
export function phase(s: Stop[], today: string): 'waiting' | 'appeal' | 'late' {
  const answer = s.find((x) => x.key === 'refused') ?? s.find((x) => x.key === 'answer')!;
  const appeal = s.find((x) => x.key === 'appeal')!;
  if (today <= answer.date && answer.key === 'answer') return 'waiting';
  return today <= appeal.date ? 'appeal' : 'late';
}
