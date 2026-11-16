// The Moroccan-design review (U1–U20, 25 Oct 2026), end to end on a phone and a desk.
// BASE_URL (default http://localhost:5190) with Django behind it; SHOTS=<dir> saves a screenshot of each step.
import assert from 'node:assert/strict';
import { chromium } from 'playwright';
const CHANNEL = process.env.CHANNEL;

const base = process.env.BASE_URL ?? 'http://localhost:5190';
const shots = process.env.SHOTS;
const shot = async (page, name, fullPage = false) => {
  if (shots) await page.screenshot({ path: `${shots}/${name}.png`, fullPage });
};

const browser = await chromium.launch(CHANNEL ? { channel: CHANNEL } : {});
const errors = [];
const watch = (page) => {
  page.on('pageerror', (e) => errors.push(String(e)));
  page.on('console', (m) => m.type() === 'error' && !/favicon|404|401/.test(m.text()) && errors.push(m.text()));
};

try {
  const phone = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, deviceScaleFactor: 2 });
  const page = await phone.newPage();
  watch(page);

  // ── U5: the phone's back closes a sheet and leaves the reader on the page ─────
  await page.goto(`${base}/`);
  await page.goto(`${base}/ma/loi/70-03`);
  await page.getByRole('heading', { level: 1 }).waitFor();
  const url = page.url();
  await page.getByRole('button', { name: /أدوات أخرى/ }).first().click();
  const dialog = page.getByRole('dialog');
  await dialog.waitFor();
  await shot(page, 'u5-sheet-open');
  await page.goBack();
  await dialog.waitFor({ state: 'detached' });
  assert.equal(page.url(), url, 'back closed the sheet and stayed on the text');
  // Closed another way, it takes its history entry with it: one back leaves the text.
  await page.getByRole('button', { name: /أدوات أخرى/ }).first().click();
  await dialog.waitFor();
  await page.keyboard.press('Escape');
  await dialog.waitFor({ state: 'detached' });
  await page.waitForTimeout(100);
  await page.goBack();
  await page.waitForURL(`${base}/`);

  // An article's own «⋯» is a sheet from the bottom: pulled down by its handle, it closes.
  await page.goto(`${base}/ma/loi/70-03`);
  await page.getByRole('button', { name: 'إجراءات أخرى' }).first().click();
  await dialog.waitFor();
  const handle = await page.locator('[data-handle]').boundingBox();
  const cdp = await phone.newCDPSession(page);
  const touch = (type, y) => cdp.send('Input.dispatchTouchEvent', { type, touchPoints: type === 'touchEnd' ? [] : [{ x: handle.x + 40, y }] });
  await touch('touchStart', handle.y + 10);
  for (let dy = 20; dy <= 400; dy += 40) await touch('touchMove', handle.y + 10 + dy);
  await touch('touchEnd');
  await dialog.waitFor({ state: 'detached' });
  assert.equal(page.url(), `${base}/ma/loi/70-03`, 'dragged down, the sheet closed and the text stayed');

  // ── U1, U3, U7: the twelve doors on the first screen; a door opens its topic (through a view transition) ──
  await page.goto(`${base}/`);
  const doors = page.locator('a[href^="/topics/"]:has([data-door])');
  await doors.first().waitFor();
  assert.equal(await doors.count(), 12);
  const lastDoor = await doors.nth(11).boundingBox();
  assert.ok(lastDoor.y + lastDoor.height <= 844 - 56, 'the twelfth door is above the bottom bar on the first screen');
  await shot(page, 'u3-home');
  await doors.first().click();
  await page.waitForURL(`${base}/topics/family`);
  await page.locator('[data-vt="topic-arch"]').waitFor();

  // ── U6: an article the law names opens as a peek on a phone ───────────────────
  await page.goto(`${base}/ma/loi/52-05/art_99`);
  const ref = page.locator('#art_99').getByRole('link', { name: 'المادة 29' }).first();
  await ref.waitFor();
  const before = page.url();
  await ref.click();
  await dialog.waitFor();
  await dialog.getByText('فتح المادة').waitFor();
  await shot(page, 'u6-peek');
  assert.equal(page.url(), before, 'the peek keeps the reader on the article');
  await page.goBack();
  await dialog.waitFor({ state: 'detached' });
  assert.equal(page.url(), before);

  // ── U8: the app offered once, after an article is kept; «لا، شكرا» is for good ────────
  const fresh = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
  const p8 = await fresh.newPage();
  watch(p8);
  const androidOffers = () => p8.evaluate(() => {
    const e = Object.assign(new Event('beforeinstallprompt'), { prompt: async () => {}, userChoice: Promise.resolve({ outcome: 'dismissed' }) });
    window.dispatchEvent(e);
  });
  await p8.goto(`${base}/ma/loi/70-03`);
  await p8.getByRole('heading', { level: 1 }).waitFor();
  await androidOffers();
  const offer = p8.getByRole('complementary', { name: 'زيد «قانون» لشاشة التيليفون' });
  assert.equal(await offer.count(), 0, 'nothing on a first visit');
  await p8.locator('#art_1').getByRole('button', { name: 'حفظ' }).click();
  await offer.waitFor();
  await shot(p8, 'u8-offer');
  await offer.getByRole('button', { name: 'لا، شكرا' }).click();
  await offer.waitFor({ state: 'detached' });
  await p8.reload();
  await androidOffers();
  await p8.locator('#art_2').getByRole('button', { name: 'حفظ' }).click();
  await p8.waitForTimeout(400);
  assert.equal(await offer.count(), 0, 'never again');
  await fresh.close();

  assert.deepEqual(errors, []);
  console.log('ok: moroccan');
} finally {
  await browser.close();
}
