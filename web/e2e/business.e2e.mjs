// The business topic end to end (the business review, 27 Oct 2026), on a phone and a desk. Needs a backend in
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

  // The band for a bounced cheque, the one question, the doors in a business's stages, each on its stamp.
  await page.goto(`${base}/topics/business`);
  await page.getByRole('heading', { name: 'شيك رجع بلا رصيد؟' }).waitFor();
  await page.getByText('داخل يومين من الرفض', { exact: false }).first().waitFor();
  await page.getByRole('button', { name: 'شنو كتدير؟' }).waitFor();
  for (const stage of ['كنبدا', 'كنخدم', 'الشيك', 'إلا تعقدات', 'كنكبر']) {
    await page.getByRole('heading', { name: stage, level: 3 }).waitFor();
  }
  assert.ok((await page.getByRole('link', { name: /السجل التجاري/ }).first().innerText()).includes('3'), 'the register carries its 3 months');
  await shot(page, '01-hub');

  // The answer «تعاونية»: five members, two days for the name, 30 % with third parties.
  await page.getByRole('button', { name: 'شنو كتدير؟' }).click();
  await page.getByRole('radio', { name: 'فتعاونية' }).click();
  await page.getByText('حد المعاملات مع الأغيار', { exact: false }).waitFor();
  await shot(page, '02-cooperative');

  // A journey ends at Barid Al-Maghrib with the registration.
  await page.goto(`${base}/topics/business/journeys/auto-start`);
  await page.getByText('41 مهنة', { exact: false }).first().waitFor();
  await shot(page, '03-auto-start');

  // The forms: a jeweller alone is no auto-entrepreneur; the trader and the SARL stay open.
  await page.goto(`${base}/topics/business/tools/form?q=${encodeURIComponent('bijoutier')}`);
  await page.getByText('تجار التفصيل في الذهب والحلي والمجوهرات').first().waitFor();
  await page.getByText('المهنة ديالك من المهن المستثناة', { exact: false }).waitFor();
  await shot(page, '04-form');

  // The cheque: written on 1 September, back on the 10th; the injunction by the 12th, three months to settle.
  await page.goto(`${base}/topics/business/tools/cheque?s=drawer&d=2026-09-01&r=2026-09-10&m=30000&n=2`);
  await page.getByText('السبت، 12 شتنبر 2026', { exact: false }).first().waitFor();
  await page.getByText('الخميس، 10 دجنبر 2026', { exact: false }).first().waitFor();
  await shot(page, '05-cheque');

  // A late invoice: 1 May, 60 days, 100,000 DH, at 2.25 %: the first month's 2,250 DH on its own line.
  await page.goto(`${base}/topics/business/tools/late?i=2026-05-01&m=100000&p=2026-08-15`);
  await page.getByText('الثلاثاء، 30 يونيو 2026', { exact: false }).first().waitFor();
  await page.getByText('2.250 درهم').first().waitFor();
  await shot(page, '06-late');

  // The company's year: the assembly six months after the close.
  await page.goto(`${base}/topics/business/tools/year?y=2026-12-31`);
  await page.getByText('الأربعاء، 30 يونيو 2027', { exact: false }).first().waitFor();

  // A desk: the instruments in the side column.
  const desk = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const d = await desk.newPage();
  watch(d);
  await d.goto(`${base}/topics/business`);
  await d.getByRole('heading', { name: 'شنو كتحتاج فالمقاولة ديالك؟' }).waitFor();
  await shot(d, '07-desk');

  assert.deepEqual(errors, []);
  console.log('business: ok');
} finally {
  await browser.close();
}
