// What the site counts, in a real browser (the analytics review, 15 Nov 2026), with no backend: the built web served by
// Vite's preview, every /api/ call answered here. A reader with a cookie and a stored session opens /privacy, follows a
// link inside the app, then hides the page: exactly one POST /api/measure/, JSON, with the two pages shown (the first
// a visit's entry) and every event within the registry's rules, and with no Cookie and no Authorization header, though
// the app's other calls carry both. «لا تحسبني» then stops it; a device that refused sends nothing; nor does a browser a
// program drives.
//
//   npm run build && node e2e/measure.e2e.mjs
//
// Playwright's Chromium says navigator.webdriver = true, and the engine sends nothing to such a browser: the first
// scenarios turn it off with an init script (Navigator.prototype.webdriver read as false, before any page script runs);
// the last leaves it on and expects nothing. WEB_DIST: the built web (default web/dist); WEB_PORT: the preview's port
// (default 0, a free one); SHOTS=<dir> saves a screenshot of /privacy's counted section.
import assert from 'node:assert/strict';
import path from 'node:path';
import { chromium } from 'playwright';
import { preview } from 'vite';
import { BUILD, MOST_EVENTS, PATH, RULES } from '../src/shared/analytics/measures.ts';

const web = path.resolve(import.meta.dirname, '..');
const dist = path.resolve(process.env.WEB_DIST ?? path.join(web, 'dist'));
const shots = process.env.SHOTS;

const server = await preview({
  root: web,
  configFile: false,
  logLevel: 'warn',
  build: { outDir: dist },
  preview: { host: '127.0.0.1', port: Number(process.env.WEB_PORT ?? 0), strictPort: true },
});
const base = `http://127.0.0.1:${server.httpServer.address().port}`;
console.log(`measure: the built web at ${base}`);

/** What GET /api/measure/ answers, made from the registry's copy (measures.ts). */
const PUBLIC = {
  days: 90,
  measures: Object.entries(RULES).map(([name, props]) => ({
    name, category: ['page.shown', 'tool.step'].includes(name) ? 'interaction' : 'technical', props: Object.keys(props),
  })),
};

/** An event as the door checks it (back/apps/analytics/services/record.py): its path, and each property by its rule. */
function door(event) {
  assert.ok(RULES[event.name], `a known measure: ${event.name}`);
  assert.match(event.path, new RegExp(PATH), event.path);
  for (const [key, value] of Object.entries(event.props ?? {})) {
    const rule = RULES[event.name][key];
    assert.ok(rule, `${event.name} carries ${key}`);
    if (rule.type === 'bool') assert.equal(typeof value, 'boolean', key);
    if (rule.type === 'choice') assert.ok(rule.values.includes(value), `${key}=${value}`);
    if (rule.type === 'number') assert.ok(typeof value === 'number' && value >= rule.lo && value <= rule.hi, `${key}=${value}`);
    if (rule.type === 'pattern') assert.ok(value.length <= rule.most && new RegExp(rule.pattern).test(value), `${key}=${value}`);
  }
}

const browser = await chromium.launch();

/** A reader's browser: a cookie and a stored session, the API answered here; `driven` leaves navigator.webdriver on. */
async function reader({ refused = false, driven = false } = {}) {
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 }, locale: 'ar-MA', serviceWorkers: 'block' });
  await context.addCookies([{ name: 'reader', value: 'e2e', url: base }]);
  await context.addInitScript(({ driven, refused }) => {
    if (!driven) Object.defineProperty(Navigator.prototype, 'webdriver', { get: () => false, configurable: true });
    localStorage.setItem('law.session', JSON.stringify({ access: 'e2e-access', refresh: 'e2e-refresh' }));
    if (refused) localStorage.setItem('law.measure.off', '1');
  }, { driven, refused });
  const posts = [];
  const others = [];
  await context.route('**/api/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    if (url.pathname === '/api/measure/' && request.method() === 'POST') {
      posts.push({ headers: await request.allHeaders(), body: request.postData() });
      return route.fulfill({ status: 204 });
    }
    others.push({ path: url.pathname, headers: await request.allHeaders() });
    if (url.pathname === '/api/measure/') return route.fulfill({ json: PUBLIC });
    if (url.pathname === '/api/auth/me/') {
      return route.fulfill({ json: { id: 1, username: 'e2e', email: 'e2e@example.org', display_name: 'e2e', preferred_language: 'ar',
        date_joined: '2026-11-01T00:00:00Z', email_proven: true, address_form: '', email_notices: false } });
    }
    if (url.pathname === '/api/discussion/me/unseen/') return route.fulfill({ json: { unseen: 0, review: 0, reviewer: false, karma: 0 } });
    return route.fulfill({ status: 404, json: { errors: [{ field: 'request', code: 'not_found' }] } });
  });
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  return { context, page, posts, others, errors };
}

/** Until the measures' engine came (loaded when the browser is idle) and took the page's history over. */
const engineReady = (page) => page.waitForFunction(() => !String(history.pushState).includes('[native code]'), null, { timeout: 15000 });

/** The page as the reader leaves it: hidden, as a tab put away or the phone locked. */
const hide = (page) => page.evaluate(() => {
  Object.defineProperty(document, 'visibilityState', { value: 'hidden', configurable: true });
  Object.defineProperty(document, 'hidden', { value: true, configurable: true });
  document.dispatchEvent(new Event('visibilitychange', { bubbles: true }));
});
const show = (page) => page.evaluate(() => {
  Object.defineProperty(document, 'visibilityState', { value: 'visible', configurable: true });
  Object.defineProperty(document, 'hidden', { value: false, configurable: true });
  document.dispatchEvent(new Event('visibilitychange', { bubbles: true }));
});

/** Into the app: the header's way home, followed by the router. */
async function goHome(page) {
  await page.locator('header a[href="/"]').first().click();
  await page.waitForURL(`${base}/`);
}

try {
  // ── a reader, counted ─────────────────────────────────────────────────────────────────────────────────────────────
  {
    const { context, page, posts, others, errors } = await reader();
    await page.goto(`${base}/privacy`);
    await page.locator('#counted').getByText('page.shown').waitFor();
    await engineReady(page);
    if (shots) await page.locator('#counted').screenshot({ path: `${shots}/privacy-counted.png` });
    await goHome(page);
    await page.waitForTimeout(300);
    assert.equal(posts.length, 0, 'nothing is sent while the page is in view');
    await hide(page);
    await page.waitForTimeout(800);
    assert.equal(posts.length, 1, 'one batch when the page is hidden');
    const [post] = posts;
    assert.match(post.headers['content-type'] ?? '', /^application\/json/);
    assert.equal(post.headers.cookie, undefined, 'no cookie goes with the measures');
    assert.equal(post.headers.authorization, undefined, 'no account token goes with the measures');
    // The test is not empty: the app's own calls carried both.
    assert.ok(others.some((o) => o.headers.cookie?.includes('reader=e2e')), 'the app\'s calls carry the cookie');
    assert.ok(others.some((o) => o.headers.authorization === 'Bearer e2e-access'), 'the app\'s calls carry the session');

    const batch = JSON.parse(post.body);
    assert.deepEqual(Object.keys(batch).sort(), ['build', 'events', 'lang', 'screen']);
    assert.equal(batch.lang, 'ar');
    assert.equal(batch.screen, 'desk');
    assert.match(batch.build, new RegExp(BUILD));
    assert.ok(batch.events.length >= 2 && batch.events.length <= MOST_EVENTS);
    batch.events.forEach(door);
    const shown = batch.events.filter((e) => e.name === 'page.shown');
    assert.deepEqual(shown.map((e) => [e.path, e.kind]), [['/privacy', 'page'], ['/', 'home']]);
    assert.deepEqual(shown[0].props, { entry: true, back: 'first', fresh: 'dwm' }, 'the visit\'s first page, from nowhere');
    assert.equal(shown[1].props, undefined, 'the next page is no entry');
    const speed = batch.events.find((e) => e.name === 'page.speed');
    console.log(`ok   one batch: ${batch.events.map((e) => e.name).join(', ')}; build ${batch.build}`);
    if (speed) console.log(`     page.speed on ${speed.path}: ${JSON.stringify(speed.props)}`);
    const day = await page.evaluate(() => localStorage.getItem('law.measure.day'));
    assert.match(day ?? '', /^\d{4}-\d{2}-\d{2}$/, 'the phone keeps the day it came');

    // «لا تحسبني»: pressed, the device sends nothing more and its day goes.
    await show(page);
    await page.goto(`${base}/privacy`);
    await engineReady(page);
    const button = page.getByRole('button', { name: 'لا تحسبني' });
    assert.equal(await button.getAttribute('aria-pressed'), 'false');
    await button.click();
    assert.equal(await button.getAttribute('aria-pressed'), 'true');
    assert.equal(await page.evaluate(() => localStorage.getItem('law.measure.off')), '1');
    assert.equal(await page.evaluate(() => localStorage.getItem('law.measure.day')), null, 'the day kept for the measures goes');
    await goHome(page);
    await hide(page);
    await page.waitForTimeout(800);
    assert.equal(posts.length, 1, 'nothing after «لا تحسبني»');
    console.log('ok   «لا تحسبني» stops the measures and removes the day');
    assert.deepEqual(errors, [], 'no error in the page');
    await context.close();
  }

  // ── a device that refused before ───────────────────────────────────────────────────────────────────────────────────
  {
    const { context, page, posts, errors } = await reader({ refused: true });
    await page.goto(`${base}/privacy`);
    await engineReady(page);
    assert.equal(await page.getByRole('button', { name: 'لا تحسبني' }).getAttribute('aria-pressed'), 'true');
    await goHome(page);
    await hide(page);
    await page.waitForTimeout(1000);
    assert.equal(posts.length, 0, 'a device that refused sends nothing');
    assert.equal(await page.evaluate(() => localStorage.getItem('law.measure.day')), null, 'and keeps no day');
    assert.deepEqual(errors, []);
    console.log('ok   a device that refused sends nothing');
    await context.close();
  }

  // ── a browser a program drives (navigator.webdriver, as Playwright leaves it) ──────────────────────────────────────
  {
    const { context, page, posts, errors } = await reader({ driven: true });
    const engine = page.waitForResponse(async (r) => r.url().includes('/assets/') && r.url().endsWith('.js')
      && (await r.text().catch(() => '')).includes('/api/measure/'), { timeout: 15000 });
    await page.goto(`${base}/privacy`);
    await engine;
    await page.waitForTimeout(500);
    await goHome(page);
    await hide(page);
    await page.waitForTimeout(1000);
    assert.equal(posts.length, 0, 'a driven browser sends nothing');
    assert.equal(await page.evaluate(() => localStorage.getItem('law.measure.day')), null, 'and nothing is kept');
    assert.deepEqual(errors, []);
    console.log('ok   a browser a program drives sends nothing');
    await context.close();
  }
} finally {
  await browser.close();
  await server.close();
}
console.log('measure: all passed');
