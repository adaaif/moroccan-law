// The justice topic end to end (the justice review, 27 Oct 2026), on a phone and a desk. Needs a backend in
// development (DEBUG: drafts and unchecked tools show) behind the web dev server: BASE_URL (default
// http://localhost:5190). SHOTS=<dir> saves a screenshot of each step.
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

  // The band for an arrest, the one question, the doors in a case's stages, each on its court file.
  await page.goto(`${base}/topics/justice`);
  await page.getByRole('heading', { name: 'شي حد ديالك تشد؟' }).waitFor();
  await page.getByText('48 ساعة على الأكثر', { exact: false }).first().waitFor();
  await page.getByRole('button', { name: 'فين واقف فالقضية؟' }).waitFor();
  for (const stage of ['عند البوليس', 'الشكاية', 'المحامي والمساعدة القضائية', 'القضية المدنية', 'الحكم والطعن', 'من بعد الحكم']) {
    await page.getByRole('heading', { name: stage, level: 3 }).waitFor();
  }
  assert.ok((await page.getByRole('link', { name: /قاضي القرب/ }).first().innerText()).includes('5.000'), 'proximity carries its 5.000 DH');
  await shot(page, '01-hub');

  // The answer «عندي حق بغيت نطالب بيه»: 5.000 DH, 10.000 DH, the requête.
  await page.getByRole('button', { name: 'فين واقف فالقضية؟' }).click();
  await page.getByRole('radio', { name: 'عندي حق بغيت نطالب بيه' }).click();
  await page.getByText('أقل منها: قاضي القرب', { exact: false }).waitFor();
  await shot(page, '02-claimant');

  // The custody journey ends before the prosecutor.
  await page.goto(`${base}/topics/justice/journeys/custody`);
  await page.getByText('ثلاثين دقيقة', { exact: false }).first().waitFor();
  await shot(page, '03-custody-journey');

  // A civil appeal notified on Thursday 1 October 2026: 31 October counted, 1 November a Sunday → Monday 2 November.
  await page.goto(`${base}/topics/justice/tools/deadline?k=appeal&d=2026-10-01`);
  await page.getByText('الاثنين، 2 نونبر 2026', { exact: false }).first().waitFor();
  await shot(page, '04-deadline');

  // A complaint for a délit of 15 March 2023 lapses on 15 March 2027.
  await page.goto(`${base}/topics/justice/tools/deadline?k=delit&d=2023-03-15`);
  await page.getByText('15 مارس 2027', { exact: false }).first().waitFor();

  // Custody from 22:30 on 27 October: 48 hours end on the 29th at 22:30.
  await page.goto(`${base}/topics/justice/tools/custody?a=2026-10-27T22:30&c=ordinary`);
  await page.getByText('22:30', { exact: false }).first().waitFor();
  await shot(page, '05-custody');

  // A debt of 4.000 DH goes to the proximity judge; 40.000 DH can go up to cassation.
  await page.goto(`${base}/topics/justice/tools/court?s=debt&m=4000`);
  await page.getByText('قاضي القرب').first().waitFor();
  await shot(page, '06-court-small');
  await page.goto(`${base}/topics/justice/tools/court?s=debt&m=40000`);
  await page.getByText('محكمة الاستئناف').first().waitFor();
  await page.getByText('كتنظر فالقانون', { exact: false }).first().waitFor();

  // Ninety days of prison: 270 hours of community work, 9.000 to 180.000 DH of day-fines.
  await page.goto(`${base}/topics/justice/tools/alternative?d=90&f=yes`);
  await page.getByText('270', { exact: false }).first().waitFor();
  await page.getByText('180.000 درهم', { exact: false }).first().waitFor();
  await shot(page, '07-alternative');

  // A desk: the instruments in the side column.
  const desk = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const d = await desk.newPage();
  watch(d);
  await d.goto(`${base}/topics/justice`);
  await d.getByRole('heading', { name: 'شنو كتحتاج فالقضية ديالك؟' }).waitFor();
  await shot(d, '08-desk');
  await d.goto(`${base}/topics/justice/tools/deadline?k=opposition&d=2026-10-21`);
  await d.getByText('9 نونبر 2026', { exact: false }).first().waitFor();
  await shot(d, '09-desk-deadline');

  assert.deepEqual(errors, []);
  console.log('justice: ok');
} finally {
  await browser.close();
}
