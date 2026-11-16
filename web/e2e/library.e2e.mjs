// The library and its rooms end to end (the every-code review, 9 Nov 2026; the library-search review, 10 Nov 2026), on a
// phone and a desk. Needs both dev
// servers: BASE_URL (default http://localhost:5190). SHOTS=<dir> saves a screenshot of each step.
import assert from 'node:assert/strict';
import { chromium } from 'playwright';
const CHANNEL = process.env.CHANNEL;

const base = process.env.BASE_URL ?? 'http://localhost:5190';
const shots = process.env.SHOTS;
const shot = async (page, name) => {
  if (shots) await page.screenshot({ path: `${shots}/${name}.png`, fullPage: true });
};

const browser = await chromium.launch(CHANNEL ? { channel: CHANNEL } : {});
const errors = [];
const watch = (page) => {
  page.on('pageerror', (e) => errors.push(String(e)));
  // The open data's manifest answers 403 while the downloads are closed (since 2 Nov 2026): the tools' line says «soon».
  page.on('console', (m) => m.type() === 'error' && !/favicon|404|403/.test(m.text()) && errors.push(m.text()));
};

try {
  const phone = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
  const page = await phone.newPage();
  watch(page);

  // The first screen (15 Nov 2026): the box, then the two rooms as tabs; the codes' room is the one a reader enters,
  // and the Bulletin's tab names its newest issue.
  await page.goto(`${base}/library`);
  await page.getByRole('heading', { name: 'المكتبة', level: 1 }).waitFor();
  await page.getByRole('tab', { name: /المدونات والقوانين/ }).waitFor();
  assert.equal(await page.getByRole('tab', { name: /المدونات والقوانين/ }).getAttribute('aria-selected'), 'true', 'the codes first');
  await page.getByRole('tab', { name: /الجريدة الرسمية/ }).getByText('آخر عدد', { exact: false }).waitFor();

  // The codes on nine shelves: each led by its general code as a bound book, every one of the 67 names in view on a
  // phone without a tap (W7).
  await page.locator('#branch-civil').waitFor();
  assert.equal(await page.locator('.lb-shelves .lb-shelf').count(), 9, 'nine shelves');
  assert.equal(await page.locator('.lb-shelves .lb-cover').count(), 9, 'a bound code on each');
  assert.equal(await page.locator('.lb-shelf a.lb-cover:visible, .lb-shelf li:not(.old) > a:visible').count(), 67, '67 names in view');
  await page.locator('#branch-civil').getByRole('link', { name: 'قانون الالتزامات والعقود' }).waitFor();
  await shot(page, '01-shelves');

  // «بالأرقام» puts each text's number and state back on its line; the line's facts open the book's card, with its
  // parts and the reference to cite.
  assert.equal(await page.locator('.lb-shelf li > button').count(), 0, 'no number until asked');
  await page.getByRole('button', { name: 'بالأرقام' }).click();
  await page.locator('#branch-business li > button').first().click();
  await page.getByRole('heading', { name: 'مدونة التجارة', level: 2 }).waitFor();
  await page.getByText('أجزاؤه').waitFor();
  await page.getByText('للإحالة عليه').waitFor();
  await shot(page, '02-card');
  await page.keyboard.press('Escape');

  // The box reads what people write, and answers under its field: an issue and its page, a reference whose date is
  // wrong, a law's number taken apart. The examples leave at the first letter (W2).
  const box = page.getByLabel('اكتب ما تعرفه عن النص أو العدد: اسما، رقما، تاريخا، أو إحالة منسوخة');
  await box.fill('5167 ص 3969');
  await page.getByText('الصفحة 3969: صفحته 3', { exact: false }).waitFor();
  assert.equal(await page.locator('.lb-eg').isVisible(), false, 'the examples leave once the reader types');
  await box.fill('الجريدة الرسمية عدد 5167 بتاريخ 9 دجنبر 2003، ص. 3969');
  await page.getByText('صدر هذا العدد يوم', { exact: false }).waitFor();
  await box.fill('65.99');
  await page.getByText('سنة المشروع، لا سنة الصدور', { exact: false }).waitFor();
  await page.locator('.lb-read .lb-line.sure').getByRole('link', { name: /مدونة الشغل/ }).waitFor();
  // What names a text is read on the server (W3–W6): a short form, an article, a dahir's day in either calendar, a law
  // outside the 67, a finance law's year; a number is never an issue.
  await box.fill('ق.م.م');
  await page.locator('.lb-read .lb-line.sure').getByRole('link', { name: /قانون المسطرة المدنية/ }).waitFor();
  await box.fill('ظهير 2 أكتوبر 1984');
  await page.locator('.lb-und').getByText('6 محرم 1405', { exact: false }).waitFor();
  await page.locator('.lb-read').getByRole('link', { name: /تعويض المصابين/ }).waitFor();
  await box.fill('ظهير 6 محرم 1405');
  await page.locator('.lb-read').getByRole('link', { name: /تعويض المصابين/ }).waitFor();
  await box.fill('43.20');
  await page.locator('.lb-read .lb-line.sure').getByRole('link', { name: /خدمات الثقة/ }).waitFor();
  await box.fill('loi n° 17-95');
  await page.locator('.lb-read .lb-line.sure').getByRole('link', { name: /شركات المساهمة/ }).waitFor();
  await box.fill('قانون المالية 2025');
  await page.locator('.lb-read .lb-line.sure a[href="/ma/loi/60-24"]').waitFor();
  await shot(page, '03-box');
  // A signing day with no text read: the issues that followed it are offered (W4). A Hijri day alone is a day like any
  // other. A French reference never opens the Arabic issue of its number (W10).
  await box.fill('ظهير 3 مارس 1915');
  await page.locator('.lb-read').getByText('أول عدد صدر بعد ذلك اليوم').first().waitFor();
  assert.equal(await page.locator('.lb-read .lb-line.sure').count(), 0, 'an issue that followed is offered, not opened');
  await box.fill('18 جمادى الأولى 1448');
  await page.locator('.lb-und').getByText('30 أكتوبر 2026', { exact: false }).waitFor();
  await box.fill('B.O. n° 5210 du 6 mai 2004, p. 667');
  await page.locator('.lb-read .note.warn').first().waitFor();
  assert.equal(await page.locator('.lb-read .lb-line.sure').count(), 0, 'a French reference opens no Arabic issue');
  // «فتح» never opens a guess (W1): two readings, neither sure, and the page stays.
  await box.fill('قانون المحاكم الإدارية');
  await page.locator('.lb-read a[href="/ma/loi/41-90"]').waitFor();
  assert.equal(await page.locator('.lb-read .lb-line.sure').count(), 0, 'no reading is sure');
  await box.press('Enter');
  await page.getByText('لم نتأكد أيها تقصد', { exact: false }).waitFor();
  assert.ok(page.url().endsWith('/library'), 'the page stayed');
  // An article citation opens the article (W5), even when Enter comes before the server's answer.
  await box.fill('المادة 16 من مدونة الأسرة');
  await box.press('Enter');
  await page.waitForURL('**/ma/loi/70-03/art_16');
  // An issue's number opens it on Enter; its neighbours come from the map. A year is the year first.
  await page.goto(`${base}/library`);
  await box.fill('7551');
  await box.press('Enter');
  await page.waitForURL('**/bo/general_ar/7551');
  await page.getByRole('heading', { name: 'العدد 7551', level: 1 }).waitFor();
  await page.getByRole('link', { name: /العدد السابق/ }).waitFor();
  // «آخر عدد» asks for one issue, the newest held: Enter opens it.
  await page.goto(`${base}/library`);
  await box.fill('آخر عدد');
  await page.locator('.lb-read .lb-line.sure').first().waitFor();
  await box.press('Enter');
  await page.waitForURL('**/bo/general_ar/**');
  await page.goto(`${base}/library`);
  await box.fill('1958');
  await box.press('Enter');
  await page.waitForURL('**/bo?year=1958');
  // A year holds its laws and dahirs, not only its issues (W8).
  await page.getByRole('tab', { name: 'قوانينها وظهائرها' }).click();
  await page.waitForURL('**/bo?year=1958&view=texts');
  await page.getByText('ما يُحال عليه أكثر من نصوص 1958').waitFor();
  assert.ok(await page.locator('.lb-yt').count() >= 40, 'the year lists its texts');
  await page.getByLabel('كلمة من العنوان أو رقم').fill('1.58.376');
  await page.locator('.lb-yt[href="/ma/dahir/1-58-376"]').waitFor();
  await shot(page, '03-year-texts');

  // The Bulletin's room, by its tab: the two newest issues as they are beside the week (W9), then the strata: a
  // decade's row opens its years; a year opens /bo on its months, one row of issues a month. The room is in the address.
  await page.goto(`${base}/library`);
  await page.getByRole('tab', { name: /الجريدة الرسمية/ }).click();
  await page.waitForURL('**/library#bo');
  await page.locator('.lb-new > a').first().waitFor();
  assert.equal(await page.locator('.lb-new > a').count(), 2, 'the two newest issues');
  assert.equal(await page.locator('#lb-room-codes').isVisible(), false, 'one room at a time');
  await page.locator('.lb-decrow').nth(1).click();
  await page.locator('.lb-yrow', { hasText: '2016' }).click();
  await page.waitForURL('**/bo?year=2016');
  await page.getByRole('heading', { name: '2016', level: 2 }).waitFor();
  assert.ok(await page.locator('.lb-months2 .lb-chip').count() > 100, 'a year on a phone is its issues by month');
  assert.equal(await page.locator('.lb-yearsec > .lb-months').isVisible(), false, 'the calendars are a desk\'s');
  await shot(page, '04-year');

  // A page opened from the bottom of another starts at its top (the bug of 26 Oct 2026).
  await page.goto(`${base}/library`);
  await page.locator('#branch-civil').waitFor();
  await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
  await page.waitForTimeout(300);
  assert.ok(await page.evaluate(() => window.scrollY) > 500, 'the library scrolled down');
  await page.locator('footer').getByRole('link', { name: 'كلمات القانون' }).click();
  await page.waitForURL('**/words');
  await page.getByRole('heading', { name: 'كلمات القانون', level: 1 }).waitFor();
  assert.equal(await page.evaluate(() => window.scrollY), 0, 'the words open at their top');

  // On a desk: the nine shelves three to a row, the box lights a book where it stands; in the Bulletin's room (opened by
  // its address) every year is a link, and a year opens /bo on its calendars.
  const desk = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const d = await desk.newPage();
  watch(d);
  await d.goto(`${base}/library`);
  await d.locator('#branch-civil').waitFor();
  assert.equal(await d.locator('.lb-shelf a.lb-cover:visible, .lb-shelf li:not(.old) > a:visible').count(), 67, '67 names');
  const tops = await d.locator('.lb-shelf').evaluateAll((els) => els.slice(0, 3).map((e) => Math.round(e.getBoundingClientRect().top)));
  assert.ok(tops[0] === tops[1] && tops[1] === tops[2], 'three shelves to a row');
  await d.getByLabel('اكتب ما تعرفه عن النص أو العدد: اسما، رقما، تاريخا، أو إحالة منسوخة').fill('الكراء');
  await d.locator('.lb-shelf li.hit, .lb-shelf .lb-cover.hit').first().waitFor();
  await shot(d, '05-desk');
  await d.goto(`${base}/library#bo`);
  assert.equal(await d.getByRole('tab', { name: /الجريدة الرسمية/ }).getAttribute('aria-selected'), 'true', 'the address opens the room');
  await d.locator('.lb-sgrid a.lb-yr').first().waitFor();
  assert.ok(await d.locator('.lb-sgrid a.lb-yr').count() >= 110, 'every year a link');
  await d.locator('.lb-sgrid a.lb-yr', { hasText: '1956' }).click();
  await d.waitForURL('**/bo?year=1956');
  await d.getByRole('heading', { name: '1956', level: 2 }).waitFor();
  assert.ok(await d.locator('.lb-yearsec > .lb-months .lb-month').count() >= 10, 'a year on a desk is its calendars');
  await shot(d, '06-bo');
  await d.goto(`${base}/codes`);
  await d.locator('#branch-civil').waitFor();
  assert.equal(await d.locator('.lb-shelves .lb-shelf').count(), 9, '/codes holds the nine shelves');
  await d.goto(`${base}/words`);
  await d.locator('.lb-index').getByRole('link', { name: /السكن والكراء/ }).click();
  await d.getByRole('link', { name: /الوجيبة الكرائية/ }).first().waitFor();
  await d.goto(`${base}/check`);
  await d.getByRole('button', { name: 'جرّب بمثال' }).click();
  await d.getByRole('button', { name: 'تحقق', exact: true }).click();
  await d.locator('main section ol > li').first().waitFor();

  assert.deepEqual(errors, [], 'no errors in the page');
  console.log('library: ok');
} finally {
  await browser.close();
}
