import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

// The word checker of /open-source (src/features/opensource/words.ts): the order of the readings, the ids a device
// keeps and sends, the arrows' sides, the bar's share as written, what a 429 and a failure do; and the page's words, the
// same keys in both languages.
const words = await import('../src/features/opensource/words.ts');
const { step, START, wantsWord, remember, notList, readKept, sideOf, share, percent, slots, nextWord, answer, readCounts, NOT_MAX } = words;
type Word = import('../src/features/opensource/words.ts').Word;
type State = import('../src/features/opensource/words.ts').State;

const json = (path: string) => JSON.parse(readFileSync(new URL(path, import.meta.url), 'utf8'));

const word = (id: number, first: 'word' | 'suggestion' = id % 2 ? 'suggestion' : 'word'): Word => ({
  id,
  readings: first === 'word'
    ? [{ key: 'word', text: 'خيط' }, { key: 'suggestion', text: 'حيط' }]
    : [{ key: 'suggestion', text: 'حيط' }, { key: 'word', text: 'خيط' }],
  before: 'ارا حدودها شمالا وشرقا',
  after: 'ابن التنيجي وقبلة وغربا',
  strip: { url: `/api/quality/words/${id}/strip/`, width: 640, height: 150, mark: { x: 0.41, w: 0.16 } },
  source: { issue: { number: 1432, suffix: '', date: '1940-04-05' }, page: 512, document_id: 77, page_index: 3, language: 'ar' },
});
const run = (events: Parameters<typeof step>[1][], from: State = START) => events.reduce(step, from);

test('the readings stay in the order the server gave them', () => {
  for (const w of [word(50), word(51)]) {
    const s = run([{ type: 'asked' }, { type: 'got', asked: { word: w } }]);
    assert.equal(s.phase, 'word');
    assert.deepEqual(s.word?.readings.map((r) => r.key), w.readings.map((r) => r.key));
  }
  // Neither side is always «what we have now»: an even id puts the word first, an odd one the suggestion.
  assert.equal(word(50).readings[0].key, 'word');
  assert.equal(word(51).readings[0].key, 'suggestion');
});

test('a press shows the word asked for meanwhile, at once, and asks for the one after it', () => {
  let s = run([{ type: 'asked' }, { type: 'got', asked: { word: word(1) } }]);
  assert.equal(wantsWord(s), true, 'the word after this one is asked for while this one is read');
  s = run([{ type: 'asked' }, { type: 'got', asked: { word: word(2) } }], s);
  assert.equal(s.next?.id, 2);
  assert.equal(wantsWord(s), false);
  s = step(s, { type: 'pressed' });
  assert.equal(s.phase, 'word');
  assert.equal(s.word?.id, 2);
  assert.equal(s.next, null);
  assert.equal(wantsWord(s), true);
  // Pressed before the next one came: the sheet waits for it, and takes it when it comes.
  s = step(s, { type: 'asked' });
  s = step(s, { type: 'pressed' });
  assert.equal(s.phase, 'loading');
  assert.equal(wantsWord(s), false, 'the GET already out is the one awaited');
  s = step(s, { type: 'got', asked: { word: word(3) } });
  assert.equal(s.phase, 'word');
  assert.equal(s.word?.id, 3);
  // The same word twice is not shown twice.
  s = run([{ type: 'asked' }, { type: 'got', asked: { word: word(3) } }], s);
  assert.equal(s.next, null);
});

test('none left: said at once, or after the word on the sheet', () => {
  assert.equal(run([{ type: 'asked' }, { type: 'got', asked: { word: null } }]).phase, 'none');
  let s = run([{ type: 'asked' }, { type: 'got', asked: { word: word(4) } }, { type: 'asked' }, { type: 'got', asked: { word: null } }]);
  assert.equal(s.phase, 'word');
  assert.equal(s.last, true);
  assert.equal(wantsWord(s), false, 'no more asking once the server said none');
  s = step(s, { type: 'pressed' });
  assert.equal(s.phase, 'none');
});

test('a 429 is a pause, anything else an error; a press on the line tries again', () => {
  assert.equal(run([{ type: 'asked' }, { type: 'got', asked: { failed: 'paused' } }]).phase, 'paused');
  let s = run([{ type: 'asked' }, { type: 'got', asked: { failed: 'error' } }]);
  assert.equal(s.phase, 'error');
  assert.equal(wantsWord(s), false, 'nothing is asked until the reader presses');
  s = step(s, { type: 'again' });
  assert.equal(s.phase, 'loading');
  assert.equal(wantsWord(s), true);
  // The word after this one failing to come leaves the sheet as it is: the press asks again.
  s = run([{ type: 'asked' }, { type: 'got', asked: { word: word(5) } }, { type: 'asked' }, { type: 'got', asked: { failed: 'error' } }]);
  assert.equal(s.phase, 'word');
  assert.equal(s.word?.id, 5);
  s = step(s, { type: 'pressed' });
  assert.equal(s.phase, 'loading');
  assert.equal(wantsWord(s), true);
});

test('an answer that did not arrive is not lost: the line, then sent again on the press', () => {
  let s = run([{ type: 'asked' }, { type: 'got', asked: { word: word(6) } }, { type: 'asked' }, { type: 'got', asked: { word: word(7) } },
    { type: 'pressed' }]);
  s = step(s, { type: 'unsent', answer: { id: 6, says: 'suggestion' }, why: 'error' });
  assert.equal(s.phase, 'error');
  assert.deepEqual(s.retry, [{ id: 6, says: 'suggestion' }]);
  assert.equal(s.word?.id, 7, 'the next word waits behind the line');
  // A word that comes meanwhile does not hide the line.
  s = run([{ type: 'asked' }, { type: 'got', asked: { word: word(8) } }], s);
  assert.equal(s.phase, 'error');
  s = step(s, { type: 'unsent', answer: { id: 9, says: 'neither' }, why: 'paused' });
  assert.equal(s.phase, 'paused');
  assert.equal(s.retry.length, 2);
  s = step(s, { type: 'again' });
  assert.equal(s.phase, 'word');
  assert.equal(s.word?.id, 7);
  assert.deepEqual(s.retry, [], 'the page sends them again as it clears them');
});

test('the device keeps the last hundred ids it saw, and sends the words in hand with them', () => {
  let seen: number[] = [];
  for (let id = 1; id <= 130; id++) seen = remember(seen, id);
  assert.equal(seen.length, NOT_MAX);
  assert.equal(seen[0], 31);
  assert.equal(seen.at(-1), 130);
  // Seen again, it moves to the newest end, once.
  seen = remember(seen, 40);
  assert.equal(seen.length, NOT_MAX);
  assert.equal(seen.at(-1), 40);
  assert.equal(seen.filter((x) => x === 40).length, 1);
  const not = notList(seen, [500, 501]);
  assert.equal(not.length, NOT_MAX, 'a hundred ids at most');
  assert.deepEqual(not.slice(-2), [500, 501], 'the words in hand are always sent');
  assert.equal(not.includes(40), true, 'the newest seen are kept');
  assert.deepEqual(notList([1, 2, 3], [undefined, 2]), [1, 3, 2]);
  assert.deepEqual(notList([], [undefined, undefined]), []);
});

test('what the device kept is read back, and anything else is a fresh start', () => {
  assert.deepEqual(readKept(JSON.stringify({ mine: 7, seen: [3, 9, 12] })), { mine: 7, seen: [3, 9, 12] });
  assert.deepEqual(readKept(null), { mine: 0, seen: [] });
  assert.deepEqual(readKept('{not json'), { mine: 0, seen: [] });
  assert.deepEqual(readKept(JSON.stringify({ mine: -2, seen: [1, 'x', 2.5, 4] })), { mine: 0, seen: [1, 4] });
  const many = Array.from({ length: 150 }, (_, i) => i);
  assert.equal(readKept(JSON.stringify({ mine: 1, seen: many })).seen.length, NOT_MAX);
});

test('an arrow chooses the key on its side, in both directions', () => {
  // Arabic: the first reading is on the right.
  assert.equal(sideOf('ArrowRight', 'rtl'), 0);
  assert.equal(sideOf('ArrowLeft', 'rtl'), 1);
  // French: the first reading is on the left.
  assert.equal(sideOf('ArrowLeft', 'ltr'), 0);
  assert.equal(sideOf('ArrowRight', 'ltr'), 1);
  for (const key of ['ArrowUp', 'ArrowDown', 'Enter', ' ', 'a']) {
    assert.equal(sideOf(key, 'rtl'), null);
    assert.equal(sideOf(key, 'ltr'), null);
  }
});

test('the bar is filled to the share settled, written as the site writes a percentage', () => {
  assert.equal(share(0, 30401), 0);
  assert.equal(share(15000, 30000), 0.5);
  assert.equal(share(5, 0), 0, 'no words yet');
  assert.equal(share(40, 30), 1, 'never past full');
  // Arabic: the sign on the number's right, kept so by an isolate; one decimal under 10 %.
  assert.equal(percent(0, 30401, 'ar'), '\u20660٪\u2069');
  assert.equal(percent(1064, 30401, 'ar'), '\u20663,4٪\u2069');
  assert.equal(percent(12000, 30401, 'ar'), '\u206639٪\u2069');
  // Rounded down: 100 only when every word is settled.
  assert.equal(percent(30400, 30401, 'ar'), '\u206699٪\u2069');
  assert.equal(percent(30401, 30401, 'ar'), '\u2066100٪\u2069');
  assert.equal(percent(1064, 30401, 'fr'), '3,4\u202f%');
  assert.equal(percent(12000, 30401, 'fr'), '39\u202f%');
});

test('a sentence is cut at its figures', () => {
  assert.deepEqual(slots('منذ 1913: {{issues}} عددا و{{pages}} صفحة.'), ['منذ 1913: ', { name: 'issues' }, ' عددا و', { name: 'pages' }, ' صفحة.']);
  assert.deepEqual(slots('{{count}}'), [{ name: 'count' }]);
  assert.deepEqual(slots('بلا أرقام'), ['بلا أرقام']);
});

test('the calls: a 429 is a pause, a failure or no network an error, a word gone is not tried again', async () => {
  const real = globalThis.fetch;
  const asked: { url: string; init?: RequestInit }[] = [];
  const answerWith = (status: number, body: unknown = {}) => {
    globalThis.fetch = (async (url: string, init?: RequestInit) => {
      asked.push({ url, init });
      return new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } });
    }) as typeof fetch;
  };
  try {
    answerWith(200, { word: word(51) });
    const got = await nextWord([3, 9, 12]);
    assert.ok('word' in got && got.word?.id === 51);
    assert.equal(asked.at(-1)?.url, '/api/quality/words/next/?not=3,9,12');
    assert.equal(new Headers(asked.at(-1)?.init?.headers).get('authorization'), null, 'no token goes with a word');
    answerWith(200, { word: null });
    assert.deepEqual(await nextWord([]), { word: null });
    assert.equal(asked.at(-1)?.url, '/api/quality/words/next/');
    answerWith(429);
    assert.deepEqual(await nextWord([]), { failed: 'paused' });
    answerWith(503);
    assert.deepEqual(await nextWord([]), { failed: 'error' });

    answerWith(201, { ok: true });
    assert.equal(await answer(51, 'suggestion'), 'ok');
    assert.equal(asked.at(-1)?.url, '/api/quality/words/51/');
    assert.equal(asked.at(-1)?.init?.method, 'POST');
    assert.deepEqual(JSON.parse(String(asked.at(-1)?.init?.body)), { says: 'suggestion' });
    assert.equal(new Headers(asked.at(-1)?.init?.headers).get('authorization'), null, 'no token goes with an answer');
    answerWith(404, { errors: [{ field: 'word', code: 'not_found' }] });
    assert.equal(await answer(51, 'word'), 'gone');
    answerWith(429);
    assert.equal(await answer(51, 'word'), 'paused');
    answerWith(500);
    assert.equal(await answer(51, 'word'), 'error');

    globalThis.fetch = (async () => { throw new TypeError('offline'); }) as typeof fetch;
    assert.deepEqual(await nextWord([1]), { failed: 'error' });
    assert.equal(await answer(51, 'unclear'), 'error');
    await assert.rejects(readCounts());
    answerWith(200, { words: 30401, ready: 120, settled: 0, answers: 12, today: 12 });
    assert.equal((await readCounts()).words, 30401);
  } finally {
    globalThis.fetch = real;
  }
});

test('the page\'s words: the same keys in both languages, and every word the page reads', () => {
  const keys = (o: unknown, at = ''): string[] => (o && typeof o === 'object'
    ? Object.entries(o).flatMap(([k, v]) => keys(v, at ? `${at}.${k}` : k)) : [at]);
  const ar = json('../src/features/opensource/locales/open.ar.json');
  const fr = json('../src/features/opensource/locales/open.fr.json');
  assert.deepEqual(keys(ar).sort(), keys(fr).sort());
  // Empty only where a line is said in one language alone: the note that the words are Arabic, the French glosses.
  const empty = (o: unknown) => keys(o).filter((k) => k.split('.').reduce((v: Record<string, unknown>, p) => v[p] as Record<string, unknown>, o as Record<string, unknown>) === '');
  assert.deepEqual(empty(ar).sort(), ['example.rightGloss', 'example.wrongGloss', 'word.arabic']);
  assert.deepEqual(empty(fr), []);
  // The figures each sentence waits for are the same in both.
  const names = (o: unknown) => keys(o).map((k) => {
    const v = k.split('.').reduce((x: Record<string, unknown>, p) => x[p] as Record<string, unknown>, o as Record<string, unknown>);
    return `${k}:${slots(String(v)).filter((p) => typeof p !== 'string').map((p) => (p as { name: string }).name).join(',')}`;
  });
  assert.deepEqual(names(ar), names(fr));
  // The readers are told «الذكاء الاصطناعي», never a model's or a company's name.
  for (const file of [ar, fr]) assert.doesNotMatch(JSON.stringify(file), /Claude|Haiku|Sonnet|Anthropic|GPT|Gemini/);
  // Elsewhere on the site: the footer's link, «عن «قانون»»'s row, /privacy's line, in both languages.
  for (const lang of ['ar', 'fr']) {
    assert.ok(json(`../src/shared/locales/${lang}.json`).nav.contribute, lang);
    const row = json(`../src/shared/locales/pages.${lang}.json`).about.yours.open;
    assert.ok(row.t && row.d, lang);
    const item = json(`../src/features/discussion/locales/${lang}.json`).privacy.acts.read.items.word;
    assert.ok(item.t && item.d, lang);
  }
});
