// The digital topic end to end (the digital review, 27 Oct 2026), on a phone and a desk. Needs a backend in
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

  // The band for extortion, the one question, the doors in their stages, each on its message bubble.
  await page.goto(`${base}/topics/digital`);
  await page.getByRole('heading', { name: 'كيبتزوك ولا نشرو صورك؟' }).waitFor();
  await page.getByText('من سنة إلى خمس سنوات', { exact: false }).first().waitFor();
  await page.getByRole('button', { name: 'شنو كتدير فالأنترنت؟' }).waitFor();
  for (const stage of ['معطياتي الشخصية', 'تعدّاو عليّا فالأنترنت', 'معلومة من الإدارة', 'المحتوى ديالي وديال الناس']) {
    await page.getByRole('heading', { name: stage, level: 3 }).waitFor();
  }
  assert.ok((await page.getByRole('link', { name: /معطيات غالطة/ }).first().innerText()).includes('10'), 'the correction carries its 10 days');
  await shot(page, '01-hub');

  // The answer «بغيت معلومة من الإدارة»: 20 working days, 3 days, 60 days.
  await page.getByRole('button', { name: 'شنو كتدير فالأنترنت؟' }).click();
  await page.getByRole('radio', { name: 'بغيت معلومة من الإدارة' }).click();
  await page.getByText('فالحالة المستعجلة', { exact: false }).waitFor();
  await shot(page, '02-citizen');

  // The extortion journey.
  await page.goto(`${base}/topics/digital/journeys/extortion`);
  await page.getByText('الزوج أو الطليق', { exact: false }).first().waitFor();
  await shot(page, '03-extortion');

  // The law answering: images published by a fiancé → one to five years.
  await page.goto(`${base}/topics/digital/tools/offence?w=intimate&a=yes&d=2026-10-01`);
  await page.getByText('المس بالحياة الخاصة').first().waitFor();
  await page.getByText('الحبس من سنة حتى 5 سنين', { exact: false }).first().waitFor();
  await shot(page, '04-offence');

  // An insult published on 31 May lapses on 30 November.
  await page.goto(`${base}/topics/digital/tools/offence?w=insult&d=2026-05-31`);
  await page.getByText('30 نونبر 2026', { exact: false }).first().waitFor();

  // A request received on Monday 2 November: the answer by Wednesday 2 December (6 and 18 November are holidays).
  await page.goto(`${base}/topics/digital/tools/info?d=2026-11-02`);
  await page.getByText('2 دجنبر 2026', { exact: false }).first().waitFor();
  await shot(page, '05-info');

  // The data letter asking access and erasure.
  await page.goto(`${base}/topics/digital/tools/letter?r=access,erase&c=${encodeURIComponent('شركة المثال')}&d=2026-10-01`);
  await page.getByText('إلى: شركة المثال').waitFor();
  await page.getByText('الاثنين، 12 أكتوبر 2026', { exact: false }).first().waitFor();
  await shot(page, '06-letter');

  // Copyright: an author who died on 14 July 1956 is free from 15 July 2026.
  await page.goto(`${base}/topics/digital/tools/copyright?k=author&d=1956-07-14`);
  await page.getByText('15 يوليوز 2026', { exact: false }).first().waitFor();
  await shot(page, '07-copyright');

  // A desk: the instruments in the side column.
  const desk = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const d = await desk.newPage();
  watch(d);
  await d.goto(`${base}/topics/digital`);
  await d.getByRole('heading', { name: 'شنو كتحتاج فالأنترنت؟' }).waitFor();
  await shot(d, '08-desk');
  await d.goto(`${base}/topics/digital/tools/offence?w=extortion`);
  await d.getByText('الابتزاز').first().waitFor();
  await shot(d, '09-desk-offence');

  assert.deepEqual(errors, []);
  console.log('digital: ok');
} finally {
  await browser.close();
}
