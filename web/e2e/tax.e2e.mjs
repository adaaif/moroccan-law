// The tax topic end to end (the tax review, 26 Oct 2026), on a phone and a desk. Needs a backend in development
// (DEBUG: drafts and unchecked tools show) behind the web dev server, with the CGI loaded (`load_dgi`): BASE_URL (default
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

  // T9: the year's dates in a band, the next two with their days; T7: the one question; T8: the doors in stages.
  await page.goto(`${base}/topics/tax`);
  await page.getByRole('heading', { name: 'الآجال ديالك' }).waitFor();
  assert.ok((await page.getByText(/باقي|اليوم آخر/).count()) >= 2, 'two dates with their days left');
  await page.getByRole('button', { name: 'منين كيجيك الدخل؟' }).waitFor();
  for (const stage of ['شنو كيدخل ليك', 'شنو عندك', 'بعتي، شريتي ولا ورثتي', 'خدام بحسابك', 'إلا ما تحلاتش', 'فالخارج ولا عندك شركة']) {
    await page.getByRole('heading', { name: stage, level: 3 }).waitFor();
  }
  // T6: the salary door's stamp carries the top rate.
  assert.ok((await page.getByRole('link', { name: /شحال كيقطعو ليا من الأجرة؟/ }).first().innerText()).includes('37%'));
  await shot(page, '01-hub');

  // The answer «متقاعد»: three facts with their articles; the band keeps the dates that concern a retired reader.
  await page.getByRole('button', { name: 'منين كيجيك الدخل؟' }).click();
  await page.getByRole('radio', { name: 'متقاعد' }).click();
  await page.getByText('على معاش نظام التقاعد الأساسي منذ 2026').waitFor();
  await shot(page, '02-retired');

  // T10: the salary, 10,000 a month, no dependent, 2026; then two dependents take 1,200 off the year's tax.
  await page.goto(`${base}/topics/tax/tools/salary?y=2026&g=10000&k=0`);
  await page.getByText('الأجرة الصافية فالشهر').waitFor();
  await page.waitForTimeout(1200);
  const net0 = await page.locator('[data-answer] p.text-h2').innerText();
  await page.goto(`${base}/topics/tax/tools/salary?y=2026&g=10000&k=2`);
  await page.waitForTimeout(1200);
  const net2 = await page.locator('[data-answer] p.text-h2').innerText();
  assert.match(net0, /8[.,\s]?903,64/, `net with no dependent: ${net0}`);
  assert.match(net2, /9[.,\s]?003,64/, `net with two dependents: ${net2}`);
  assert.notEqual(net0, net2);
  await page.getByText('الجدول بالأرقام').click();
  await shot(page, '03-salary');

  // The work payslip's tax line is computed now.
  await page.goto(`${base}/topics/work/tools/pay?w=12000`);
  await page.getByText('الصافي بعد الضريبة').first().waitFor();
  await shot(page, '04-payslip');

  // T15, T16: the home's taxes and the vignette.
  await page.goto(`${base}/topics/tax/tools/local?w=home&v=24000&m=1&u=urban`);
  await page.getByText('رسم الخدمات الجماعية').first().waitFor();
  await page.goto(`${base}/topics/tax/tools/car?cv=6&f=diesel&p=0&m=0`);
  await page.waitForTimeout(800);
  assert.match(await page.locator('[data-answer]').innerText(), /700/);
  await shot(page, '05-car');

  // The code itself: art. 73 in Arabic with the scale, the DGI's edition named.
  await page.goto(`${base}/ma/code/cgi/art_73`);
  await page.getByText('شريحة الدخل إلى غاية 40 000 درهم').first().waitFor();
  await shot(page, '06-code');

  // The finance-bill review: the home's line, the bill's door first, its page under the bill's band, the claims
  // page's sources, the open tool's five years with 442.71 at 10,000 gross, the bill's text with its mark, and a code
  // article's band opening what the bill proposes.
  await page.goto(`${base}/`);
  await page.getByRole('link', { name: /فالبرلمان دابا: مشروع قانون المالية 2027/ }).waitFor();
  await page.goto(`${base}/topics/tax`);
  await page.getByRole('heading', { name: 'فالبرلمان دابا', level: 3 }).waitFor();
  await page.getByRole('link', { name: /مشروع 2027: شنو غادي يتبدل ليك؟/ }).click();
  // The bill-page review: the band with its stops, the salaried section open (C1), the first change as an
  // amendment line, the others one line each; picking another reader opens theirs.
  await page.getByText('مشروع قانون، ماشي قانون؛ البرلمان يقدر يبدلو.').waitFor();
  // The bill-story review: the guess first (C2), then the curve with the reader's sentence (Y1); the handle moves
  // with the keyboard (Y5) and the sentence follows.
  await page.getByRole('button', { name: 'وريني' }).click();
  await page.getByText(/حسب النص، اللي كيشد 15.000 كيربح 500 درهم/).waitFor();
  const read = page.locator('.st-read').first();
  await read.getByText(/أجر خام ديال 10.000 درهم/).waitFor();
  await page.getByRole('slider', { name: 'أجرتك على المنحنى' }).focus();
  await page.keyboard.press('Shift+ArrowRight'); // the curve reads left to right in Arabic too (the chart rule of 1 Nov 2026)
  await read.getByText(/أجر خام ديال 11.000 درهم/).waitFor();
  await page.getByRole('button', { name: 'الأرقام كجدول' }).click();
  await page.locator('.st-table').waitFor();
  // The reader answered «متقاعد» on the topic's page: their section opens; «أجير» opens the salaried one.
  await page.getByRole('heading', { name: /إلا كنتي متقاعد/, level: 2 }).waitFor();
  await page.getByText('معلن، ماشي فالمشروع').first().waitFor();
  await page.getByRole('button', { name: 'أجير', exact: true }).click();
  await page.getByRole('heading', { name: /إلا كنتي أجير/, level: 2 }).waitFor();
  // The ledger (15 Nov 2026): the section's first line large, today's figure and the bill's in their two columns.
  await page.locator('.lg-row.hero .lg-today').getByText('40.000').waitFor();
  await page.locator('.lg-row.hero .lg-bill').getByText('60.000').waitFor();
  // The Chamber's vote as a door of 395 seats with its score, and «مشروع» across the sheet.
  await page.getByRole('img', { name: /179 صوت مع المشروع و126 ضد/ }).waitFor();
  assert.equal(await page.locator('.vt-seat').count(), 395, 'a dot for every seat');
  assert.equal(await page.locator('.vt-seat.f').count(), 179);
  assert.ok((await page.locator('.bl-wm span').count()) >= 3, 'the draft mark down the sheet');
  // A line the deputies changed: its change bar, the pen's note, the committee's voices as dots, the report's page.
  const pen = page.locator('.lg-row.pen').first();
  await pen.getByText('كما صوتو عليه النواب').waitFor();
  await pen.getByRole('link', { name: /تقرير اللجنة، ص\. 743/ }).waitFor();
  assert.equal(await page.getByRole('button', { name: /صورة للمشاركة/ }).count() >= 5, true, 'a picture for every change');
  await page.getByRole('button', { name: /^إلا كنتي متقاعد/ }).waitFor();
  await shot(page, '08-bill-page');
  // The page of amendments: one dot for each of the 287 filed, the figure as filed struck above the voted one, and
  // what the committee refused drawn as proposals.
  await page.goto(`${base}/topics/tax/pages/bill-amendments`);
  await page.getByRole('heading', { name: /59\s+تعديل قبلتهم لجنة المالية من 287 تقدمو/ }).waitFor();
  assert.equal(await page.locator('.am-groups .dv i').count(), 287, 'a dot for every amendment filed');
  assert.equal(await page.locator('.am-groups .dv i.f').count(), 59);
  assert.ok((await page.locator('.lg-filed s').count()) >= 2, 'a filed figure struck through');
  await page.getByRole('button', { name: 'ما تقبلش', exact: true }).click();
  await page.getByRole('heading', { name: /شنو ما قبلاتش اللجنة/, level: 2 }).waitFor();
  assert.equal(await page.locator('.lg-row.no').count(), 14);
  assert.equal(await page.locator('.lg-row.pen').count(), 0, 'no change bar beside a proposal');
  await page.goto(`${base}/topics/tax/pages/bill-claims`);
  await page.locator('.cl-row').first().waitFor();
  assert.ok((await page.locator('.cl-row').count()) >= 8, 'every claim beside the text');
  await page.getByText('بشرط').first().waitFor();
  await page.getByText('عاودوها:').first().waitFor();
  await page.goto(`${base}/topics/tax/pages/bill-press`);
  await page.getByRole('heading', { name: 'النقابات' }).waitFor();
  await page.getByText('اقتراح، ماشي فالمشروع').first().waitFor();
  await page.goto(`${base}/topics/tax/tools/bill?g=10000&k=0`);
  await page.getByText(/442[,.]71/).first().waitFor();
  for (const year of ['2027', '2028', '2029', '2030', '2031']) await page.getByRole('button', { name: new RegExp(`^${year}`) }).first().waitFor();
  await shot(page, '09-bill-tool');
  // Arabic's plural forms (two dependents is `_two`): no word left as its key.
  await page.goto(`${base}/topics/tax/tools/bill?g=15000&k=2`);
  await page.getByText(/مع جوج فتكلفك/).first().waitFor();
  assert.equal(await page.getByText(/\bbill\.\w+/).count(), 0, 'no raw key');
  await page.goto(`${base}/ma/projet-loi/60-26`);
  await page.getByText('ليس قانونا بعد').first().waitFor();
  await page.goto(`${base}/ma/code/cgi/art_73`);
  await page.locator('#art_73').getByRole('button', { name: /عرض التغيير المقترح/ }).click();
  await page.getByRole('heading', { name: 'ما يقترحه مشروع قانون المالية 2027' }).waitFor();
  await shot(page, '10-proposed');

  // A desk: the instruments in the side column.
  const desk = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const d = await desk.newPage();
  watch(d);
  await d.goto(`${base}/topics/tax`);
  await d.getByRole('heading', { name: 'الآجال ديالك' }).waitFor();
  await shot(d, '07-desk');
  // Four people (Y3) before the guess is answered: a tap draws the curve in its place, takes the reader to it with that
  // person's salary, and marks the card (26 Oct 2026: a tap on a card used to do nothing).
  await d.goto(`${base}/topics/tax/pages/bill-2027`);
  await d.getByRole('button', { name: 'وريني' }).waitFor();
  await d.getByRole('button', { name: 'شوف مهندسة على المنحنى' }).click();
  await d.locator('#st-curve .st-read').getByText(/أجر خام ديال 25.000 درهم/).waitFor();
  assert.equal(await d.getByRole('button', { name: 'وريني' }).count(), 0, 'the guess gives way to the curve');
  await d.getByRole('button', { name: 'شوف مهندسة على المنحنى', pressed: true }).waitFor();
  await d.waitForFunction(() => { const r = document.getElementById('st-curve')?.getBoundingClientRect(); return r && r.top >= 0 && r.top < innerHeight; }, null, { timeout: 5000 });

  assert.deepEqual(errors, []);
  console.log('tax e2e: ok');
} finally {
  await browser.close();
}
