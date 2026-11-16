import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

// Access on request (src/features/opendata/access.ts): where an account stands, the form's own checks, a request to
// change an access, the 30 days of use, the examples to copy; and the words the pages say, against the server's codes and
// numbers.
const access = await import('../src/features/opendata/access.ts');
const { standing, mayAsk, lastDays, shift, check, body, examples, share, KINDS, VOLUMES, REASONS, ENDED, TERMS_DATE, READS,
  changing, mayChange, checkChange, changeBody, firstCall, editionBytes, BIG_FILES, DATA_FILES, KEYS_MOST, MOST, SIZES } = access;

const read = (path: string) => readFileSync(new URL(path, import.meta.url), 'utf8');
const json = (path: string) => JSON.parse(read(path));
const pages = { ar: json('../src/shared/locales/pages.ar.json'), fr: json('../src/shared/locales/pages.fr.json') };
const mine = { ar: json('../src/features/opendata/locales/mine.ar.json'), fr: json('../src/features/opendata/locales/mine.fr.json') };
const privacy = {
  ar: json('../src/features/discussion/locales/ar.json').privacy,
  fr: json('../src/features/discussion/locales/fr.json').privacy,
};

type Req = Parameters<typeof standing>[0]['request'];
type Acc = Parameters<typeof standing>[0]['access'];
const req = (state: string, extra: object = {}) => ({ state, ask_again_on: null, change_of: null, ...extra }) as unknown as Req;
const acc = (state: string, extra: object = {}) =>
  ({ id: 7, state, ended_reason: state === 'ended' ? 'asked' : '', api: true, data: false, size: 'try', ...extra }) as unknown as Acc;

test('where an account stands decides what its door says', () => {
  assert.equal(standing({ request: null, access: null }), 'none');
  assert.equal(standing({ request: req('waiting'), access: null }), 'waiting');
  assert.equal(standing({ request: req('more'), access: null }), 'more');
  assert.equal(standing({ request: req('declined', { ask_again_on: '2026-12-16' }), access: null }), 'declined');
  assert.equal(standing({ request: req('declined'), access: null }), 'again');
  assert.equal(standing({ request: req('accepted'), access: acc('live') }), 'live');
  assert.equal(standing({ request: req('accepted'), access: acc('ended') }), 'ended');
  // A request sent after an access ended is what stands.
  assert.equal(standing({ request: req('waiting'), access: acc('ended') }), 'waiting');
  assert.equal(standing({ request: req('declined', { ask_again_on: '2026-12-16' }), access: acc('ended') }), 'declined');
  // A question about a change request is the one thing to do, though the access is live; a change waiting is not.
  assert.equal(standing({ request: req('more', { change_of: 7 }), access: acc('live') }), 'more');
  assert.equal(standing({ request: req('waiting', { change_of: 7 }), access: acc('live') }), 'live');
  assert.equal(standing({ request: req('declined', { change_of: 7, ask_again_on: '2026-12-16' }), access: acc('live') }), 'live');
});

test('a change request stands beside the live access it would change', () => {
  for (const state of ['waiting', 'more', 'declined', 'accepted']) {
    assert.equal(changing({ request: req(state, { change_of: 7 }), access: acc('live') })?.state, state);
  }
  assert.equal(changing({ request: req('accepted'), access: acc('live') }), null);
  assert.equal(changing({ request: req('waiting', { change_of: 7 }), access: acc('ended') }), null);
  assert.equal(changing({ request: req('waiting', { change_of: 3 }), access: acc('live') }), null);
});

test('a change may be asked only where the server would take it', () => {
  const at = (request: Req, a: Acc, position = 'request') => mayChange({ position, request, access: a } as never);
  assert.equal(at(req('accepted'), acc('live')), true);
  assert.equal(at(req('accepted', { change_of: 7 }), acc('live')), true);
  assert.equal(at(req('accepted'), acc('live'), 'open'), true);
  assert.equal(at(req('accepted'), acc('live'), 'closed'), false);
  assert.equal(at(req('accepted'), acc('ended')), false);
  assert.equal(at(req('waiting', { change_of: 7 }), acc('live')), false);
  assert.equal(at(req('more', { change_of: 7 }), acc('live')), false);
  assert.equal(at(req('declined', { change_of: 7, ask_again_on: '2026-12-16' }), acc('live')), false);
  assert.equal(at(req('declined', { change_of: 7 }), acc('live')), true);
});

test('a change request is checked as the server checks it', () => {
  const held = { api: true, data: false, size: 'try' as const };
  const ask = (f: object) => checkChange(held, { api: true, data: false, size: '', why: 'More.', ...f });
  assert.deepEqual(ask({}), [['change', 'nothing']]);
  assert.deepEqual(ask({ size: 'try' }), [['change', 'nothing']]);
  assert.deepEqual(ask({ data: true }), []);
  assert.deepEqual(ask({ size: 'app' }), []);
  assert.deepEqual(ask({ api: false, data: true }), []);
  // The fields first, all at once; whether anything changes only when they are right.
  assert.deepEqual(ask({ api: false, why: ' ' }), [['wants', 'required'], ['why', 'required']]);
  assert.deepEqual(ask({ data: true, why: 'x'.repeat(601) }), [['why', 'too_long']]);
  // A partner may ask for the partner size again: its numbers are its own.
  assert.deepEqual(checkChange({ ...held, size: 'partner' }, { api: true, data: false, size: 'partner', why: 'x' }), []);
  assert.deepEqual(changeBody({ api: true, data: true, size: 'app', why: 'x' }), { wants_api: true, wants_data: true, size: 'app', why: 'x' });
});

test('a new key\'s first call holds it, and asks what the access opens', () => {
  const key = `law_${'a'.repeat(38)}`;
  const api = firstCall('https://site.example', key, { api: true });
  assert.ok(api.startsWith('curl ') && api.includes(`-H "X-Api-Key: ${key}"`) && api.includes('https://site.example/api/v1/search'), api);
  assert.ok(!api.includes('$API_KEY'));
  const data = firstCall('https://site.example', key, { api: false });
  assert.ok(data.includes(`X-Api-Key: ${key}`) && data.includes('/api/open/latest/texts.jsonl.gz'), data);
});

test('the edition\'s size is its data files\', the two large ones first', () => {
  const files = Object.fromEntries(DATA_FILES.map((name, i) => [name, { bytes: (i + 1) * 1000, sha256: '' }]));
  assert.equal(editionBytes({ files: { ...files, 'manifest.json': { bytes: 5e6, sha256: '' } } }), 28_000);
  assert.ok(BIG_FILES.every((name) => DATA_FILES.includes(name)));
});

test('the form is offered only where the server would take it', () => {
  assert.deepEqual(['none', 'waiting', 'more', 'declined', 'again', 'live', 'ended'].filter((s) => mayAsk(s as never)),
    ['none', 'again', 'ended']);
});

test('the last 30 days run oldest first, today last, a day without use at zero, across a month', () => {
  const days = lastDays([{ day: '2026-11-02', calls: 4, articles: 9 }, { day: '2026-10-20', calls: 1, articles: 0 }], '2026-11-16');
  assert.equal(days.length, 30);
  assert.equal(days[0].day, '2026-10-18');
  assert.equal(days.at(-1)?.day, '2026-11-16');
  assert.deepEqual(days.find((d) => d.day === '2026-11-02'), { day: '2026-11-02', calls: 4, articles: 9 });
  assert.deepEqual(days.find((d) => d.day === '2026-10-31'), { day: '2026-10-31', calls: 0, articles: 0 });
  assert.equal(days.reduce((n, d) => n + d.calls, 0), 5);
  assert.equal(shift('2026-03-01', -1), '2026-02-28');
  assert.equal(shift('2028-02-28', 1), '2028-02-29');
});

test('a meter never runs past its limit', () => {
  assert.equal(share(500, 1000), 50);
  assert.equal(share(1500, 1000), 100);
  assert.equal(share(3, 0), 0);
});

const filled = { name: 'Salma', kind: 'school', purpose: 'A course on labour law.', wants_api: false, wants_data: true,
  runs_at: '', volume: 'small', commercial: false, terms: true, consent: true };

test('the form says every missing answer at once, as the server would', () => {
  const empty = { name: '  ', kind: '', purpose: '', wants_api: false, wants_data: false, runs_at: '', volume: '',
    commercial: null, terms: false, consent: false };
  assert.deepEqual(check(empty).map(([f]) => f), ['name', 'kind', 'purpose', 'wants', 'volume', 'commercial', 'terms', 'consent']);
  assert.deepEqual(check(filled), []);
  assert.deepEqual(check({ ...filled, name: 'x'.repeat(121) }), [['name', 'too_long']]);
  assert.deepEqual(check({ ...filled, purpose: 'x'.repeat(601) }), [['purpose', 'too_long']]);
  assert.deepEqual(check({ ...filled, runs_at: 'x'.repeat(201) }), [['runs_at', 'too_long']]);
  // A name folded to one line, as the server folds it, is counted after folding.
  assert.deepEqual(check({ ...filled, name: `${'x'.repeat(60)}\n\n   ${'y'.repeat(59)}` }), []);
});

test('the body sends the terms the server gave, only when they were accepted, and the consent as ticked', () => {
  assert.equal(body(filled, '2026-11-16').terms, '2026-11-16');
  assert.equal(body({ ...filled, terms: false }, '2026-11-16').terms, '');
  assert.equal(body({ ...filled, consent: false }, '2026-11-16').consent, false);
  assert.deepEqual(Object.keys(body(filled, 'x')).sort(),
    ['commercial', 'consent', 'kind', 'name', 'purpose', 'runs_at', 'terms', 'volume', 'wants_api', 'wants_data']);
});

test('every example sends the key in its header, to the site\'s own address', () => {
  const ex = examples('https://site.example', '2026-10-17');
  for (const [k] of READS) {
    assert.match(ex[k], /^curl /, k);
    assert.ok(ex[k].includes('-H "X-Api-Key: $API_KEY"'), k);
    assert.ok(ex[k].includes('https://site.example/api/v1/'), k);
  }
  assert.ok(ex.changes.includes('since=2026-10-17'));
  assert.ok(ex.edition.includes('/api/open/latest/'));
  // A French reader's examples ask in French.
  const fr = examples('https://site.example', '2026-10-17', 'fr');
  assert.ok(fr.search.includes('q=salaire minimum') && fr.references.includes('article 53 de la loi'));
  assert.ok(ex.search.includes('q=الحد الأدنى للأجر'));
});

test('the numbers the words say that the server does not send are the server\'s settings', () => {
  const settings = read('../../back/config/settings/base.py');
  const setting = (name: string) => Number(settings.match(new RegExp(`^${name} = (\\d+)`, 'm'))?.[1]);
  // «30 days» before a declined account may ask again (ACCESS_ASK_AGAIN_DAYS).
  const again = setting('ACCESS_ASK_AGAIN_DAYS');
  for (const lang of ['ar', 'fr'] as const) assert.ok(pages[lang].access.how.again.includes(String(again)), lang);
  // «Two keys, the most» (ACCESS_KEYS): the words name the number, so a new number needs new words.
  assert.equal(setting('ACCESS_KEYS'), 2, 'errors.keys.full and mine\'s keys.second say two keys');
  assert.equal(KEYS_MOST, setting('ACCESS_KEYS'));
  // A change request's reason (WHY_MOST) and its sizes (Access.Size).
  const service = read('../../back/apps/opendata/services/requests.py');
  assert.equal(MOST.why, Number(service.match(/^WHY_MOST = (\d+)$/m)?.[1]));
  const models = read('../../back/apps/opendata/models.py');
  for (const k of SIZES) assert.match(models, new RegExp(`= '${k}', `), k);
});

test('the terms the page shows are the terms the server records with a request', () => {
  const server = read('../../back/config/settings/base.py').match(/^ACCESS_TERMS = '(\d{4}-\d{2}-\d{2})'/m)?.[1];
  assert.equal(TERMS_DATE, server);
  for (const lang of ['ar', 'fr'] as const) assert.equal(pages[lang].access.terms.lines.length, 10, lang);
});

/** Every key path of an object of words. */
const paths = (o: unknown, at = ''): string[] => (o && typeof o === 'object' && !Array.isArray(o)
  ? Object.entries(o).flatMap(([k, v]) => paths(v, at ? `${at}.${k}` : k)) : [at]);

test('the two languages say the same things', () => {
  assert.deepEqual(paths(pages.fr.access), paths(pages.ar.access));
  assert.deepEqual(paths(mine.fr), paths(mine.ar));
  for (const lang of ['ar', 'fr'] as const) {
    for (const p of paths(mine[lang])) assert.ok(String(p.split('.').reduce((o: never, k) => o[k], mine[lang])).trim(), `${lang} mine.${p}`);
    for (const [k] of READS) assert.ok(mine[lang].api.reads[k], `${lang} mine read ${k}`);
  }
  assert.equal(mine.ar.title, 'وصولي');
  assert.equal(mine.fr.title, 'Mon accès');
  for (const lang of ['ar', 'fr'] as const) {
    const a = pages[lang].access;
    for (const k of KINDS) assert.ok(a.form.kinds[k], `${lang} kind ${k}`);
    for (const k of VOLUMES) assert.ok(a.form.volumes[k], `${lang} volume ${k}`);
    for (const k of REASONS) assert.ok(a.reasons[k].t && a.reasons[k].d, `${lang} reason ${k}`);
    for (const k of ENDED) assert.ok(a.ended[k], `${lang} ended ${k}`);
    for (const [k] of READS) assert.ok(a.api.reads[k], `${lang} read ${k}`);
  }
});

// The refusals of the request, the keys and the edition (their views and services under back/apps/opendata/): each said
// in words in both languages.
const REFUSALS = [
  'access.closed', 'access.live', 'access.none', 'access.no_api', 'email.unproven', 'request.open', 'request.too_soon',
  'request.none', 'terms.required', 'terms.stale', 'terms.invalid', 'consent.required', 'wants.required', 'name.required',
  'name.too_long', 'name.invalid', 'kind.required', 'kind.invalid', 'purpose.required', 'purpose.too_long',
  'purpose.invalid', 'runs_at.too_long', 'runs_at.invalid', 'volume.required', 'volume.invalid', 'commercial.required',
  'commercial.invalid', 'wants_api.invalid', 'wants_data.invalid', 'answer.required', 'answer.too_long', 'answer.invalid',
  'keys.full', 'key.not_found', 'key.invalid', 'key.ended', 'key.expired', 'open_data.closed', 'open_data.request',
  'open_data.no_access', 'open_data.daily', 'ticket.invalid', 'ticket.expired', 'file.invalid', 'edition.unknown',
  // A change request, and the server's doors that read one row.
  'change.nothing', 'size.invalid', 'why.required', 'why.too_long', 'why.invalid', 'access.ended', 'access.not_found',
  'request.not_found',
];

test('every refusal is said in both languages', () => {
  for (const lang of ['ar', 'fr'] as const) {
    for (const code of REFUSALS) {
      const [field, c] = code.split('.');
      // «وصولي» reads its own words first (mine:errors), then the shared ones (pages:errors).
      assert.ok((mine[lang].errors[field]?.[c] ?? pages[lang].errors[field]?.[c])?.trim(), `${lang} errors.${code}`);
    }
    assert.ok(pages[lang].errors.request.too_soon.includes('{{on}}'), lang);
  }
});

test('one word for the data: never «المعطيات» on these pages', () => {
  assert.ok(!JSON.stringify(pages.ar.access).includes('المعطيات'));
  assert.ok(!JSON.stringify(mine.ar).includes('المعطيات'));
  assert.ok(!JSON.stringify(privacy.ar.acts.write.items.access).includes('المعطيات'));
});

test('/privacy keeps a request as long as the server does', () => {
  const service = read('../../back/apps/opendata/services/requests.py');
  const [, declined, ended] = service.match(/^DECLINED_MONTHS, ENDED_MONTHS = (\d+), (\d+)$/m) ?? [];
  assert.ok(declined && ended, 'the retention is read from services/requests.py');
  for (const lang of ['ar', 'fr'] as const) {
    const p = privacy[lang];
    const item = p.acts.write.items.access.d;
    const words = (n: string) => (lang === 'fr' ? { 6: 'six', 12: 'douze' }[n] ?? n : n);
    for (const n of [declined, ended]) assert.ok(item.includes(n) || item.includes(words(n)), `${lang}: ${n} months in the item`);
    assert.ok(p.rows.access[1].includes(ended), `${lang}: the access row says ${ended}`);
    assert.ok(p.rows.declined[1].includes(declined), `${lang}: the declined row says ${declined}`);
    const form = pages[lang].access.form.keepText.join(' ');
    for (const n of [declined, ended]) assert.ok(form.includes(n) || form.includes(words(n)), `${lang}: ${n} in the consent`);
  }
});
