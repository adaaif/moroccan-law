/** What the library's box reads in the browser (LB2 of the every-code review, read again for the library-search review, 10
 *  Nov 2026): an issue's number in any digits, an issue and its page, a whole reference pasted from a judgment (its date
 *  checked against the issue), a French reference told from an Arabic one, a day, a month, a year, the newest issue, a
 *  text's number taken apart, and a code by one of its whole names. Whatever names a text otherwise (a law outside the
 *  67, a short form, a dahir's day, an article) is read on the server (`find.ts`): `ask` says to ask it.
 *
 *  Every reading is sure or not (W1): «فتح» opens a sure first reading and nothing else. Pure: `npm run test:library`. */
import { around, issueByNumber, type Archive, type Held } from './map.ts';

export type BookRef = { key: string; number: string; names: string[]; base?: boolean; shelf?: boolean };
export type Day = { y: number; m: number; d: number; date: string };
/** A text number's part and what it says: «2.22.431» is a decree (2) numbered in 2022 (22), the 431st of that year. */
export type Part = { value: string; role: 'kind' | 'year' | 'seq' | 'billSeq' | 'billYear' | 'orderSeq' | 'orderYear' };
export type TextKind = 'law' | 'dahir' | 'decree' | 'decision' | 'order' | 'text';

export type Reading =
  | { kind: 'issue'; sure: boolean; number: number; suffix: Held['suffix']; issue: Held | null; cover: boolean; page: number | null;
      /** The page's place in the issue, 1 first; null when the issue's first page is unknown or the page is not in it. */
      pageAt: number | null; pageOut: boolean; claimed: Day | null; nowhere: boolean; past: boolean;
      /** A reference to the French edition («B.O. n° 5210 du 6 mai 2004, p. 667»): its pages are not the Arabic one's
       *  (W10). `issue` is then the French issue when the site holds it, and `arabic` the issue of that number in Arabic. */
      french: boolean; arabic: Held | null }
  | { kind: 'day'; sure: boolean; day: Day; weekday: number; exact: Held[]; before: Held[]; after: Held[] }
  | { kind: 'month'; sure: boolean; year: number; month: number; issues: Held[] }
  | { kind: 'year'; sure: boolean; year: number }
  | { kind: 'newest'; sure: boolean; issues: Held[] }
  | { kind: 'number'; sure: boolean; parts: Part[]; textKind: TextKind; year: number; books: string[]; query: string }
  | { kind: 'books'; sure: boolean; books: string[]; query: string };

/** What was read here, and whether the server is to be asked for the texts the words may name. */
export type Read = { readings: Reading[]; ask: boolean; query: string };

/** Digits as a phone's Arabic keyboard types them (٧٥٣٣, ۷۵۳۳), read as the Bulletin prints them. */
export const western = (s: string) =>
  s.replace(/[٠-٩]/g, (d) => String(d.charCodeAt(0) - 0x660)).replace(/[۰-۹]/g, (d) => String(d.charCodeAt(0) - 0x6f0));

/** Words compared without vowels, tatweel, the alef's seats, the ya's dots, the ta marbuta's or a French accent. */
export const fold = (s: string) => western(s).toLowerCase().replace(/[أإآٱ]/g, 'ا').normalize('NFD')
  .replace(/[̀-ًͯ-ٰٕـ]/g, '').replace(/ى/g, 'ي').replace(/ة/g, 'ه')
  .replace(/[«»"'’.,،:؛()\-–_/°؟?]/g, ' ').replace(/\s+/g, ' ').trim();

// Months as Moroccans, the Mashreq and the French write them, folded.
const MONTHS = [['يناير', 'جانفي', 'janvier'], ['فبراير', 'فيفري', 'fevrier'], ['مارس', 'mars'], ['ابريل', 'افريل', 'avril'],
  ['ماي', 'مايو', 'mai'], ['يونيو', 'يونيه', 'جوان', 'juin'], ['يوليوز', 'يوليو', 'جويليه', 'juillet'], ['غشت', 'اغسطس', 'اغشت', 'اوت', 'aout'],
  ['شتنبر', 'سبتمبر', 'septembre'], ['اكتوبر', 'octobre'], ['نونبر', 'نوفمبر', 'novembre'], ['دجنبر', 'ديسمبر', 'decembre']];
const MONTH_RE = MONTHS.flat().sort((a, b) => b.length - a.length).join('|');
const monthOf = (word: string) => MONTHS.findIndex((w) => w.includes(word)) + 1;
const WEEKDAYS = /\b(?:le|du|bo|yom)\b|يوم|بتاريخ|الاثنين|الثلاثاء|الاربعاء|الخميس|الجمعه|السبت|الاحد|lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche/g;
const SUFFIX = '(مكرر\\s*مرتين|مكرر|bis|ter)';
const suffixOf = (w?: string): Held['suffix'] => (!w ? '' : /ter|مرتين/i.test(w) ? 'ter' : 'bis');
/** Issues the SGG lists that exist nowhere online in Arabic (its index, 31 Oct 2026). */
const NOWHERE = new Set(['6017:', '7410:', '5823:bis']);
/** «آخر عدد», «le dernier BO»: the newest issue, as people ask for it (folded). */
const NEWEST = /^(?:اخر عدد|العدد الاخير|اخر جريده|الجريده الرسميه اليوم|جريده اليوم|هذا الاسبوع|جديد الجريده الرسميه|(?:le |la )?dernier(?:e)? (?:bulletin officiel|bulletin|bo|numero|edition)|cette semaine)$/;
/** Among them, the words that ask for one issue, the last: its line is sure. «هذا الأسبوع» and «اليوم» may be several
 *  issues or none: offered, never opened. */
const LAST = /^(?:اخر عدد|العدد الاخير|اخر جريده|(?:le |la )?dernier(?:e)? (?:bulletin officiel|bulletin|bo|numero|edition))$/;
/** The issues of a day, or the nearest on each side when none came out that day. */
export function issuesOn(a: Archive, date: string): { exact: Held[]; before: Held[]; after: Held[] } {
  const exact = a.byDay.get(date) ?? [];
  return { exact, ...(exact.length ? { before: [], after: [] } : around(a, date)) };
}
/** A reference written for the French edition: «B.O.», «Bulletin officiel», and no Arabic letter. */
const FRENCH = /\b(?:b\.?\s?o\.?|bulletin officiel)\b/i;
/** Words that name no code by themselves, folded. */
const STOP = new Set(['قانون', 'مدونه', 'ظهير', 'شريف', 'رقم', 'loi', 'code', 'dahir', 'le', 'la', 'les', 'du', 'de', 'des', 'd', 'l', 'و',
  'جديد', 'مغربي', 'مغرب', 'marocain', 'marocaine', 'maroc']);

const pad = (n: number) => String(n).padStart(2, '0');

/** A folded word without the letters Arabic writes on its front: «للوظيفه» and «الوظيفه» are one word (W6). */
export const stem = (w: string) => (w.length > 4 && w.startsWith('لل') ? w.slice(2) : w.length > 5 && /^[بوكف]ال/.test(w) ? w.slice(3)
  : w.length > 4 && w.startsWith('ال') ? w.slice(2) : w);
/** The words of a name that can tell one code from another. A year counts: «قانون المالية 2025» is not «قانون المالية 2026», nor «قانون المالية». */
export const nameWords = (s: string) => fold(s).split(' ').filter(Boolean).map(stem).filter((w) => w.length > 1 && !STOP.has(w));

/** A day written in figures or with a month's name: «17/09/2016», «2016-09-17», «17 شتنبر 2016», «فاتح غشت 2016»,
 *  «1er août 2016». `text` is the words it was read from. */
export function findDate(raw: string): (Day & { text: string }) | null {
  const t = western(raw);
  let m: RegExpMatchArray | null, y = 0, mo = 0, d = 0, text = '';
  if ((m = t.match(/(?:^|[^\d])(\d{1,2})\s*[/.-]\s*(\d{1,2})\s*[/.-]\s*(\d{4})(?!\d)/))) { d = +m[1]; mo = +m[2]; y = +m[3]; text = m[0]; }
  else if ((m = t.match(/(?:^|[^\d])(\d{4})-(\d{1,2})-(\d{1,2})(?!\d)/))) { y = +m[1]; mo = +m[2]; d = +m[3]; text = m[0]; }
  else {
    const f = fold(raw);
    m = f.match(new RegExp(`(\\d{1,2}|فاتح|1er)\\s*(?:er\\s+)?(?:من\\s+)?(${MONTH_RE})\\s+(?:سنه\\s+)?(\\d{4})`));
    if (!m) return null;
    d = /^\d+$/.test(m[1]) ? parseInt(m[1], 10) : 1;
    mo = monthOf(m[2]);
    y = +m[3];
    text = m[0];
  }
  const day = new Date(Date.UTC(y, mo - 1, d));
  if (y < 1912 || y > 2100 || day.getUTCMonth() !== mo - 1 || day.getUTCDate() !== d) return null;
  return { y, m: mo - 1, d, date: `${y}-${pad(mo)}-${pad(d)}`, text };
}

/** «65.99», «09.08» and «9.08» are one number. */
export const normalNumber = (s: string) => s.split(/[.\-/]/).map((p) => String(parseInt(p, 10))).join('.');

/** A text's number taken apart: what kind of text, the year it was numbered, its rank in that year. A law's number is
 *  its bill's: «65.99» was numbered in 1999 and became law in 2003. */
export function anatomy(a: string, b: string, c: string | undefined, word = ''): { parts: Part[]; textKind: TextKind; year: number } {
  const yy = Number(b);
  if (c !== undefined) {
    const textKind: TextKind = a === '1' ? 'dahir' : a === '2' ? 'decree' : a === '3' ? 'decision' : 'text';
    const year = yy >= 56 ? 1900 + yy : 2000 + yy;
    return { textKind, year, parts: [{ value: a, role: 'kind' }, { value: b, role: 'year' }, { value: c, role: 'seq' }] };
  }
  const order = a.length === 4 || /قرار|arr[eê]t/i.test(word);
  const year = order ? (yy >= 56 ? 1900 + yy : 2000 + yy) : yy >= 60 ? 1900 + yy : 2000 + yy;
  return order
    ? { textKind: 'order', year, parts: [{ value: a, role: 'orderSeq' }, { value: b, role: 'orderYear' }] }
    : { textKind: 'law', year, parts: [{ value: a, role: 'billSeq' }, { value: b, role: 'billYear' }] };
}

/** The books one of whose names is what was typed, whole: the same words, no more and no fewer («قانون الكراء» is the
 *  housing lease; «قانون المحاكم الإدارية» names no book although «المحاكم» is one's name: W1). The base of a branch first. */
export function matchBooks(q: string, books: BookRef[]): string[] {
  const typed = nameWords(q);
  // «المدونة» alone is the family code's everyday name: a name made of such words only is compared as written.
  const whole = fold(q).split(' ').map(stem).join(' ');
  if (!whole) return [];
  const found = books.filter((b) => b.names.some((name) => {
    const words = nameWords(name);
    return typed.length ? words.length === typed.length && words.every((w) => typed.includes(w)) : fold(name).split(' ').map(stem).join(' ') === whole;
  }));
  return found.sort((x, y) => Number(!!y.base) - Number(!!x.base) || Number(!!y.shelf) - Number(!!x.shelf)).map((b) => b.key);
}

function issueReading(a: Archive, number: number, suffix: Held['suffix'], page: number | null, claimed: Day | null, french: boolean): Reading {
  const { issue: own, cover } = issueByNumber(a, number, suffix);
  const frenchOwn = french ? a.frByNumber.get(`${number}:${suffix}`) ?? null : null;
  const issue = french ? frenchOwn : own;
  let pageAt: number | null = null, pageOut = false;
  // A French reference's page is never checked against the Arabic issue's pages: they are other pages.
  if (!french && issue && page !== null && issue.first && issue.pages) {
    if (page >= issue.first && page < issue.first + issue.pages) pageAt = page - issue.first + 1;
    else pageOut = true;
  }
  return { kind: 'issue', sure: !!issue, number, suffix, issue, cover: !french && cover, page, pageAt, pageOut, claimed, french, arabic: french ? own : null,
           nowhere: !french && !issue && NOWHERE.has(`${number}:${suffix}`), past: !french && !issue && number > a.maxNumber };
}

/** What `raw` reads as here, the likeliest first, and whether to ask the server. Without the archive (still loading),
 *  only text numbers and names. */
export function read(raw: string, a: Archive | null, books: BookRef[]): Read {
  const q = western(raw).replace(/\s+/g, ' ').trim();
  const out = (readings: Reading[], ask: boolean): Read => ({ readings, ask, query: q });
  if (!q) return out([], false);
  const f = fold(q);
  let m: RegExpMatchArray | null;
  if (a) {
    if (NEWEST.test(f)) return out([{ kind: 'newest', sure: LAST.test(f) && a.ar.length > 0, issues: a.ar.slice(-2).reverse() }], false);
    // An issue and its page, or a reference: «5167 ص 3969», «BO n° 5167 p. 3969», «الجريدة الرسمية عدد 5167 بتاريخ … ص. 3969».
    // Never a text's number: «loi n° 17-95» is law 17.95, not Bulletin no. 17.
    const page = q.match(/(?:^|[\s،,(])(?:ص|صفحة|الصفحة|p|page)\s*\.?\s*(\d{1,5})(?!\d)/i);
    const named = q.match(new RegExp(`(?:عدد|العدد|ج\\s*\\.?\\s*ر\\s*\\.?\\s*ع?\\s*\\.?|bulletin officiel n°|bulletin officiel|\\bbo n°|\\bb\\.\\s?o\\.?\\s*n°|\\bbo\\b|b\\.o\\.?)\\s*(?:رقم|n°|no\\.?)?\\s*(\\d{1,4})(?![\\d.\\-])\\s*${SUFFIX}?`, 'i'));
    const bare = page ? q.match(new RegExp(`^(\\d{1,4})\\s*${SUFFIX}?(?=\\s*[،,]?\\s*(?:ص|صفحة|الصفحة|p\\b|page))`, 'i')) : null;
    const issue = named ?? bare;
    if (issue) {
      const rest = q.replace(issue[0], ' ').replace(page ? page[0] : '', ' ');
      const french = FRENCH.test(q) && !/[ء-ي]/.test(q);
      return out([issueReading(a, Number(issue[1]), suffixOf(issue[2]), page ? Number(page[1]) : null, findDate(rest), french)], false);
    }
    // A month of a year: its issues.
    if ((m = f.match(new RegExp(`^(?:شهر )?(${MONTH_RE}) (\\d{4})$`)))) {
      const year = Number(m[2]), month = monthOf(m[1]);
      return out([{ kind: 'month', sure: true, year, month, issues: (a.years.get(year)?.ar ?? []).filter((x) => x.m === month - 1) }], false);
    }
    // A day alone: its issues here, and the texts signed that day from the server.
    const day = findDate(q);
    // Compared folded: «2 أكتوبر 1984» is read as «2 اكتوبر 1984», and what is left of it must be nothing.
    if (day && fold(q).replace(fold(day.text), ' ').replace(WEEKDAYS, '').trim() === '') {
      const on = issuesOn(a, day.date);
      return out([{ kind: 'day', sure: on.exact.length === 1, day, weekday: new Date(`${day.date}T00:00:00Z`).getUTCDay(), ...on }], true);
    }
    // A number alone: a year first when it can be one (issues 1912 to 2026 are of 1949 to 1951), then an issue's.
    if ((m = q.match(new RegExp(`^(\\d{1,4})\\s*${SUFFIX}?$`, 'i')))) {
      const number = Number(m[1]), found: Reading[] = [];
      const isYear = !m[2] && a.years.has(number);
      if (isYear) found.push({ kind: 'year', sure: true, year: number });
      if (number >= 1 && number <= a.maxNumber + 40) {
        const r = issueReading(a, number, suffixOf(m[2]), null, null, false);
        if (r.kind === 'issue' && (r.issue || !isYear)) found.push({ ...r, sure: !isYear && !!r.issue });
      }
      if (found.length) return out(found, false);
    }
  }
  // A text's number, with or without its kind: «65.99», «القانون رقم 65.99», «2.22.431», «décret n° 2-22-431». The server
  // opens the text whatever its kind; the book of that number, if it is one of the 67, is known here at once.
  m = q.match(/^(?:(القانون التنظيمي|قانون تنظيمي|القانون|قانون|الظهير الشريف|ظهير شريف|الظهير|ظهير|المرسوم|مرسوم|القرار|قرار|loi organique|loi|dahir|décret|decret|arrêté|arrete)\s*(?:رقم|n°|no\.?)?\s*)?(\d{1,4})\s*[.\-/]\s*(\d{2})(?:\s*[.\-/]\s*(\d{1,4}))?$/i);
  if (m) {
    const { parts, textKind, year } = anatomy(m[2], m[3], m[4], m[1]);
    const want = normalNumber([m[2], m[3], m[4]].filter((x) => x !== undefined).join('.'));
    const named = books.filter((b) => b.number && normalNumber(b.number) === want).map((b) => b.key);
    return out([{ kind: 'number', sure: named.length === 1, parts, textKind, year, query: q, books: named }], !named.length);
  }
  // A code by one of its whole names: known here at once. Anything else is the server's to read.
  const found = matchBooks(q, books);
  return out(found.length ? [{ kind: 'books', sure: found.length === 1, books: found, query: q }] : [], !found.length && f.length >= 2);
}
