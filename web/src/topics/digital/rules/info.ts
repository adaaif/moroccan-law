import { addDays } from '../../papers/rules/dates.ts';
import { workingDays } from '../../land/rules/permit.ts';

/** The right to information's road (law 31.13): from the day the institution received the request, the last day for
 *  its answer (20 working days, art. 16; 20 more when it says so in writing; 3 days in an emergency, art. 17), then, if
 *  the reader waits each step to its end, the complaint to the head (20 working days, art. 19), his answer (15 days), the
 *  complaint to the commission (30 days, art. 20), its answer (30 days) and the administrative court (60 days, art. 21).
 *  Pure. */
export const ARTICLES = { answer: '/ma/loi/31-13/art_16', urgent: '/ma/loi/31-13/art_17', head: '/ma/loi/31-13/art_19', commission: '/ma/loi/31-13/art_20', court: '/ma/loi/31-13/art_21' } as const;

export type Stop = { key: 'received' | 'answer' | 'head' | 'headAnswer' | 'commission' | 'commissionAnswer' | 'court'; date: string; path: string; who: 'me' | 'them' };

export function road(received: string, urgent: boolean, extended: boolean): Stop[] {
  const answer = urgent ? addDays(received, 3) : workingDays(received, extended ? 40 : 20);
  const head = workingDays(answer, 20);
  const headAnswer = addDays(head, 15);
  const commission = addDays(headAnswer, 30);
  const commissionAnswer = addDays(commission, 30);
  const court = addDays(commissionAnswer, 60);
  return [
    { key: 'received', date: received, path: ARTICLES.answer, who: 'me' },
    { key: 'answer', date: answer, path: urgent ? ARTICLES.urgent : ARTICLES.answer, who: 'them' },
    { key: 'head', date: head, path: ARTICLES.head, who: 'me' },
    { key: 'headAnswer', date: headAnswer, path: ARTICLES.head, who: 'them' },
    { key: 'commission', date: commission, path: ARTICLES.commission, who: 'me' },
    { key: 'commissionAnswer', date: commissionAnswer, path: ARTICLES.commission, who: 'them' },
    { key: 'court', date: court, path: ARTICLES.court, who: 'me' },
  ];
}
