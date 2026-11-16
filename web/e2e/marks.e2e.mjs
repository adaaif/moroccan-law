// A search's marks on a phone (H1–H6, 29 Oct 2026): the word searched lit in the article a search opened, the line under
// the law, ‹ › to the next article holding it (landing on it, not at the law's top), «إخفاء», the French; and the outline's
// jump to an article, which the top-of-page reset sent back to the law's top. Needs both dev servers: BASE_URL (default
// http://localhost:5190).
import { chromium } from 'playwright';
const CHANNEL = process.env.CHANNEL;

const base = process.env.BASE_URL ?? 'http://localhost:5190';
const browser = await chromium.launch(CHANNEL ? { channel: CHANNEL } : {});
const failed = [];
const check = (ok, what) => { console.log(`${ok ? 'ok  ' : 'FAIL'} ${what}`); if (!ok) failed.push(what); };
const phone = { viewport: { width: 412, height: 915 }, isMobile: true, hasTouch: true, serviceWorkers: 'block' };
try {
  const ar = await browser.newContext({ ...phone, locale: 'ar-MA' });
  const page = await ar.newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  const lit = () => page.evaluate(() => CSS.highlights?.get('search-marks')?.size ?? 0);
  const top = (id) => page.evaluate((x) => document.getElementById(x)?.getBoundingClientRect().top ?? -1, id);
  const line = page.locator('[role=region]');

  await page.goto(`${base}/search?q=${encodeURIComponent('كراء')}`, { waitUntil: 'networkidle' });
  const link = page.locator('main ol li a[href*="hl="]').first();
  check(await link.count() > 0, 'a result carries the words searched');
  await page.goto(`${base}/ma/loi/67-12/art_3?hl=${encodeURIComponent('كراء')}`, { waitUntil: 'networkidle' });
  await page.waitForTimeout(1200);
  check(await lit() > 0, 'the word is lit in the law');
  check((await line.innerText()).includes('كراء'), 'the line names the words');
  await line.locator('button[aria-label*="الموالية"]').click();
  await page.waitForLoadState('networkidle'); await page.waitForTimeout(1200);
  check(page.url().includes('/art_4?hl='), '‹ › goes to the next article holding the word');
  const t4 = await top('art_4');
  check(t4 >= 0 && t4 < 300, `and lands on it (its top at ${Math.round(t4)} px)`);
  await line.getByRole('button', { name: 'إخفاء' }).click();
  await page.waitForTimeout(600);
  check(await lit() === 0 && await line.count() === 0 && !page.url().includes('hl='), '«إخفاء» puts the marks away');

  await page.goto(`${base}/ma/loi/67-12/art_2`, { waitUntil: 'networkidle' });
  await page.waitForTimeout(800);
  await page.getByRole('button', { name: /الفهرس/ }).first().click();
  await page.getByPlaceholder('رقمها').first().fill('10');
  await page.getByPlaceholder('رقمها').first().press('Enter');
  await page.waitForTimeout(1200);
  const t10 = await top('art_10');
  check(t10 >= 0 && t10 < 300, `the outline's jump lands on art. 10 (its top at ${Math.round(t10)} px)`);
  check(!errors.length, `no page error${errors.length ? `: ${errors[0]}` : ''}`);

  const fr = await browser.newContext({ ...phone, locale: 'fr-MA' });
  await fr.addInitScript(() => localStorage.setItem('law.lang', 'fr'));
  const p2 = await fr.newPage();
  await p2.goto(`${base}/ma/loi/65-99/art_35?hl=licenciement`, { waitUntil: 'networkidle' });
  await p2.waitForTimeout(1500);
  check(await p2.evaluate(() => CSS.highlights?.get('search-marks')?.size ?? 0) > 0, 'a French word is lit in the French');
} finally {
  await browser.close();
}
if (failed.length) process.exit(1);
