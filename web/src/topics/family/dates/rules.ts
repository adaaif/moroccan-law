/** The time limits the family's texts set (F7 of the family plan), each with its article. A limit is counted from the
 *  day of the event: days from the next day (the event day + n), months to the same date (decree 2.22.04, art. 40,
 *  writes it out for births and deaths; the site counts every limit so until a person checks the rule). A limit the law
 *  counts in cycles or by a birth is said in words, never as a date. */
import type { Event } from '../../kit/dates.ts';

export { due } from '../../kit/dates.ts';
export type { Deadline, Event } from '../../kit/dates.ts';

const code = (n: number) => ({ path: `/ma/loi/70-03/art_${n}`, label: `المادة ${n}` });
const decree = (n: number) => ({ path: `/ma/decret/2-22-04/art_${n}`, label: `المرسوم 2.22.04، المادة ${n}` });

export const EVENTS: Event[] = [
  { key: 'birth', deadlines: [
    { key: 'declareBirth', days: 30, rolls: true, ...decree(40) },
    { key: 'declareBirthAbroad', months: 12, rolls: true, ...decree(40) },
    { key: 'birthGrant', months: 6, path: '/ma/loi/58-23/art_3', label: 'القانون 58.23، المادة 3' },
  ] },
  { key: 'death', deadlines: [
    { key: 'declareDeath', days: 30, rolls: true, ...decree(40) },
    { key: 'widowIddah', months: 4, extraDays: 10, ...code(132) },
  ], words: ['widowPregnant'] },
  { key: 'marriageAbroad', deadlines: [{ key: 'consulate', months: 3, ...code(15) }] },
  { key: 'divorce', deadlines: [
    { key: 'deedToWife', days: 15, ...code(140) },
    { key: 'summary', days: 15, ...code(141), note: 'summary' },
    { key: 'iddahMonths', months: 3, ...code(136) },
  ], words: ['iddahCycles', 'iddahPregnant'] },
  { key: 'dues', deadlines: [{ key: 'deposit', days: 30, ...code(83), note: 'deposit' }] },
  { key: 'shiqaq', deadlines: [{ key: 'shiqaqJudgment', months: 6, ...code(97) }] },
  { key: 'grounds', deadlines: [{ key: 'groundsJudgment', months: 6, ...code(113) }] },
  { key: 'nafaqaCase', deadlines: [{ key: 'nafaqaJudgment', months: 1, ...code(190) }] },
  { key: 'nafaqaStopped', deadlines: [{ key: 'abandonment', months: 1, ...code(202) }] },
  { key: 'kafala', deadlines: [
    { key: 'kafalaExecution', days: 15, path: '/ma/loi/15-01/art_18', label: 'القانون 15.01، المادة 18' },
    { key: 'kafalaRecord', months: 1, path: '/ma/loi/15-01/art_21', label: 'القانون 15.01، المادة 21' },
  ] },
  { key: 'supportRefused', deadlines: [{ key: 'complaint', days: 15, path: '/ma/decret/2-23-1067/art_5', label: 'المرسوم 2.23.1067، المادة 5' }] },
];
