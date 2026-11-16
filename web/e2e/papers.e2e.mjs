// The papers topic end to end (the papers review, 27 Oct 2026), on a phone and a desk. Needs a backend in development
// (DEBUG: drafts and unchecked tools show) behind the web dev server: BASE_URL (default http://localhost:5190).
// SHOTS=<dir> saves a screenshot of each step.
import assert from 'node:assert/strict';
import { chromium } from 'playwright';
const CHANNEL = process.env.CHANNEL;

const base = process.env.BASE_URL ?? 'http://localhost:5190';
const shots = process.env.SHOTS;
const shot = async (page, name) => {
  if (shots) await page.screenshot({ path: `${shots}/${name}.png`, fullPage: true, style: 'nav.fixed.bottom-0 { display: none !important; }' });
};

const browser = await chromium.launch(CHANNEL ? { channel: CHANNEL } : {});
const errors = [];
const watch = (page) => {
  page.on('pageerror', (e) => errors.push(String(e)));
  page.on('console', (m) => m.type() === 'error' && !/favicon|404|401/.test(m.text()) && errors.push(m.text()));
};

try {
  const phone = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
  const page = await phone.newPage();
  watch(page);

  // The band for a lost card, the one question, the doors in a paper's stages, each on the card with its figure.
  await page.goto(`${base}/topics/papers`);
  await page.getByRole('heading', { name: 'ضاعت ليك البطاقة ولا الباسبور؟' }).waitFor();
  await page.getByText('التصريح بالضياع أو السرقة', { exact: false }).first().waitFor();
  await page.getByRole('button', { name: 'فين كتقضي الوراق ديالك؟' }).waitFor();
  for (const stage of ['البطاقة الوطنية', 'الحالة المدنية', 'الباسبور والجنسية', 'فالإدارة: حقوقك فالشباك', 'السجل العدلي']) {
    await page.getByRole('heading', { name: stage, level: 3 }).waitFor();
  }
  assert.ok((await page.getByRole('link', { name: /الإدارة ما جاوباتنيش/ }).innerText()).includes('60'), 'the counter carries its 60 days');
  await shot(page, '01-hub');

  // The answer «فالقنصلية»: a year to declare, the consular registration, the minors' passport stamp.
  await page.getByRole('button', { name: 'فين كتقضي الوراق ديالك؟' }).click();
  await page.getByRole('radio', { name: 'فالقنصلية (ساكن فالخارج)' }).click();
  await page.getByText('شهادة التسجيل القنصلي كتعوض شهادة السكنى', { exact: false }).waitFor();
  await shot(page, '02-abroad');

  // A journey ends at the police's service with the card.
  await page.goto(`${base}/topics/papers/journeys/card-first`);
  await page.getByText('أربع صور', { exact: false }).first().waitFor();
  await shot(page, '03-card-first');

  // The card: moved house, so renew; the card drawn with its end date and its machine line.
  await page.goto(`${base}/topics/papers/tools/card?b=1995-04-12&h=yes&e=2029-03-02&ev=moved`);
  await page.getByText('خاصك تجددها').first().waitFor();
  await page.getByText('950412<290302', { exact: false }).waitFor();
  await shot(page, '04-card');

  // The administration's road: 60 complete days, then 30 to appeal.
  await page.goto(`${base}/topics/papers/tools/counter?d=2026-08-20`);
  await page.getByText('آخر نهار للطعن الإداري', { exact: false }).first().waitFor();
  await page.getByText('الجمعة، 20 نونبر 2026', { exact: false }).first().waitFor();
  await shot(page, '05-counter');

  // The first name: a title found, never «accepted».
  await page.goto(`${base}/topics/papers/tools/names?n=${encodeURIComponent('مولاي إدريس')}`);
  await page.getByText('قاعدة وحدة ما تحترماتش').waitFor();
  await page.getByText('فيها «مولاي»').waitFor();

  // Rehabilitation: a fine never shows on card no. 3.
  await page.goto(`${base}/topics/papers/tools/rehab?k=fine&d=2026-01-31`);
  await page.getByText('ما كيبانش فيها').waitFor();

  // A desk: the instruments in the side column.
  const desk = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const d = await desk.newPage();
  watch(d);
  await d.goto(`${base}/topics/papers`);
  await d.getByRole('heading', { name: 'شنو خاصك فالوراق؟' }).waitFor();
  await shot(d, '06-desk');

  assert.deepEqual(errors, []);
  console.log('papers: ok');
} finally {
  await browser.close();
}
