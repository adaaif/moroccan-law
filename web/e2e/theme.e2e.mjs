// Run against the built preview: BASE_URL=http://127.0.0.1:5192 node e2e/theme.e2e.mjs
import assert from 'node:assert/strict';
import { chromium } from 'playwright';

const base = process.env.BASE_URL ?? 'http://127.0.0.1:5192';
const browser = await chromium.launch();
try {
  const context = await browser.newContext({ colorScheme: 'light' });
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await page.goto(base);
  const toggle = page.getByRole('button', { name: 'الوضع الليلي', exact: true });
  await toggle.waitFor();
  await toggle.click();
  await page.waitForFunction(() => document.documentElement.dataset.theme === 'dark');
  await page.reload();
  await page.waitForFunction(() => document.documentElement.dataset.theme === 'dark');
  assert.equal(await toggle.getAttribute('aria-pressed'), 'true');

  const other = await context.newPage();
  await other.goto(base);
  await other.getByRole('button', { name: 'الوضع الليلي', exact: true }).waitFor();
  await toggle.click();
  await other.waitForFunction(() => document.documentElement.dataset.theme === 'light');
  await page.evaluate(() => localStorage.removeItem('law.reading'));
  await other.waitForFunction(() => !document.documentElement.dataset.theme);
  await other.emulateMedia({ colorScheme: 'dark' });
  await other.waitForFunction(() => document.querySelector('button[aria-label="الوضع الليلي"]').getAttribute('aria-pressed') === 'true');
  await other.getByRole('button', { name: 'الوضع الليلي', exact: true }).click();
  await other.waitForFunction(() => document.documentElement.dataset.theme === 'light');
  await page.waitForFunction(() => document.documentElement.dataset.theme === 'light');
  await page.evaluate(() => localStorage.clear());
  await other.waitForFunction(() => !document.documentElement.dataset.theme);

  for (const language of ['ar', 'fr']) {
    await page.evaluate((lang) => localStorage.setItem('law.lang', lang), language);
    for (const width of [360, 390, 768, 1024, 1280]) {
      await page.setViewportSize({ width, height: 900 });
      await page.reload();
      await page.getByRole('button', { name: language === 'ar' ? 'الوضع الليلي' : 'Mode nuit', exact: true }).waitFor();
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `${language} overflow at ${width}px`);
    }
  }
  assert.deepEqual(errors, []);

  // Block app JS: the CSS must still paint the saved theme, before hydration.
  for (const theme of ['light', 'dark']) {
    const firstPaint = await browser.newContext({ colorScheme: theme === 'dark' ? 'light' : 'dark',
      storageState: { cookies: [], origins: [{ origin: new URL(base).origin, localStorage: [{ name: 'law.reading', value: JSON.stringify({ theme }) }] }] } });
    const initial = await firstPaint.newPage();
    await initial.route('**/*.js', (route) => route.abort());
    await initial.goto(base);
    assert.equal(await initial.evaluate(() => document.documentElement.dataset.theme), theme);
    assert.equal(await initial.evaluate(() => getComputedStyle(document.documentElement).backgroundColor), theme === 'dark' ? 'rgb(19, 17, 26)' : 'rgb(244, 242, 238)');
    await firstPaint.close();
  }
  const blocked = await browser.newContext();
  await blocked.addInitScript(() => { Object.defineProperty(window, 'localStorage', { get() { throw new Error('blocked'); } }); });
  const privatePage = await blocked.newPage();
  await privatePage.goto(base);
  await privatePage.getByRole('button', { name: 'الوضع الليلي', exact: true }).click();
  await privatePage.waitForFunction(() => ['light', 'dark'].includes(document.documentElement.dataset.theme));
  await blocked.close();
  console.log('theme e2e: toggle, persistence, cross-tab updates/reset, device changes, first paint, blocked storage and responsive Arabic/French headers passed');
} finally {
  await browser.close();
}
