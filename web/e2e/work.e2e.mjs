// The work topic end to end (T4–T17 of the work plan; the work-counted review), on a phone and a desk. Needs a backend in development
// (DEBUG: drafts and unchecked tools show) behind the web dev server: BASE_URL (default http://localhost:5195, the
// work pair: WEB_PORT=5195 API_TARGET=http://localhost:8025). SHOTS=<dir> saves a screenshot of each step.
import assert from 'node:assert/strict';
import { chromium } from 'playwright';
const CHANNEL = process.env.CHANNEL; // e.g. CHANNEL=chrome where the bundled browser is not installed

const base = process.env.BASE_URL ?? 'http://localhost:5195';
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

  // The hub (the work-counted review): the dismissal's first days in a band in ink, its three acts; the doors led by their
  // number on a punch card, in a working life's order, none folded; the three instruments.
  await page.goto(`${base}/topics/work`);
  await page.getByRole('heading', { name: 'طردوك؟' }).waitFor();
  assert.ok(await page.getByText('يسلم لك مقرر الفصل داخل 48 ساعة', { exact: false }).count() > 0, 'the band says the decision\'s 48 hours');
  await page.getByRole('link', { name: /بديت خدمة جديدة/ }).waitFor();
  assert.equal(await page.getByRole('button', { name: /أخرى|أخريان/ }).count(), 0, 'no door is folded');
  assert.ok((await page.getByRole('link', { name: /وصلت للتقاعد/ }).innerText()).includes('1320'), 'the retirement door carries its 1320 days');
  await page.getByRole('link', { name: /ورقة الأداء/ }).first().waitFor();                   // an instrument
  await shot(page, '01-hub');
  // One question (A4 of the road-signposted review): the domestic worker's own door comes first, the band folds to a line,
  // the minimum's card says 60 %.
  await page.getByRole('button', { name: 'فين خدام؟' }).click();
  await page.getByRole('radio', { name: /خدمة منزلية/ }).click();
  await page.getByText('من الحد الأدنى للأجر، نقدا', { exact: false }).waitFor();
  const firstDoor = page.locator('#doors').locator('xpath=../..').locator('a[href*="/topics/work/"]').first();   // past the figures' articles
  assert.ok((await firstDoor.innerText()).includes('خدامة فالدار'), 'the domestic worker\'s door leads');
  assert.equal(await page.getByRole('heading', { name: 'طردوك؟' }).count(), 0, 'the band is one line for domestic work');
  assert.ok((await page.getByRole('link', { name: /ما خلصونيش/ }).innerText()).includes('60%'), 'the minimum as a share at home');
  await page.reload();
  await page.getByRole('button', { name: /أنا: .*خدمة منزلية/ }).waitFor();     // the answer stays on the phone
  await shot(page, '02-profile-home');
  // The employer (E4): an answer with its own doors.
  await page.getByRole('button', { name: /أنا: / }).click();
  await page.getByRole('radio', { name: 'أنا اللي كنشغّل' }).click();
  await page.getByRole('link', { name: /غادي نشغّل شي واحد/ }).waitFor();
  await page.getByRole('button', { name: /أنا: / }).click();
  await page.getByRole('button', { name: 'بلا جواب' }).click();          // no answer

  // The journey from the band: each step answered first, the day asked once, the 90 days counted.
  await page.getByRole('link', { name: 'الخطوات كلها' }).first().click();
  await page.waitForURL('**/topics/work/journeys/dismissed');
  await page.getByText('ترفع الدعوى داخل 90 يوما', { exact: false }).first().waitFor();
  await page.getByRole('button', { name: 'أمس' }).first().click();
  await page.getByText(/باقي 89 يوما/).first().waitFor();
  assert.ok(await page.getByRole('button', { name: 'المادة 65' }).count() > 0, 'the steps cite art. 65');
  await page.getByText('مقرر الفصل، وشهادة الشغل', { exact: false }).first().waitFor();   // the papers at the end
  await shot(page, '03-dismissed');
  await page.goto(`${base}/topics/work`);
  await page.getByRole('link', { name: /باقي 89 يوما/ }).waitFor();                        // the band counts the days

  // «شنو كيتسالني؟»: open before a professional's review, its «كيفاش حسبنا؟» leading to /about#ab-tools; the total on
  // top. The plan's example: seven years at 4,000 DH, dismissed without notice or fault, ten days of leave not taken.
  await page.goto(`${base}/topics/work/tools/end`);
  await page.getByRole('link', { name: 'كيفاش حسبنا؟' }).waitFor();
  const years = page.getByRole('group', { name: 'سنوات' });
  await years.getByRole('button', { name: '+' }).click();
  await years.getByRole('button', { name: '+' }).click();
  const leave = page.getByRole('group', { name: /أيام العطلة السنوية/ });
  for (let i = 0; i < 10; i++) await leave.getByRole('button', { name: '+' }).click();
  for (const amount of ['8.000,00', '16.083,77', '1.538,46', '42.000,00']) await page.getByText(`${amount} درهم`).first().waitFor();
  await page.getByText('25.622,23 درهم').first().waitFor();                                 // the total, on top
  assert.ok(await page.getByRole('link', { name: /المادة 53/ }).count() > 0, 'the severance cites art. 53');
  await shot(page, '04-end');

  // The payslip the law writes (E14): the review's example, the net on top; a line opens its article.
  await page.goto(`${base}/topics/work/tools/pay?o=6`);
  await page.getByText('3.422,72', { exact: false }).first().waitFor();
  await page.getByText('4.037,42 درهم').first().waitFor();
  await page.getByRole('button', { name: /منحة الأقدمية 10%/ }).click();
  await page.getByText('علاوة الأقدمية', { exact: false }).first().waitFor();
  await shot(page, '05-pay');
  await page.keyboard.press('Escape');

  // The days (E15): 2,400 days at 4,000 DH, the pension on top; the page's instrument then shows the days.
  await page.goto(`${base}/topics/work/tools/cnss?j=2400`);
  await page.getByText('1.481,20 درهم').first().waitFor();
  await shot(page, '05b-cnss');
  await page.goto(`${base}/topics/work`);
  await page.getByText('2400 يوم فالضمان').first().waitFor();

  // The dates: 90 days from a dismissal letter (art. 65).
  await page.goto(`${base}/topics/work/tools/dates`);
  await page.getByRole('button', { name: 'يوم آخر' }).click();     // the day as chips since G13 of the family-papers review
  await page.locator('input[type=date]').fill('2026-10-20');
  await page.getByText('18 يناير 2027', { exact: false }).first().waitFor();
  await shot(page, '06-dates');

  // What changed: in force, coming, announced — never one for the other.
  await page.goto(`${base}/topics/work/changes`);
  await page.getByText('نافذ الآن').first().waitFor();
  await page.getByText('حراس شركات الحراسة: الساعات العادية', { exact: false }).first().waitFor();
  await shot(page, '07-changes');

  // Search: «السميك» is the minimum wage as the law says it, the decree in force first, with the work topic's words.
  await page.goto(`${base}/search?q=${encodeURIComponent('السميك')}`);
  await page.getByText('«الحد الأدنى القانوني للأجر»', { exact: false }).first().waitFor();
  const first = page.locator('ol > li').first();
  assert.ok((await first.innerText()).includes('2.25.983'), 'the decree in force comes first');
  await page.getByText('كلمات القانون في هذا الموضوع').waitFor();
  await shot(page, '08-search');

  // The numbers on a desk: the chart and its table.
  const desk = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const d = await desk.newPage();
  watch(d);
  await d.goto(`${base}/topics/work/pages/numbers`);
  await d.getByText('الأرقام في جدول').first().click();
  await d.getByRole('cell', { name: '17,92' }).first().waitFor();
  await shot(d, '09-numbers');

  assert.deepEqual(errors, [], 'no errors in the page');
  console.log('work: ok');
} finally {
  await browser.close();
}
