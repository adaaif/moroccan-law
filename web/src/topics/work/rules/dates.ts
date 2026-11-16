/** The limits the work texts set (T10 of the work plan), each with its article, for the kit's dates tool. The Code's
 *  own limits do not say how they count: the site counts them as the family's (days from the next day, months to the same
 *  date) until a lawyer checks the rule; court limits are «complete» (law 58.25, art. 602), as are the strike law's
 *  (law 97.15, art. 32). */
import type { Event } from '../../kit/dates.ts';

const code = (n: number) => ({ path: `/ma/loi/65-99/art_${n}`, label: `مدونة الشغل، المادة ${n}` });
const law = (n: string, a: string, label: string) => ({ path: `/ma/loi/${n}/art_${a}`, label });

export const EVENTS: Event[] = [
  { key: 'dismissal', deadlines: [{ key: 'sue', days: 90, ...code(65) }] },
  { key: 'contractEnded', deadlines: [
    { key: 'certificate', days: 8, ...code(72) },
    { key: 'allowance', days: 60, path: '/ma/dahir/1-72-184/art_46-quater', label: 'ظهير الضمان الاجتماعي، الفصل 46 المكرر ثلاث مرات' },
    { key: 'prescription', months: 24, ...code(395) },
  ] },
  { key: 'receipt', deadlines: [{ key: 'withdraw', days: 60, ...code(75) }] },
  { key: 'accident', deadlines: [
    { key: 'tellEmployer', hours: 48, ...law('18-12', '14', 'القانون 18.12، المادة 14') },
    { key: 'employerDeclares', days: 5, ...law('18-12', '15', 'القانون 18.12، المادة 15') },
  ] },
  { key: 'birth', deadlines: [
    { key: 'paternity', months: 1, ...code(269) },
    { key: 'protection', days: 98, ...code(159), note: 'protection' },
    { key: 'nursing', months: 12, ...code(161), note: 'nursing' },
  ] },
  { key: 'judgment', deadlines: [{ key: 'appeal', days: 30, complete: true, ...law('58-25', '323', 'القانون 58.25، المادة 323') }] },
  { key: 'demands', deadlines: [{ key: 'strikeCall', days: 15, complete: true, path: '/ma/loi-organique/97-15/art_13', label: 'القانون التنظيمي 97.15، المادة 13' }],
    words: ['strikeNotice'] },
];
