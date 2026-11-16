import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import i18next from 'i18next';

// The access desk (src/features/opendata/desk.ts): the day an answer is due in words, the sentence of each act in the
// log, what accepting and changing restate before they go, the doors' names; and the desk's words, against the server's
// codes and the letters' own sentences.
const desk = await import('../src/features/opendata/desk.ts');
const { due, eventLine, restateAccept, restateChange, heldWords, doorName, partOf, checkAccept, checkLine, partnerNumber, linkOf,
  lastDays, REASONS, END_REASONS, DOORS, SIZES, PARTS } = desk;

const read = (path: string) => readFileSync(new URL(path, import.meta.url), 'utf8');
const words = {
  ar: JSON.parse(read('../src/features/opendata/locales/desk.ar.json')),
  fr: JSON.parse(read('../src/features/opendata/locales/desk.fr.json')),
};
const i18n = i18next.createInstance();
await i18n.init({ lng: 'ar', ns: ['desk'], defaultNS: 'desk', showSupportNotice: false, interpolation: { escapeValue: false },
  resources: { ar: { desk: words.ar }, fr: { desk: words.fr } } });
const tOf = (lng: 'ar' | 'fr') => i18n.getFixedT(lng, 'desk') as unknown as (key: string, o?: Record<string, unknown>) => string;
const ar = tOf('ar');
const fr = tOf('fr');
/** A sentence without the isolates that keep typed names in their own direction. */
const plain = (s: string) => s.replace(/[\u2066-\u2069]/g, '');

test('the day an answer is due, in words, in both languages', () => {
  const said = (t: typeof ar, n: number | null) => due(t, n);
  assert.deepEqual(said(ar, 3), { words: 'بقي 3 أيام', mark: '' });
  assert.equal(said(ar, 1).words, 'بقي يوم');
  assert.equal(said(ar, 2).words, 'بقي يومان');
  assert.equal(said(ar, 11).words, 'بقي 11 يوما');
  assert.deepEqual(said(ar, 0), { words: 'اليوم', mark: 'today' });
  assert.deepEqual(said(ar, -1), { words: 'تأخر يوما', mark: 'late' });
  assert.equal(said(ar, -2).words, 'تأخر يومين');
  assert.equal(said(ar, -4).words, 'تأخر 4 أيام');
  assert.equal(said(fr, 3).words, 'Encore 3 jours');
  assert.equal(said(fr, 1).words, 'Encore un jour');
  assert.equal(said(fr, 0).words, 'Aujourd’hui');
  assert.equal(said(fr, -1).words, 'En retard d’un jour');
  assert.equal(said(fr, -6).words, 'En retard de 6 jours');
  assert.deepEqual(said(ar, null), { words: '', mark: '' });
});

const at = '2026-11-16T10:00:00Z';
const e = (act: string, details: object = {}, extra: object = {}) =>
  ({ at, by: 'chief', act, request: 1, access: null, name: 'مختبر القانون الرقمي', details, ...extra }) as never;
const EVENTS = [
  e('sent', { api: true, data: false, volume: 'small' }, { by: 'salma' }),
  e('sent', { api: true, data: true, size: 'app' }, { by: 'salma', access: 4 }),
  e('answered', {}, { by: 'salma' }),
  e('asked', { line: 'ما اسم الكلية؟' }),
  e('accepted', { api: true, data: false, size: 'app', minute: null, calls: null, articles: null, ends_on: '2027-11-16' }),
  e('accepted', { api: true, data: true, size: 'partner', minute: 300, calls: 90000, articles: 40000, ends_on: '2027-11-16',
    before: { api: true, data: false, size: 'app' } }),
  e('declined', { reason: 'scope' }),
  e('changed', { before: { api: true, data: false, size: 'try' }, after: { api: true, data: true, size: 'app' } }, { request: null, access: 4 }),
  e('renewed', { ends_on: '2028-01-31', before: '2027-11-16' }, { request: null, access: 4 }),
  e('ended', { reason: 'leaked' }, { request: null, access: 4 }),
  e('ended', { reason: 'asked' }, { request: null, access: 4, by: 'salma' }),
  e('ended', { reason: 'expired' }, { request: null, access: 4, by: null }),
  e('key_made', { key: 9 }, { request: null, access: 4, by: 'salma' }),
  e('key_ended', { key: 9 }, { request: null, access: 4 }),
];

test('each act of the log is one sentence, in both languages, with nothing left unsaid', () => {
  for (const [lang, t] of [['ar', ar], ['fr', fr]] as const) {
    const lines = EVENTS.map((x) => plain(eventLine(t, x, lang)));
    for (const line of lines) {
      assert.ok(!/\{\{|log\.|granted\.|sizes\.|reasons\.|ended\./.test(line), `${lang}: ${line}`);
      assert.ok(line.includes('مختبر القانون الرقمي'), `${lang}: the name given is in ${line}`);
    }
    assert.equal(new Set(lines).size, lines.length, `${lang}: every act says something of its own`);
  }
  assert.equal(plain(eventLine(ar, EVENTS[4], 'ar')),
    'قبل chief طلب مختبر القانون الرقمي: الواجهة البرمجية، حجم «تطبيق»، حتى 16 نونبر 2027');
  assert.equal(plain(eventLine(fr, EVENTS[4], 'fr')),
    'chief a accepté la demande de مختبر القانون الرقمي : l’API, taille « Application », jusqu’au 16 novembre 2027');
  assert.equal(plain(eventLine(ar, EVENTS[3], 'ar')), 'سأل chief مختبر القانون الرقمي: «ما اسم الكلية؟»');
  assert.equal(plain(eventLine(ar, EVENTS[6], 'ar')), 'رفض chief طلب مختبر القانون الرقمي: أكثر من الحاجة');
  assert.equal(plain(eventLine(ar, EVENTS[10], 'ar')), 'أنهى مختبر القانون الرقمي وصوله بنفسه');
  assert.equal(plain(eventLine(ar, EVENTS[11], 'ar')), 'انتهى وصول مختبر القانون الرقمي: حلّ تاريخ انتهائه');
  // A partner's numbers are said with what was given.
  assert.match(plain(eventLine(ar, EVENTS[5], 'ar')), /^قبل chief تعديل وصول .+: الواجهة البرمجية وقاعدة البيانات، حجم «شريك» \(في الدقيقة: 300، الطلبات في اليوم: 90\.000، المواد في اليوم: 40\.000\)، حتى 16 نونبر 2027$/);
  // A name typed in Latin letters keeps its direction inside an Arabic sentence.
  assert.ok(eventLine(ar, e('answered', {}, { name: 'Lab Atlas' }), 'ar').includes('\u2068Lab Atlas\u2069'));
});

test('accepting restates in one sentence what it will give, and changing what it will become', () => {
  const g = { api: true, data: true, size: 'app' as const, ends_on: '2027-11-16' };
  assert.equal(restateAccept(ar, g, 'ar'), 'ستعطي: الواجهة البرمجية وقاعدة البيانات، حجم «تطبيق»، حتى 16 نونبر 2027.');
  assert.equal(restateAccept(fr, g, 'fr'), 'Vous donnerez : l’API et la base de données, taille « Application », jusqu’au 16 novembre 2027.');
  assert.equal(restateAccept(ar, { ...g, data: false }, 'ar', true), 'سيصير وصوله: الواجهة البرمجية، حجم «تطبيق»، حتى 16 نونبر 2027.');
  const partner = restateAccept(ar, { ...g, size: 'partner', minute: 500, calls: null, articles: 30000 }, 'ar');
  assert.ok(partner.includes('في الدقيقة: 500') && partner.includes('الطلبات في اليوم: كالتطبيق') && partner.includes('30.000'), partner);
  // Without its numbers, a partner is said as a size alone.
  assert.equal(heldWords(ar, { api: true, data: false, size: 'partner' }, 'ar'), 'الواجهة البرمجية، حجم «شريك»');
  assert.equal(restateChange(ar, { api: true, data: false, size: 'try' }, { api: true, data: true, size: 'app' }, 'ar'),
    'سيصير: الواجهة البرمجية وقاعدة البيانات، حجم «تطبيق»، بدل الواجهة البرمجية، حجم «تجربة».');
});

test('every door the server counts has a name in both languages; an unknown one is said by its code', () => {
  const usage = read('../../back/apps/opendata/services/usage.py');
  const server = [...(usage.match(/^DOORS = \(([^)]+)\)/m)?.[1] ?? '').matchAll(/'([^']+)'/g)].map((m) => m[1]);
  assert.ok(server.length >= 9, 'the doors are read from services/usage.py');
  assert.deepEqual([...server].sort(), [...DOORS].sort());
  for (const t of [ar, fr]) {
    const names = server.map((d) => doorName(t, d));
    for (const [i, n] of names.entries()) assert.ok(n && n !== server[i] && !n.startsWith('doors.'), `${server[i]}: ${n}`);
    assert.equal(new Set(names).size, names.length);
  }
  assert.equal(doorName(ar, 'v2.new'), 'v2.new');
  assert.equal(doorName(ar, 'v1.search'), 'البحث');
});

/** Every key of an object of words, without the plural endings each language has its own of. */
const paths = (o: unknown, at = ''): string[] => (o && typeof o === 'object' && !Array.isArray(o)
  ? Object.entries(o).flatMap(([k, v]) => paths(v, at ? `${at}.${k}` : k)) : [at.replace(/_(zero|one|two|few|many|other)$/, '')]);

test('the two languages say the same things, and name every code the pages show', () => {
  assert.deepEqual([...new Set(paths(words.fr))].sort(), [...new Set(paths(words.ar))].sort());
  for (const lang of ['ar', 'fr'] as const) {
    const w = words[lang];
    for (const k of REASONS) assert.ok(w.reasons[k] && w.reasonSaid[k], `${lang} reason ${k}`);
    for (const k of END_REASONS) assert.ok(w.ended[k] && w.endedSaid[k], `${lang} end ${k}`);
    for (const k of ['asked', 'terms', 'leaked', 'unused', 'expired', 'account']) assert.ok(w.ended[k], `${lang} ended ${k}`);
    for (const k of SIZES) assert.ok(w.sizes[k], `${lang} size ${k}`);
    for (const k of PARTS) assert.ok(w.parts[k], `${lang} part ${k}`);
    for (const k of ['person', 'school', 'newsroom', 'association', 'public', 'company']) assert.ok(w.kinds[k], `${lang} kind ${k}`);
    for (const k of ['small', 'medium', 'large']) assert.ok(w.volumes[k], `${lang} volume ${k}`);
  }
  assert.equal(words.ar.title, 'إدارة الوصول');
  assert.equal(words.fr.title, 'Gestion des accès');
});

// The refusals the desk's doors answer with (api/desk_views.py, services/desk.py, requests.py, access.py, keys.py).
const REFUSALS = [
  'desk.forbidden', 'request.decided', 'request.not_found', 'request.throttled', 'access.not_found', 'access.ended', 'access.live',
  'key.not_found', 'key.ended', 'by.own', 'by.not_superuser', 'size.invalid', 'ends_on.past', 'ends_on.invalid', 'wants.required',
  'reason.invalid', 'line.required', 'line.too_long', 'line.invalid', 'confirm.required', 'change.nothing', 'minute.invalid',
  'calls.invalid', 'articles.invalid', 'api.invalid', 'data.invalid', 'act.invalid', 'cursor.invalid', 'state.invalid',
  'days.invalid', 'q.invalid',
];

test('every refusal of the desk is said in words in both languages', () => {
  for (const lang of ['ar', 'fr'] as const) {
    for (const code of REFUSALS) {
      const [field, c] = code.split('.');
      assert.ok(words[lang].errors[field]?.[c]?.trim(), `${lang} errors.${code}`);
    }
  }
  const views = read('../../back/apps/opendata/api/desk_views.py') + read('../../back/apps/opendata/services/desk.py');
  for (const [, field, code] of views.matchAll(/Refused\('(\w+)', '(\w+)'/g)) {
    assert.ok(REFUSALS.includes(`${field}.${code}`), `${field}.${code} is said`);
  }
});

test('the reasons are said in the letters\' own sentences', () => {
  // The Python source's implicit string joins, undone.
  const mail = read('../../back/apps/accounts/services/mail.py').replace(/'\s*\n\s*'/g, '');
  const lower = (s: string) => s.charAt(0).toLowerCase() + s.slice(1);
  for (const lang of ['ar', 'fr'] as const) {
    for (const k of REASONS) assert.ok(mail.includes(lower(words[lang].reasonSaid[k])) || mail.includes(words[lang].reasonSaid[k]), `${lang} ${k}`);
    for (const k of END_REASONS) assert.ok(mail.includes(lower(words[lang].endedSaid[k])) || mail.includes(words[lang].endedSaid[k]), `${lang} ended ${k}`);
  }
});

test('one word for the data on the desk: never «المعطيات» but for a person\'s own', () => {
  assert.ok(!JSON.stringify(words.ar).includes('المعطيات'));
});

test('the parts are addresses; anything else is the first', () => {
  assert.equal(partOf(null), 'waiting');
  assert.equal(partOf('log'), 'log');
  assert.equal(partOf('admin'), 'waiting');
});

test('what a form would be refused for is said before a letter is asked for', () => {
  const g = { api: true, data: false, size: 'app', ends_on: '2027-01-01' };
  assert.equal(checkAccept(g, '2026-11-16'), null);
  assert.deepEqual(checkAccept({ ...g, api: false }, '2026-11-16'), ['wants', 'required']);
  assert.deepEqual(checkAccept({ ...g, size: 'huge' }, '2026-11-16'), ['size', 'invalid']);
  assert.deepEqual(checkAccept({ ...g, ends_on: '2026-11-16' }, '2026-11-16'), ['ends_on', 'past']);
  assert.equal(checkAccept({ ...g, ends_on: null }, '2026-11-16'), null);
  assert.deepEqual(checkLine('   '), ['line', 'required']);
  assert.deepEqual(checkLine('x'.repeat(301)), ['line', 'too_long']);
  assert.equal(checkLine(`ما اسم\n  الكلية؟ ${'x'.repeat(280)}`), null);
  assert.equal(partnerNumber(''), null);
  assert.equal(partnerNumber(' 500 '), 500);
  assert.ok(Number.isNaN(partnerNumber('0')));
  assert.ok(Number.isNaN(partnerNumber('99999999999')));
});

test('an address a request names is a link only when a browser can open it', () => {
  assert.equal(linkOf('https://lab.example.ma/app'), 'https://lab.example.ma/app');
  assert.equal(linkOf('lab.example.ma'), 'https://lab.example.ma/');
  assert.equal(linkOf('javascript:alert(1)'), null);
  assert.equal(linkOf('تطبيق على الهاتف'), null);
  assert.equal(linkOf(''), null);
});

test('thirty days of use run oldest first, today last, across a month', () => {
  const days = lastDays([{ day: '2026-11-02', calls: 4, articles: 9 }], '2026-11-16');
  assert.equal(days.length, 30);
  assert.equal(days[0].day, '2026-10-18');
  assert.equal(days.at(-1)?.day, '2026-11-16');
  assert.equal(days.reduce((n, d) => n + d.calls, 0), 4);
});
