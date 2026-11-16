// The housing topic end to end (H6–H17 of the housing plan), on a phone and a desk. Needs a backend in development
// (DEBUG: drafts and unchecked tools show) behind the web dev server: BASE_URL (default http://localhost:5196, the
// housing pair: WEB_PORT=5196 API_TARGET=http://localhost:8026). SHOTS=<dir> saves a screenshot of each step.
import assert from 'node:assert/strict';
import { chromium } from 'playwright';
const CHANNEL = process.env.CHANNEL; // e.g. CHANNEL=chrome where the bundled browser is not installed

const base = process.env.BASE_URL ?? 'http://localhost:5196';
const shots = process.env.SHOTS;
const shot = async (page, name) => {
  if (shots) await page.screenshot({ path: `${shots}/${name}.png`, fullPage: true });
};

const browser = await chromium.launch(CHANNEL ? { channel: CHANNEL } : {});
const errors = [];
const watch = (page) => {
  page.on('pageerror', (e) => errors.push(String(e)));
  page.on('console', (m) => m.type() === 'error' && !/favicon|404/.test(m.text()) && errors.push(m.text()));
};

try {
  const phone = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
  const page = await phone.newPage();
  watch(page);

  // The hub: where you stand first; a shopkeeper's law is 49.16, and the tenant's doors fade with the reason.
  await page.goto(`${base}/topics/housing`);
  await page.getByRole('link', { name: /مول الدار بغا يخرجني/ }).waitFor();
  await shot(page, '01-hub');
  await page.getByRole('button', { name: /شنو وضعك|فين ساكن|شكون نتا/ }).first().click();
  await page.getByRole('radio', { name: /حانوت أو محل تجاري/ }).click();
  await page.getByText('قانونك هو القانون 49.16', { exact: false }).waitFor();
  // The answer orders the doors (T2 of the road tools review): what is not yours goes after, behind «كل الحالات».
  if (await page.getByRole('button', { name: /أخرى|أخريان/ }).count()) await page.getByRole('button', { name: /أخرى|أخريان/ }).click();
  const deposit = page.getByRole('link', { name: /بغيت الضمانة ديالي/ });
  assert.ok((await deposit.innerText()).includes('لا يخصك حسب جوابك'), 'the deposit door fades for a shop');
  await shot(page, '02-profile-shop');
  await page.getByRole('button', { name: /أنا: / }).click();
  await page.getByRole('button', { name: 'بلا جواب' }).click();          // no answer

  // A journey: the notice to leave on its articles, the two months.
  await page.getByRole('link', { name: /مول الدار بغا يخرجني/ }).click();
  await page.waitForURL('**/topics/housing/journeys/eviction');
  await page.getByText('شهرين', { exact: false }).first().waitFor();
  await page.getByRole('button', { name: /المادة 46/ }).first().waitFor();    // the steps cite art. 46
  await shot(page, '03-eviction-journey');

  // The check: a notice read against art. 46; one condition unticked names its article.
  await page.goto(`${base}/topics/housing/checklists/eviction-notice`);
  const boxes = page.getByRole('checkbox');
  const n = await boxes.count();
  for (let i = 0; i < n - 2; i++) await boxes.nth(i).check();
  await page.getByText('الإشعار الذي ينقصه بيان من المادة 46 يكون باطلا', { exact: false }).waitFor();
  await shot(page, '04-notice-check');

  // «واش الزيادة قانونية؟»: open before a professional's review, its «كيفاش حسبنا؟» leading to /about#ab-tools.
  // 2,500 DH since 1 Sep 2023, 2,800 asked.
  await page.goto(`${base}/topics/housing/tools/rent`);
  await page.getByRole('link', { name: 'كيفاش حسبنا؟' }).waitFor();
  await page.getByLabel('الوجيبة المقترحة').fill('2800');
  await page.getByText('2.700 درهم').first().waitFor();
  await page.getByText('تفوق الحد الذي يضعه القانون', { exact: false }).waitFor();
  await page.getByRole('link', { name: /القانون 67.12، المادة 34/ }).first().waitFor();   // the cap cites art. 34
  await page.getByLabel('الضمانة التي أديتها').fill('7500');
  await page.getByText('الضمانة تفوق ما يسمح به القانون').waitFor();
  await shot(page, '05-rent');

  // «بغا يخرجني»: a notice of one month is short; a year of rent if a court validates it (art. 51).
  await page.goto(`${base}/topics/housing/tools/eviction`);
  await page.getByLabel('الأجل بالشهور').fill('1');
  await page.getByText('الأجل أقل من شهرين', { exact: false }).waitFor();
  await page.getByText('30.000 درهم').first().waitFor();
  await shot(page, '06-eviction-tool');

  // Off plan: what may be paid at the start of works, a late delivery's indemnity.
  await page.goto(`${base}/topics/housing/tools/offplan`);
  await page.getByText('20% على الأكثر', { exact: false }).first().waitFor();
  await page.getByLabel('أجل التسليم في العقد').fill('2026-01-31');
  await page.getByLabel('تاريخ إنذارك للبائع').fill('2026-03-10');
  await page.getByText('تجاوز البائع أجل التسليم (31 يناير 2026)', { exact: false }).waitFor();
  await page.getByText('120.000 درهم', { exact: false }).first().waitFor();     // 20% of 600,000 at the start of works
  await shot(page, '07-offplan');

  // The aid: 100,000 DH under 300,000.
  await page.goto(`${base}/topics/housing/tools/aid`);
  await page.getByText('100.000 درهم').first().waitFor();
  await page.getByLabel('ثمن السكن مع احتساب الرسوم').fill('750000');
  await page.getByText('شرط أو أكثر لم يتحقق', { exact: false }).waitFor();
  await shot(page, '08-aid');

  // What changed: in force and announced, never one for the other.
  await page.goto(`${base}/topics/housing/changes`);
  await page.getByText('نافذ الآن').first().waitFor();
  await page.getByText('المحرر الرسمي لبيوع العقار', { exact: false }).waitFor();
  await shot(page, '09-changes');

  // The DOC on the site: its off-plan article 618-6, Adala's consolidation.
  await page.goto(`${base}/ma/code/doc/art_618-6`);
  await page.getByText('عند إبرام عقد التخصيص', { exact: false }).first().waitFor();
  await shot(page, '10-doc-618-6');

  // Search: «السانديك» is the syndic as the law says it.
  await page.goto(`${base}/search?q=${encodeURIComponent('السانديك')}`);
  await page.getByText('«وكيل الاتحاد»', { exact: false }).first().waitFor();
  const first = page.locator('ol > li').first();
  assert.ok((await first.innerText()).includes('18.00'), 'the co-ownership law comes first');
  await shot(page, '11-search');

  // The numbers on a desk: the census chart and its table.
  const desk = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const d = await desk.newPage();
  watch(d);
  await d.goto(`${base}/topics/housing/pages/numbers`);
  await d.getByText('الأرقام في جدول').first().click();
  await d.getByRole('cell', { name: '61,5' }).first().waitFor();
  await shot(d, '12-numbers');

  assert.deepEqual(errors, [], 'no errors in the page');
  console.log('housing: ok');
} finally {
  await browser.close();
}
