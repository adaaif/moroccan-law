/** Morocco's paid public holidays (U12 of the Moroccan-design review, 25 Oct 2026), so a deadline that ends on one says
 *  so, and moves where the law moves it (law 58.25, art. 602: «إذا كان اليوم الأخير يوم عطلة امتد الأجل إلى أول يوم
 *  عمل بعده»). The list is decree 2.77.169's art. 1, as the SGG consolidated it to 6 Feb 2026: 14 January since decree
 *  2.23.688 (BO 7256, 14 Dec 2023), 31 October since decree 2.25.1140 (BO 7480, 5 Feb 2026). The religious days follow
 *  the moon as Morocco sees it: the Ministry of Habous announces each; until it has, the day is the Umm al-Qura
 *  calendar's, said to be expected (Morocco often sees the month a day after it). */
export const HOLIDAYS_PATH = '/ma/decret/2-77-169/art_1';

/** Month, day, its key in `topicKit:holidays.*`, the first year it counts. */
const FIXED: [number, number, string, number][] = [
  [1, 1, 'newYear', 0], [1, 11, 'manifesto', 0], [1, 14, 'amazigh', 2024], [5, 1, 'labour', 0], [7, 30, 'throne', 0],
  [8, 14, 'ouedEddahab', 0], [8, 20, 'revolution', 0], [8, 21, 'birthday', 0], [10, 31, 'unity', 2026],
  [11, 6, 'greenMarch', 0], [11, 18, 'independence', 0],
];
/** Hijri month, day, key. */
const HIJRI: [number, number, string][] = [
  [1, 1, 'hijriNewYear'], [3, 12, 'mawlid'], [3, 13, 'mawlid'], [10, 1, 'fitr'], [10, 2, 'fitr'], [12, 10, 'adha'], [12, 11, 'adha'],
];
/** The days the Ministry of Habous announced, by key and Gregorian date, replacing what the calendar expects: as each is
 *  announced, its line here, with the communiqué's date in a comment. None recorded yet. */
const ANNOUNCED: Record<string, string[]> = {};

export type Holiday = { key: string; expected: boolean };

let hijri: Intl.DateTimeFormat | null = null;
function hijriOf(date: Date): [number, number] {
  hijri ??= new Intl.DateTimeFormat('en-u-ca-islamic-umalqura', { day: 'numeric', month: 'numeric', timeZone: 'UTC' });
  const parts = hijri.formatToParts(date);
  const n = (type: string) => Number(parts.find((p) => p.type === type)?.value);
  return [n('month'), n('day')];
}

/** The holiday on an ISO day, or null. */
export function holiday(iso: string): Holiday | null {
  const date = new Date(`${iso}T12:00:00Z`);
  const [y, m, d] = [date.getUTCFullYear(), date.getUTCMonth() + 1, date.getUTCDate()];
  const fixed = FIXED.find(([fm, fd, , since]) => fm === m && fd === d && y >= since);
  if (fixed) return { key: fixed[2], expected: false };
  for (const [key, days] of Object.entries(ANNOUNCED)) if (days.includes(iso)) return { key, expected: false };
  const [hm, hd] = hijriOf(date);
  const religious = HIJRI.find(([rm, rd]) => rm === hm && rd === hd);
  // An announced feast sets its own days: the calendar's guess no longer counts for it that year.
  if (religious && !(ANNOUNCED[religious[2]] ?? []).some((a) => a.slice(0, 4) === String(y))) return { key: religious[2], expected: true };
  return null;
}
