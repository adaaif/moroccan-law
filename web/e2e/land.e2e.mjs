// The land topic end to end (the land review, 26 Oct 2026), on a phone and a desk. Needs a backend in development
// (DEBUG: drafts and unchecked tools show) behind the web dev server, with the land's places built
// (`manage.py build_land_places`): BASE_URL (default http://localhost:5190). SHOTS=<dir> saves a screenshot of each step.
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

  // M5: the papers that start a clock, in a band; M4: the one question; M3: the doors in a plot's life, none folded.
  await page.goto(`${base}/topics/land`);
  await page.getByRole('heading', { name: 'توصلت بورقة على أرضك؟' }).waitFor();
  await page.getByText('إعلان انتهاء التحديد فالجريدة الرسمية').waitFor();
  await page.getByRole('button', { name: 'أرضك شنو هي؟' }).waitFor();
  for (const stage of ['قبل ما تملك', 'تثبت ملكك', 'بين الشركاء', 'البني', 'الدولة والجماعة', 'فمواضيع أخرى']) {
    await page.getByRole('heading', { name: stage, level: 3 }).waitFor();
  }
  assert.ok((await page.getByRole('link', { name: /شريكي باع نصيبو/ }).innerText()).includes('30'), 'pre-emption carries its 30 days');
  await shot(page, '01-hub');

  // The answer «محفظة»: three facts with their articles, and possession fades with art. 261's reason.
  await page.getByRole('button', { name: 'أرضك شنو هي؟' }).click();
  await page.getByRole('radio', { name: 'محفظة (عندها رسم عقاري)' }).click();
  await page.getByText('الرسم العقاري لا يقبل الطعن').waitFor();
  await page.getByText('ما كتطبقش على أرض محفظة', { exact: false }).waitFor();
  await shot(page, '02-titled');

  // M6, M7: the last change in words; the half year's texts are the land's own.
  await page.goto(`${base}/topics/land/changes`);
  await page.getByText('بيع العقار بمحرر رسمي وحده', { exact: false }).first().waitFor();

  // A journey with its day and its office.
  await page.goto(`${base}/topics/land/journeys/oppose`);
  await page.getByText('متى نشر الإعلان عن انتهاء التحديد', { exact: false }).first().waitFor();
  await shot(page, '03-oppose');

  // M11: the clock counts a notice published on a known day.
  await page.goto(`${base}/topics/land/tools/clock?p=oppose&d=2026-09-02`);
  await page.getByText('الاثنين، 2 نونبر 2026', { exact: false }).first().waitFor();
  await shot(page, '04-clock');

  // M12: the permit's road, the tacit permit two months after the filing.
  await page.goto(`${base}/topics/land/tools/permit?d=2026-08-03`);
  await page.getByText('إلا سكت رئيس الجماعة: الرخصة مسلمة').waitFor();
  await page.getByText('السبت، 3 أكتوبر', { exact: false }).first().waitFor();

  // M13: before buying, drawn as the certificate; nothing ticked, the verdict names what is missing.
  await page.goto(`${base}/topics/land/tools/before`);
  await page.getByText('قبل ما تشري: البقعة ديالك').waitFor();
  await page.getByText('لم تعلّم على هذه النقط', { exact: false }).waitFor();

  // M8–M10: the finder by a commune, then by a title number; a commune can be followed.
  await page.goto(`${base}/topics/land/tools/find?q=${encodeURIComponent('رباط الخير')}`);
  await page.getByRole('heading', { name: 'رباط الخير', level: 2 }).waitFor();
  await page.getByRole('button', { name: /متابعة/ }).first().waitFor();
  await shot(page, '05-find');
  await page.goto(`${base}/topics/land/tools/find?q=F%2F18820`);
  await page.getByText('2766', { exact: false }).first().waitFor();

  // A desk: the band beside, the instruments in the side column.
  const desk = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const d = await desk.newPage();
  watch(d);
  await d.goto(`${base}/topics/land`);
  await d.getByRole('heading', { name: 'شنو وقع ليك؟' }).waitFor();
  await shot(d, '06-desk');

  assert.deepEqual(errors, []);
  console.log('land: ok');
} finally {
  await browser.close();
}
