// The site on the sample, in a browser (tools/ci/smoke.sh boots it: Django on the sample, the drawing service, the
// built web). This script serves the built web itself (Vite's preview, with the addresses the server's nginx sends to
// Django sent to Django) and walks it in headless Chromium: the home; the 2011 Constitution and its articles; an
// article with its official French; Bulletin issue 7278; a sign-up, the code from its letter, a sign-out and a sign-in.
// No page may log an error in the browser's console.
//
//   DJANGO=http://127.0.0.1:<port> LETTERS=<dir> node e2e/smoke.e2e.mjs
//
// DJANGO: where Django answers, on the sample (manage.py load_sample), writing its letters to files
// (EMAIL_BACKEND=django.core.mail.backends.filebased.EmailBackend, EMAIL_FILE_PATH=<dir>, the same dir as LETTERS).
// WEB_DIST: the built web (default web/dist); WEB_PORT: the preview's port (default 0, a free one). SHOTS=<dir> saves
// a screenshot of each step, and of the page where a step failed. The account it makes is on example.org, with a
// password drawn for the run. The existing e2e scripts need the whole corpus and both dev servers; this one, the sample.
import assert from 'node:assert/strict';
import { randomBytes } from 'node:crypto';
import { readdirSync, readFileSync, statSync } from 'node:fs';
import path from 'node:path';
import { chromium } from 'playwright';
import { preview } from 'vite';

const web = path.resolve(import.meta.dirname, '..');
const django = process.env.DJANGO;
const letters = process.env.LETTERS;
assert.ok(django, 'DJANGO=<the address Django answers on>');
assert.ok(letters, 'LETTERS=<the folder EMAIL_FILE_PATH names>');
const dist = path.resolve(process.env.WEB_DIST ?? path.join(web, 'dist'));
const shots = process.env.SHOTS;

// What deploy/nginx.conf sends to Django rather than to the built files (a law's address has no prerendered file here).
const DJANGO_PATHS = ['/api/', '/admin/', '/static/', '/oauth/', '/.well-known/', '/ma/', '/robots.txt', '/sitemap',
  '^/bo/[a-z_]+/[0-9]+(-[a-z]+)?(\\?|$)', '^/words(/[^/?]+)?(\\?|$)', '^/texts/[0-9]+(\\?|$)', '^/search(\\?|$)'];

/** A letter's plain-text words (Django's file backend writes MIME, the parts in base64). */
function words(mime) {
  const part = mime.match(/Content-Type: text\/plain; charset="utf-8"\nContent-Transfer-Encoding: (\S+)\n\n([\s\S]*?)\n--=/);
  return part[1] === 'base64' ? Buffer.from(part[2].replace(/\s/g, ''), 'base64').toString('utf8') : part[2];
}

/** The words of the newest letter to `to` (one file a connection, letters split on its rule), looked for ten seconds. */
async function letterTo(to) {
  for (let i = 0; i < 50; i += 1) {
    const found = readdirSync(letters)
      .map((f) => path.join(letters, f))
      .sort((a, b) => statSync(a).mtimeMs - statSync(b).mtimeMs)
      .flatMap((f) => readFileSync(f, 'utf8').split(/\n-{79}\n/))
      .filter((mime) => mime.includes(`\nTo: ${to}\n`));
    if (found.length) return words(found.at(-1));
    await new Promise((r) => setTimeout(r, 200));
  }
  throw new Error(`no letter to ${to} in ${letters}`);
}

const server = await preview({
  root: web,
  configFile: false,
  logLevel: 'warn',
  build: { outDir: dist },
  preview: {
    host: '127.0.0.1',
    port: Number(process.env.WEB_PORT ?? 0),
    strictPort: true,
    proxy: Object.fromEntries(DJANGO_PATHS.map((p) => [p, { target: django }])),
  },
});
const base = `http://127.0.0.1:${server.httpServer.address().port}`;
console.log(`smoke: the built web at ${base}, Django at ${django}`);

const browser = await chromium.launch();
const errors = [];
let step = '';
const steps = [];
/** One step of the walk, which fails on its own error or on any the browser's console logged (each named with its
 *  step), and its screenshot (on a failure too). */
async function walk(name, run) {
  step = name;
  const started = Date.now();
  const shot = (what) => (shots ? page.screenshot({ path: `${shots}/${steps.length + 1}-${what}.png` }).catch(() => {}) : null);
  try {
    await run();
    await page.waitForLoadState('networkidle');
    assert.deepEqual(errors, [], 'no error in the browser\'s console');
  } catch (e) {
    await shot(`${name}-failed`);
    throw e;
  }
  await shot(name);
  steps.push(name);
  console.log(`ok   ${name} (${((Date.now() - started) / 1000).toFixed(1)} s)`);
}

const context = await browser.newContext({ viewport: { width: 1280, height: 900 }, locale: 'ar-MA' });
const page = await context.newPage();
page.on('console', (m) => { if (m.type() === 'error') errors.push(`${step}: ${m.text()} ${m.location()?.url ?? ''}`.trim()); });
page.on('pageerror', (e) => errors.push(`${step}: ${e}`));

/** Until the app has mounted (main.tsx): a page Django drew shows its words, and its buttons, before the app takes them
 *  over, and a click before that does nothing. */
const mounted = () => page.waitForFunction(() => {
  const root = document.getElementById('root');
  return Boolean(root) && Object.keys(root).some((key) => key.startsWith('__reactContainer$'));
});

const username = `smoke${randomBytes(4).toString('hex')}`;
const email = `${username}@example.org`;
const password = `pw-${randomBytes(12).toString('base64url')}`;

try {
  await walk('home', async () => {
    await page.goto(`${base}/`);
    await mounted();
    await page.getByRole('heading', { level: 1, name: 'قانون المغرب، بكلام مفهوم' }).waitFor();
    await page.getByRole('search').first().getByRole('combobox').waitFor();
  });

  await walk('law', async () => {
    // Drawn by Django with the law's words, then the app mounts over them.
    const answer = await page.goto(`${base}/ma/dahir/1-11-91`);
    const html = await answer.text();
    assert.match(html, /<div id="root" data-prerendered>/, 'the law came drawn from Django');
    assert.ok(html.includes('نظام الحكم بالمغرب نظام ملكية دستورية'), 'the drawn page holds article 1');
    await mounted();
    await page.locator('article#art_1').getByText('نظام الحكم بالمغرب نظام ملكية دستورية').waitFor();
    await page.locator('article#art_2').getByText('السيادة للأمة').waitFor();
    assert.ok(await page.locator('article[id^="art_"]').count() >= 10, 'the law shows its articles');
  });

  await walk('article', async () => {
    const answer = await page.goto(`${base}/ma/dahir/1-11-91/art_1`);
    assert.match(await answer.text(), /<div id="root" data-prerendered>/, 'the article came drawn from Django');
    await mounted();
    const article = page.locator('article#art_1');
    await article.getByText('نظام الحكم بالمغرب نظام ملكية دستورية').waitFor();
    await article.getByRole('button', { name: 'بالفرنسية' }).click();
    await article.getByText('Le Maroc est une monarchie constitutionnelle').waitFor();
  });

  await walk('issue', async () => {
    const answer = await page.goto(`${base}/bo/general_ar/7278`);
    assert.match(await answer.text(), /<div id="root" data-prerendered>/, 'the issue came drawn from Django');
    await mounted();
    await page.getByRole('heading', { level: 1 }).filter({ hasText: '7278' }).waitFor();
    await page.getByRole('link', { name: /قانون رقم 98\.18 يتعلق بالهيئة الوطنية للصيادلة/ }).first().waitFor();
  });

  await walk('sign-up', async () => {
    await page.goto(`${base}/register`);
    await mounted();
    await page.getByLabel('اسم المستخدم', { exact: true }).fill(username);
    await page.getByLabel('البريد الإلكتروني', { exact: true }).fill(email);
    await page.getByLabel('كلمة السر', { exact: true }).fill(password);
    await page.getByRole('button', { name: 'إنشاء الحساب' }).click();
    await page.waitForURL('**/account');
    // The code is in the letter Django wrote; its box is open on the account page at once.
    const code = (await letterTo(email)).match(/\n\n(\d{6})\n\n/)?.[1];
    assert.ok(code, 'the letter holds a six-digit code');
    await page.getByLabel('الرمز', { exact: true }).fill(code);
    await page.getByRole('button', { name: 'تأكيد', exact: true }).click();
    await page.locator('.ac-head').getByText('البريد مؤكَّد').waitFor();
  });

  await walk('sign-out', async () => {
    // Leaving this device is on the account's second page, «الإعدادات».
    await page.locator('.ac-tabs').getByRole('link', { name: 'الإعدادات' }).click();
    await page.waitForURL('**/account/settings');
    await page.getByRole('button', { name: 'الخروج من هذا الجهاز' }).click();
    await page.waitForURL('**/login');
  });

  await walk('sign-in', async () => {
    await page.getByLabel('اسم المستخدم أو البريد الإلكتروني', { exact: true }).fill(username);
    await page.getByLabel('كلمة السر', { exact: true }).fill(password);
    await page.getByRole('button', { name: 'دخول', exact: true }).last().click();
    await page.waitForURL('**/account/settings');
    await page.getByText(username, { exact: true }).first().waitFor();
  });

  console.log(`smoke e2e: ok, ${steps.length} steps`);
} finally {
  await browser.close();
  await server.close();
}
