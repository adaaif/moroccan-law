// The road topic end to end (R5–R17 of the road plan), on a phone and a desk. Needs a backend in development (DEBUG:
// drafts and unchecked tools show) behind the web dev server: BASE_URL (default http://localhost:5197, the road pair:
// WEB_PORT=5197 API_TARGET=http://localhost:8027). SHOTS=<dir> saves a screenshot of each step.
import assert from 'node:assert/strict';
import { chromium } from 'playwright';
const CHANNEL = process.env.CHANNEL; // e.g. CHANNEL=chrome where the bundled browser is not installed

const base = process.env.BASE_URL ?? 'http://localhost:5197';
const shots = process.env.SHOTS;
const shot = async (page, name) => {
  if (shots) await page.screenshot({ path: `${shots}/${name}.png`, fullPage: true });
};

const browser = await chromium.launch(CHANNEL ? { channel: CHANNEL } : {});
const errors = [];
const watch = (page) => {
  page.on('pageerror', (e) => errors.push(String(e)));
  // The desk's 401 for a reader who is not signed in is its answer, not an error.
  page.on('console', (m) => m.type() === 'error' && !/favicon|404|401/.test(m.text()) && errors.push(m.text()));
};

try {
  const phone = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
  const page = await phone.newPage();
  watch(page);

  // The road's page (the road-signposted review): the band with its first acts and its sourced number, one question, the
  // doors as rows led by their sign, the instruments, the learning road, the next date.
  await page.goto(`${base}/topics/road`);
  await page.getByRole('heading', { name: 'شنو وقع ليك؟' }).waitFor();
  await page.getByRole('heading', { name: 'درت أكسيدة؟' }).waitFor();
  await page.getByText('التوقف فورا دون إحداث خطر جديد', { exact: false }).waitFor();
  await page.getByRole('link', { name: /19/ }).first().waitFor();
  await page.getByRole('link', { name: /dgsn\.gov\.ma/ }).waitFor();
  await page.getByRole('link', { name: 'شحال غادي نخلص؟' }).first().waitFor();
  await page.getByText('جاي:', { exact: false }).waitFor();
  assert.equal(await page.locator('section[aria-labelledby=doors] > ul').getByText('درت أكسيدة', { exact: true }).count(), 0, 'the band is the accident\'s door');
  await shot(page, '01-hub');
  await page.getByRole('button', { name: 'شنو وضعك؟' }).click();
  await page.getByRole('radio', { name: 'موطور ولا تروتينيت' }).click();
  await page.getByText('واجب على الموطور والتروتينيت').waitFor();
  const firstDoor = page.locator('section[aria-labelledby=doors] > ul > li').first();
  assert.ok((await firstDoor.innerText()).includes('الموطور والتروتينيت'), 'a rider meets the riders door first');
  await shot(page, '02-profile-rider');
  await page.getByRole('button', { name: /أنا: موطور ولا تروتينيت/ }).click();
  await page.getByRole('button', { name: 'بلا جواب' }).click();
  await page.getByRole('button', { name: 'شنو وضعك؟' }).waitFor();

  // The emergency (U1): the accident's steps in order, ticked one by one; the number with its source.
  await page.getByRole('link', { name: 'الخطوات كلها' }).click();
  await page.waitForURL('**/topics/road/tools/now');
  await page.getByRole('button', { name: 'نسخ الرقم' }).waitFor();
  const stop = page.getByRole('button', { name: /الوقوف/ });
  await stop.click();
  assert.equal(await stop.getAttribute('aria-pressed'), 'true');
  await shot(page, '03-now');

  // A journey (J1–J4): its day asked once, the limits as dates, the prices in place, a step ticked.
  await page.goto(`${base}/topics/road/journeys/radar?d=2026-10-20`);
  await page.getByText('آخر أجل:', { exact: false }).first().waitFor();
  await page.getByText('الدرجة الأولى').first().waitFor();
  await page.getByRole('button', { name: 'علّم الخطوة 1 كمنجزة' }).click();
  await page.getByText('أنجزت 1 من 7 خطوات').waitFor();
  // A step's article opens over the journey (A16).
  await page.getByRole('button', { name: 'المادة 197' }).first().click();
  await page.getByRole('dialog').getByText('المادة 197', { exact: false }).first().waitFor();
  await shot(page, '04-radar-journey');
  await page.keyboard.press('Escape');
  await page.getByRole('dialog').waitFor({ state: 'detached' });
  await page.waitForTimeout(300);     // the sheet closes through the history: let it settle before going on

  // The points page: art. 99's table, its rows in figures.
  await page.goto(`${base}/topics/road/pages/points`);
  await page.getByRole('cell', { name: 'الهاتف ممسوكا باليد أثناء السياقة' }).waitFor();

  // «شحال غادي نخلص؟» (A1–A4): a red light seen by an officer today costs 400; the staircase; the radar's 24 hours.
  await page.goto(`${base}/topics/road/tools/fine?o=redLight&s=officer`);
  await page.getByRole('link', { name: 'كيفاش حسبنا؟' }).waitFor();          // the tool's one way to /about#ab-tools
  await page.getByText('400 درهم').first().waitFor();
  await page.getByText('1.400 درهم', { exact: false }).first().waitFor();       // the deposit to contest
  await page.getByRole('radio', { name: 'إشعار الرادار' }).click();
  await page.getByText('24 ساعة').first().waitFor();
  await shot(page, '05-fine');
  // Scrolled, the answer folds to one line held at the top (A14).
  await page.evaluate(() => window.scrollTo(0, 900));
  await page.locator('button.fixed').filter({ hasText: 'درهم' }).waitFor();

  // «شحال كنتي كتسوق؟» (A2): 96 on a 60 sign, less the radar's 6, is +30: the first class.
  await page.goto(`${base}/topics/road/tools/speed?l=60&v=96`);
  await page.getByText('مخالفة من الدرجة الأولى', { exact: false }).waitFor();
  await shot(page, '06-speed');

  // The points as a licence (P1–P4): four offences at one stop, art. 100 stops at 8.
  await page.goto(`${base}/topics/road/tools/points?o=speed30,redLight,phone,overtaking`);
  await page.getByText('يتوقف الخصم عند 8 نقط', { exact: false }).waitFor();
  await page.getByText('22 من 30').waitFor();
  await shot(page, '07-points-tool');

  // The compensation tool, kept back: 30,000 a year at 35, a 10% rate.
  await page.goto(`${base}/topics/road/tools/compensation?a=35&e=30000&r=10&d=2026-03-01`);
  await page.getByText('ينتظر هذا الحساب مراجعة محام', { exact: false }).waitFor();
  await page.getByText('أين أنت في الجدول').waitFor();
  await shot(page, '08-compensation');

  // A scene asks first (S1): a wrong answer shows what would happen, then the right way.
  await page.goto(`${base}/topics/road/tools/scenes?s=stop`);
  await page.getByText('علامة «قف» والطريق تبدو خالية', { exact: false }).first().waitFor();
  await page.getByRole('button', { name: 'أمر ببطء' }).click();
  await page.getByText('ليس هذا', { exact: false }).waitFor();
  await page.getByRole('button', { name: 'شاهد الطريقة الصحيحة' }).click();
  await page.getByText('كم تكلف هذه المخالفة؟').waitFor();
  await shot(page, '09-scene-stop');

  // The signs sort themselves into families (G1); a sign opens big (G2).
  await page.goto(`${base}/topics/road/tools/signs`);
  await page.getByRole('heading', { name: 'المنع' }).waitFor();
  await page.getByRole('button', { name: 'قف' }).first().click();
  await page.getByText('اللوحة 201 في القرار المشترك 2805.14').waitFor();
  await shot(page, '10-signs');

  // Practice (Q2, Q3): a sign, three answers, the next card.
  await page.goto(`${base}/topics/road/tools/practice`);
  await page.getByRole('heading', { name: 'ماذا تفرض هذه العلامة؟' }).waitFor();
  await page.locator('section ul button').first().click();
  await page.getByRole('button', { name: 'التالية' }).click();

  // The pedestrians' page and the papers (V2, U2).
  await page.goto(`${base}/topics/road/pages/walking`);
  await page.getByText('على أقل من 50 مترا', { exact: false }).first().waitFor();
  await page.goto(`${base}/topics/road/checklists/carry`);
  await page.getByText('شهادة التأمين').first().waitFor();

  // What changed: five texts, each by the day it applies.
  await page.goto(`${base}/topics/road/changes`);
  await page.getByText('التروتينيت والخوذة والمثلث', { exact: false }).first().waitFor();

  // Search answers with the road's own answers (X1, X2).
  await page.goto(`${base}/search?q=${encodeURIComponent('شحال المخالفة ديال التيليفون')}`);
  await page.getByText('300 درهم').first().waitFor();
  await page.getByRole('link', { name: /الحساب حسب يومك/ }).waitFor();
  await shot(page, '11-search-phone');
  await page.goto(`${base}/search?q=${encodeURIComponent('شدني الرادار')}`);
  await page.getByRole('link', { name: /جاتني ورقة الرادار/ }).first().waitFor();

  // The numbers on a desk (N1): the year told first, then the series and its table.
  const desk = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const d = await desk.newPage();
  watch(d);
  // The road's page on a desk (A2, A12 of the road-signposted review): no sideways scroll, the instruments in the
  // side column.
  await d.goto(`${base}/topics/road`);
  await d.locator('aside').getByRole('link', { name: 'شحال كنتي كتسوق؟' }).waitFor();
  assert.ok(await d.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), 'nothing scrolls sideways');
  await shot(d, '12-hub-desk');
  await d.goto(`${base}/topics/road/pages/numbers`);
  await d.getByRole('heading', { name: 'من مات في الطريق سنة 2025' }).waitFor();
  await d.getByText('الأرقام في جدول').first().click();
  await d.getByRole('cell', { name: '4786' }).or(d.getByRole('cell', { name: '4.786' })).first().waitFor();
  await shot(d, '13-numbers');
  // The reviewer's desk asks for a staff account.
  await d.goto(`${base}/topics/road/review`);
  await d.getByText('هذا المكتب للمراجعين', { exact: false }).waitFor();

  assert.deepEqual(errors, [], 'no errors in the page');
  console.log('road: ok');
} finally {
  await browser.close();
}
