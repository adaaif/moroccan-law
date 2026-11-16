// The consumer topic end to end (the consumer plan, 24 Oct 2026), on a phone and a desk. Needs a backend in
// development (DEBUG: drafts and unchecked tools show) behind the web dev server: BASE_URL (default
// http://localhost:5201, the consumer pair: WEB_PORT=5201 API_TARGET=http://localhost:8031). SHOTS=<dir> saves a
// screenshot of each step.
import assert from 'node:assert/strict';
import { chromium } from 'playwright';
const CHANNEL = process.env.CHANNEL; // e.g. CHANNEL=chrome where the bundled browser is not installed

const base = process.env.BASE_URL ?? 'http://localhost:5201';
const shots = process.env.SHOTS;
const shot = async (page, name) => {
  // The phone's bottom bar is fixed: a full-page picture would draw it across the middle of the page.
  if (shots) await page.screenshot({ path: `${shots}/${name}.png`, fullPage: true, style: 'nav.fixed.bottom-0 { display: none !important; }' });
};
const ago = (n) => new Date(Date.now() - n * 864e5).toISOString().slice(0, 10);

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

  // The page asks how one bought (D1), its doors in people's words (D2), the beliefs (D3).
  await page.goto(`${base}/topics/consumer`);
  await page.getByRole('button', { name: 'كيفاش شريتي؟' }).waitFor();
  await page.getByRole('heading', { name: 'شنو وقع ليك؟' }).waitFor();
  await page.getByText('«لا ترد ولا تستبدل»').first().waitFor();
  await shot(page, '01-hub');
  // The consumer-receipt review: the doors in the life of a purchase, none folded, each led by its price tag.
  for (const stage of ['قبل ما تشري', 'فاش كتخلص', 'من بعد ما شريتي', 'إلا ما تحلاتش', 'فمواضيع أخرى']) {
    await page.getByRole('heading', { name: stage, level: 3 }).waitFor();
  }
  assert.equal(await page.getByRole('button', { name: /حالة أخرى|حالات أخرى/ }).count(), 0, 'no door is folded');
  assert.ok((await page.getByRole('link', { name: /طلبت أونلاين/ }).innerText()).includes('7'), 'the online door carries its 7 days');
  await page.getByRole('button', { name: 'كيفاش شريتي؟' }).click();
  await page.getByRole('radio', { name: 'أونلاين ولا فالأنستغرام' }).click();
  await page.getByText('للتراجع من تسلم السلعة، بلا تبرير', { exact: false }).first().waitFor();    // the answer's figures
  // The answer's stage comes first, its own door first in it.
  const firstStage = page.locator('section[aria-labelledby=doors] h3').first();
  assert.equal((await firstStage.innerText()).trim(), 'من بعد ما شريتي', 'an online buyer meets the after-purchase stage first');
  const firstDoor = page.locator('section[aria-labelledby=doors] section ul > li').first();
  assert.ok((await firstDoor.innerText()).includes('طلبت أونلاين'), 'an online buyer meets the online door first');
  await shot(page, '02-profile-online');
  await page.getByRole('button', { name: /أنا: / }).click();
  await page.getByRole('button', { name: 'بلا جواب' }).click();

  // «فاتورة حقوقي»: an online purchase received two days ago, 4,200 DH → its rights as a receipt, kept on the phone,
  // then its soonest day on the page's instrument.
  await page.goto(`${base}/topics/consumer/tools/receipt?c=online&p=4200&d=${ago(2)}&i=${encodeURIComponent('تلفون')}`);
  await page.getByRole('heading', { name: 'فاتورة حقوقك' }).waitFor();
  for (const line of ['حق التراجع', 'إذا تراجعت', 'الضمان القانوني', 'أجل التسليم مكتوب', 'الفاتورة']) await page.getByText(line, { exact: true }).first().waitFor();
  await page.getByText('باقي 5 أيام.').first().waitFor();
  await page.getByText('لا ترد ولا تستبدل').first().waitFor();
  await page.getByRole('button', { name: 'حفظ فمشترياتي' }).click();
  await page.getByRole('heading', { name: 'مشترياتي' }).waitFor();
  await shot(page, '02b-receipt');
  await page.goto(`${base}/topics/consumer`);
  await page.getByText(/باقي 5 أيام.*تلفون/).first().waitFor();

  // T1: received three days ago online → the last day four days from now; without confirmation, thirty days.
  await page.goto(`${base}/topics/consumer/tools/return?c=online&d=${ago(3)}`);
  await page.getByText('آخر يوم للتراجع').waitFor();
  await page.getByText('باقي 4 أيام.').waitFor();
  await shot(page, '03-return');
  await page.getByRole('radio', { name: 'لا', exact: true }).click();
  await page.getByText('باقي 27 يوما.').waitFor();
  await page.getByRole('radio', { name: 'فحانوت' }).click();
  await page.getByText('في المحل لا يوجد حق التراجع').first().waitFor();     // the card, and its folded line (A14)

  // T2: delivered a year and ten days ago, a 24-month card and 21 days in repair → the legal one passed, the shop's runs.
  await page.goto(`${base}/topics/consumer/tools/guarantee?d=${ago(375)}&m=24&r=21`);
  await page.getByText('مضت السنة', { exact: false }).waitFor();
  await page.getByText('ضمان المحل إلى', { exact: false }).first().waitFor();
  await shot(page, '04-guarantee');

  // T3: a date written twelve days ago → the five days are now.
  await page.goto(`${base}/topics/consumer/tools/late?p=${ago(9)}`);
  await page.getByText('الفسخ دون محكمة ممكن الآن', { exact: false }).waitFor();
  await shot(page, '05-late');

  // T4: a consumer credit in default, 20,000 left and 3,000 unpaid → 800 and 120 at most.
  await page.goto(`${base}/topics/consumer/tools/credit?q=default&k=20000&u=3000`);
  await page.getByText('800').first().waitFor();
  await page.getByText('120', { exact: false }).first().waitFor();
  await shot(page, '06-credit');

  // T5, T6, T7, T8.
  await page.goto(`${base}/topics/consumer/tools/where?s=bank`);
  await page.getByRole('heading', { name: 'المركز المغربي للوساطة البنكية' }).waitFor();
  await shot(page, '07-where');
  await page.goto(`${base}/topics/consumer/tools/clause`);
  await page.getByRole('searchbox').fill('يمكن للشركة فسخ العقد في أي وقت');
  await page.getByText('قد يشبهه', { exact: false }).waitFor();
  await shot(page, '08-clause');
  await page.goto(`${base}/topics/consumer/tools/prices?p=g1`);
  await page.getByText('القرار 2889.25', { exact: false }).first().waitFor();
  await shot(page, '09-prices');
  await page.goto(`${base}/topics/consumer/tools/letters?l=late`);
  await page.getByText('فسخ الالتزام بسبب تجاوز أجل التسليم', { exact: false }).waitFor();
  await shot(page, '10-letters');

  // A journey: the day asked once, the last day as a date.
  await page.goto(`${base}/topics/consumer/journeys/online?d=${ago(2)}`);
  await page.getByText('آخر أجل:', { exact: false }).first().waitFor();
  await shot(page, '11-online-journey');
  await page.goto(`${base}/topics/consumer/pages/beliefs`);
  await page.getByText('ما يقال، وما يقوله القانون').first().waitFor();
  await page.goto(`${base}/topics/consumer/checklists/invoice`);
  await page.getByText('كيفيات الأداء').first().waitFor();

  // Search answers a consumer question itself (S2).
  await page.goto(`${base}/search?q=${encodeURIComponent('شحال من يوم نرجع اللي شريت أونلاين')}`);
  await page.getByText('سبعة أيام كاملة').first().waitFor();
  await shot(page, '12-search');

  // A desk: the hub and the changes.
  const desk = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const d = await desk.newPage();
  watch(d);
  await d.goto(`${base}/topics/consumer`);
  await d.getByRole('heading', { name: 'شنو وقع ليك؟' }).waitFor();
  await shot(d, '13-hub-desk');
  await d.goto(`${base}/topics/consumer/changes`);
  await d.getByText('القانون 78.20', { exact: false }).first().waitFor();

  assert.deepEqual(errors, [], 'no errors in the page');
  console.log('consumer: ok');
} finally {
  await browser.close();
}
