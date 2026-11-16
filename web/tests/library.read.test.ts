import { test } from 'node:test';
import assert from 'node:assert/strict';
import { archive, around, decode, type RawMap } from '../src/features/corpus/library/map.ts';
import { anatomy, findDate, fold, issuesOn, matchBooks, read as readAll, type BookRef, type Reading } from '../src/features/corpus/library/read.ts';

// A small map as the server writes it (back/apps/corpus/services/library.py issue_map): 610 on a cover bearing 610–637,
// 5167 with its pages, 6500 and 6501 three days apart, 7555 and its bis, a report held without texts.
const epoch = Date.UTC(1912, 0, 1);
const day = (iso: string) => (Date.parse(`${iso}T00:00:00Z`) - epoch) / 86_400_000;
const rows: [number, string, string, number, number, number, number, boolean][] = [
  [610, '', '1925-01-06', 7, 41, 0, 637, false],
  [5167, '', '2003-12-08', 20, 176, 3967, 0, false],
  [6500, '', '2016-09-15', 50, 56, 6700, 0, false],
  [6501, '', '2016-09-19', 48, 119, 6756, 0, false],
  [7555, '', '2026-10-26', 30, 22, 7867, 0, false],
  [7555, 'bis', '2026-10-27', 43, 83, 7889, 0, false],
  [7556, 'bis', '2026-10-30', 0, 40, 0, 0, true],
];
function raw(): RawMap {
  const col = { n: [] as number[], d: [] as number[], t: [] as number[], p: [] as number[], f: [] as number[],
                s: [] as [number, number][], l: [] as [number, number][], z: [] as number[] };
  let n = 0, d = 0, first = 0, pages = 0;
  rows.forEach(([number, suffix, date, texts, p, f, last, held], i) => {
    col.n.push(number - n); col.d.push(day(date) - d); col.t.push(texts); col.p.push(p);
    col.f.push(f - (first && pages ? first + pages : 0));
    if (suffix) col.s.push([i, suffix === 'bis' ? 1 : 2]);
    if (last) col.l.push([i, last]);
    if (held) col.z.push(i);
    n = number; d = day(date); first = f; pages = p;
  });
  return { epoch: '1912-01-01', ar: col, fr: { n: [3], d: [day('1912-11-15')], t: [4], p: [4], f: [], s: [], l: [], z: [] } };
}
const A = archive(raw());
const BOOKS: BookRef[] = [
  { key: 'labour', number: '65.99', names: ['مدونة الشغل', 'Le Code du travail', 'الشغل', 'code du travail'], base: true, shelf: true },
  { key: 'family', number: '70.03', names: ['مدونة الأسرة', 'Le Code de la famille', 'المدونة', 'moudawana'], base: true, shelf: true },
  { key: 'tax', number: '', names: ['المدونة العامة للضرائب', 'الضرائب'], base: true, shelf: true },
  { key: 'customs', number: '1.77.339', names: ['مدونة الجمارك', 'الديوانة', 'douane'] },
  { key: 'personal_data', number: '09.08', names: ['حماية المعطيات الشخصية', 'cndp'], shelf: true },
  { key: 'public_markets', number: '2.22.431', names: ['الصفقات العمومية'] },
  { key: 'judicial_organisation', number: '38.15', names: ['التنظيم القضائي', 'المحاكم'] },
  { key: 'finance_2026', number: '50.25', names: ['قانون المالية 2026', 'قانون المالية', 'loi de finances'] },
  { key: 'direct_support', number: '58.23', names: ['الدعم الاجتماعي المباشر'] },
  { key: 'civil_service', number: '1.58.008', names: ['الوظيفة العمومية', 'fonction publique'] },
];
const read = (q: string, a: typeof A | null = A): Reading[] => readAll(q, a, BOOKS).readings;
const asks = (q: string) => readAll(q, A, BOOKS).ask;

test('the map reads back what the server wrote', () => {
  const { ar, fr } = decode(raw());
  assert.deepEqual(ar.map((x) => [x.number, x.suffix, x.date, x.texts, x.pages, x.first, x.last, x.pagesOnly]),
    rows.map(([n, s, d, t, p, f, l, h]) => [n, s, d, t, p, f, l, h]));
  assert.equal(ar[5].key, '7555-bis');
  assert.equal(fr[0].date, '1912-11-15');
  assert.equal(A.years.get(2016)?.min, 6500);
  assert.equal(A.years.get(1925)?.max, 637);
  assert.equal(A.years.get(2026)?.pagesOnly, 1);
  assert.equal(A.maxNumber, 7556);
});

test('an issue by its number, in any digits, with its suffix, or on another cover', () => {
  const [r] = read('٦٥٠١');
  assert.ok(r.kind === 'issue' && r.issue?.number === 6501 && !r.cover && r.sure);
  const [bis] = read('7555 مكرر');
  assert.ok(bis.kind === 'issue' && bis.issue?.key === '7555-bis' && bis.sure);
  const [cover] = read('611');
  assert.ok(cover.kind === 'issue' && cover.cover && cover.issue?.number === 610);
  const [nowhere] = read('6017');
  assert.ok(nowhere.kind === 'issue' && !nowhere.issue && nowhere.nowhere && !nowhere.sure);
  const [past] = read('7590');
  assert.ok(past.kind === 'issue' && past.past && !past.sure);
});

test('an issue and its page, and a reference whose date is checked', () => {
  const [r] = read('5167 ص 3969');
  assert.ok(r.kind === 'issue' && r.page === 3969 && r.pageAt === 3);
  const [out] = read('العدد 5167 ص 9000');
  assert.ok(out.kind === 'issue' && out.issue?.number === 5167 && out.pageOut);
  const [ok] = read('الجريدة الرسمية عدد 5167 بتاريخ 8 دجنبر 2003، ص. 3969');
  assert.ok(ok.kind === 'issue' && ok.claimed?.date === '2003-12-08' && ok.pageAt === 3 && ok.sure);
  const [wrong] = read('ج.ر عدد 5167 بتاريخ 9 دجنبر 2003');
  assert.ok(wrong.kind === 'issue' && wrong.claimed?.date === '2003-12-09' && wrong.issue?.date === '2003-12-08');
  const [short] = read('ج ر ع 5167 ص 3969');
  assert.ok(short.kind === 'issue' && short.issue?.number === 5167 && short.pageAt === 3);
  assert.equal(asks('ج.ر عدد 5167'), false);
});

test('a French reference is the French edition: its page is never checked against the Arabic pages', () => {
  // W10: «B.O. n° 5167 … p. 667» was told its page is not in the issue. It is another edition's page.
  const [r] = read('B.O. n° 5167 du 8 décembre 2003, p. 667');
  assert.ok(r.kind === 'issue' && r.french && !r.issue && !r.sure && !r.pageOut && r.arabic?.number === 5167);
  // The French issue the site holds (no. 3 of 1912) opens, and is sure.
  const [held] = read('Bulletin officiel n° 3');
  assert.ok(held.kind === 'issue' && held.french && held.issue?.edition === 'translation_fr' && held.sure);
});

test('a text number is never an issue', () => {
  // W1: «loi n° 17-95» opened Bulletin no. 17 of 1913; a dahir's title opened issue no. 1.
  assert.equal(read('loi n° 17-95')[0].kind, 'number');
  assert.deepEqual(read('Dahir n° 1-03-194 du 11 septembre 2003 portant promulgation de la loi n° 65-99 relative au Code du travail'), []);
  assert.equal(asks('Dahir n° 1-03-194 du 11 septembre 2003 portant promulgation de la loi n° 65-99 relative au Code du travail'), true);
});

test('a day: its issues, or the nearest on each side; the server is asked for the texts of that day', () => {
  const [r] = read('19/09/2016');
  assert.ok(r.kind === 'day' && r.exact.map((x) => x.number).join() === '6501' && r.sure);
  assert.equal(asks('19/09/2016'), true);
  const [none] = read('السبت 17 شتنبر 2016');
  assert.ok(none.kind === 'day' && !none.exact.length && !none.sure && none.before[0].number === 6500 && none.after[0].number === 6501);
  // A month written with a hamza is a day alone too («أكتوبر», «أبريل»: it was sent to word search).
  const [hamza] = read('19 أكتوبر 2016');
  assert.ok(hamza.kind === 'day' && hamza.day.date === '2016-10-19');
  assert.equal(findDate('17 septembre 2016')?.date, '2016-09-17');
  assert.equal(findDate('فاتح غشت 2016')?.date, '2016-08-01');
  assert.equal(findDate('31/02/2016'), null);
  assert.deepEqual(around(A, '2026-10-26').after.map((x) => x.key), ['7555-bis']);
  // A dahir's day is no issue's day: the server reads it.
  assert.deepEqual(read('ظهير 19 شتنبر 2016'), []);
  assert.equal(asks('ظهير 19 شتنبر 2016'), true);
});

test('a month, and the newest issue as people ask for it', () => {
  const [month] = read('أكتوبر 2026');
  assert.ok(month.kind === 'month' && month.issues.map((x) => x.key).join() === '7555,7555-bis,7556-bis');
  const [fr] = read('septembre 2016');
  assert.ok(fr.kind === 'month' && fr.issues.length === 2);
  // «آخر عدد» asks for one issue, the last: sure. «هذا الأسبوع» may be several: offered, never opened.
  for (const [q, sure] of [['آخر عدد', true], ['العدد الأخير', true], ['le dernier BO', true], ['هذا الأسبوع', false], ['الجريدة الرسمية اليوم', false]] as const) {
    const [r] = read(q);
    assert.ok(r.kind === 'newest' && r.issues.map((x) => x.key).join() === '7556-bis,7555-bis' && r.sure === sure, q);
    assert.equal(asks(q), false);
  }
});

test('the issues of a day the server named: a Hijri day is a day like any other', () => {
  const a = archive(raw());
  assert.deepEqual(issuesOn(a, '2026-10-30').exact.map((x) => x.key), ['7556-bis']);
  const none = issuesOn(a, '2026-10-28');
  assert.ok(!none.exact.length && none.before[0]?.key === '7555-bis' && none.after[0]?.key === '7556-bis');
});

test('a number that is also a year is the year first, then the issue', () => {
  // W1: «1958» opened issue 1958 of May 1950. Issues 1912 to 2026 are of 1949 to 1951.
  const r = read('2016');
  assert.deepEqual(r.map((x) => [x.kind, x.sure]), [['year', true]]);
  const both = readAll('1925', archive({ ...raw(), ar: { ...raw().ar } }), BOOKS).readings;
  assert.equal(both[0].kind, 'year');
});

test('a text number taken apart, and the book it names', () => {
  const [law] = read('65.99');
  assert.ok(law.kind === 'number' && law.textKind === 'law' && law.year === 1999 && law.books[0] === 'labour' && law.sure);
  assert.equal(asks('65.99'), false);
  const [decree] = read('مرسوم رقم 2.22.431');
  assert.ok(decree.kind === 'number' && decree.textKind === 'decree' && decree.year === 2022 && decree.books[0] === 'public_markets');
  const [zero] = read('9.08');
  assert.ok(zero.kind === 'number' && zero.books[0] === 'personal_data' && zero.year === 2008);
  assert.equal(anatomy('1', '58', '376').textKind, 'dahir');
  assert.equal(anatomy('1', '58', '376').year, 1958);
  assert.equal(anatomy('2805', '14', undefined).textKind, 'order');
  // A number outside the 67: taken apart here, opened by the server.
  const [unknown] = read('103.13', null);
  assert.ok(unknown.kind === 'number' && unknown.books.length === 0 && unknown.year === 2013 && !unknown.sure);
  assert.equal(asks('103.13'), true);
});

test('a code by one of its whole names; words beside a name are the server\'s to read', () => {
  assert.equal(matchBooks('المدونة', BOOKS)[0], 'family');
  assert.equal(matchBooks('code du travail', BOOKS)[0], 'labour');
  assert.equal(matchBooks('قانون الشغل', BOOKS)[0], 'labour');
  assert.equal(matchBooks('الديوانة', BOOKS)[0], 'customs');
  assert.equal(matchBooks('قانون الوظيفة العمومية', BOOKS)[0], 'civil_service');
  assert.equal(matchBooks('للوظيفة العمومية', BOOKS)[0], 'civil_service');           // «لل» is «ال» with a «ل» before it
  assert.equal(fold('مُدَوَّنَة الأسرة'), fold('مدونة الاسره'));
  // W1: none of these is a book's name, though each holds one.
  for (const q of ['قانون المحاكم الإدارية', 'قانون المالية 2025', 'مشروع قانون المالية 2027', 'م.أ', 'زيادة الشغل']) {
    assert.deepEqual(matchBooks(q, BOOKS), [], q);
    assert.equal(asks(q), true, q);
  }
  const [r] = read('مدونة الشغل');
  assert.ok(r.kind === 'books' && r.sure && r.books[0] === 'labour');
  assert.equal(asks('مدونة الشغل'), false);
  assert.deepEqual(read('xyz'), []);
  assert.equal(asks('xyz'), true);
});
