import { test } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';

// The analytics review (15 Nov 2026): an event is fitted to the registry's rules before it leaves, since the door refuses
// a whole batch for one value outside them; and a tool's steps (topics/kit/use.ts) as the measure counts them.
const src = new URL('../src/', import.meta.url).href;
register('data:text/javascript,' + encodeURIComponent(`
export async function resolve(specifier, context, next) {
  return next(specifier.startsWith('@/') ? ${JSON.stringify(src)} + specifier.slice(2) + '.ts' : specifier, context);
}`));

const { fit, fitPath } = await import('../src/shared/analytics/rules.ts');

test('a property the registry does not list, or a value its rule refuses, is left out', () => {
  assert.deepEqual(fit('page.shown', { entry: true, ref: 'WWW.Google.CO.MA', back: 'week', fresh: 'dw', typed: 'x' }),
    { entry: true, ref: 'www.google.co.ma', back: 'week', fresh: 'dw' });
  assert.deepEqual(fit('page.shown', { ref: 'not a host', back: 'yesterday', entry: 'yes', installed: true }), { installed: true });
  assert.deepEqual(fit('tool.step', { step: 'typed' }), {});
  assert.deepEqual(fit('app.error', { error: 'TypeError', at: 'assets/x.js:1:2' }), { error: 'TypeError', at: 'assets/x.js:1:2' });
  assert.deepEqual(fit('app.error', { error: 'Cannot read x', at: undefined }), {});
  assert.deepEqual(fit('page.speed', { net: '', saver: false }), { net: '', saver: false });
});

test('a number outside its range is held at its end, a number that is none is left out', () => {
  assert.deepEqual(fit('page.speed', { lcp: 75_000, cls: -1, ttfb: 312.4, inp: Number.NaN }), { lcp: 60_000, cls: 0, ttfb: 312.4 });
  assert.deepEqual(fit('api.failed', { endpoint: '/corpus/at', status: 503 }), { endpoint: '/corpus/at', status: 503 });
});

test('an address loses its query, and is cut back a segment at a time until the door reads it', () => {
  assert.equal(fitPath('/topics/tax/tools/salary?g=10000&k=2#top'), '/topics/tax/tools/salary');
  assert.equal(fitPath('/places/%D8%A7%D9%84%D8%B1%D8%A8%D8%A7%D8%B7'), '/places');
  assert.equal(fitPath('/%D8%A7'), '/');
  assert.equal(fitPath(`/ma/${'x'.repeat(250)}`), '/ma');
  assert.equal(fitPath('/'), '/');
});

test('a tool counts by its page, its own sub-addresses as the tool, as the topics counter always wrote it', async () => {
  const { toolPage } = await import('../src/topics/kit/use.ts');
  assert.equal(toolPage('/topics/family/tools/inheritance/zawja-ibn-bint'), '/topics/family/tools/inheritance');
  assert.equal(toolPage('/topics/tax/tools/salary/'), '/topics/tax/tools/salary');
  assert.equal(toolPage('/topics/work/journeys/fired'), '/topics/work/journeys/fired');
  assert.equal(toolPage('/topics/road'), '/topics/road');
  assert.equal(toolPage('/search'), '/search');
  assert.equal(toolPage('/search/more'), null);
  assert.equal(toolPage('/ma/loi/65-99'), null);
  assert.equal(toolPage('/'), null);
});

test('a tool\'s steps: one flow an opening, the first answer and the first result after it once each', async () => {
  const noted: { props?: { step?: string }; path: string; flow?: number }[] = [];
  (globalThis as { window?: unknown }).window = { location: { pathname: '/topics/tax/tools/salary' } };
  const { hand } = await import('../src/shared/analytics/note.ts');
  hand((n) => noted.push(n as (typeof noted)[number]));
  const { noteUse } = await import('../src/topics/kit/use.ts');
  noteUse('result');                    // the card's words before anything was opened: not a step
  noteUse('open');
  noteUse('result');                    // an example before the reader answered: not a result
  noteUse('answered');
  noteUse('answered');
  noteUse('result');
  noteUse('result');
  noteUse('share');
  noteUse('door', '/search');           // another page: no flow
  noteUse('open', '/topics/tax/tools/salary/');
  noteUse('answered', '/topics/tax/tools/salary');
  noteUse('tick', '/ma/loi/65-99');     // neither a topic's nor the search's page: not counted
  assert.deepEqual(noted.map((n) => n.props?.step), ['opened', 'answered', 'result', 'shared', 'door', 'opened', 'answered']);
  assert.ok(noted.every((n) => n.path === (n.props?.step === 'door' ? '/search' : '/topics/tax/tools/salary')));
  const [first, , , , door, second] = noted;
  assert.ok(Number.isSafeInteger(first.flow) && first.flow! >= 1);
  assert.ok(noted.slice(0, 4).every((n) => n.flow === first.flow), 'one opening, one flow');
  assert.equal(door.flow, undefined);
  assert.notEqual(second.flow, first.flow, 'another opening, another flow');
  delete (globalThis as { window?: unknown }).window;
});
