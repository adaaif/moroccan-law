// Search and reading, end to end in a real browser, on a desk and on a phone.
// Needs a backend with the search index (Postgres + ParadeDB) behind the web dev server: BASE_URL (default
// http://localhost:5191, the second pair: WEB_PORT=5191 API_TARGET=http://localhost:8021).
// SHOTS=<dir> saves a screenshot of each step.
import assert from 'node:assert/strict';
import { chromium } from 'playwright';
const CHANNEL = process.env.CHANNEL; // e.g. CHANNEL=chrome where the bundled browser is not installed

const base = process.env.BASE_URL ?? 'http://localhost:5191';
const shots = process.env.SHOTS;
const shot = async (page, name, fullPage = false) => {
  if (shots) await page.screenshot({ path: `${shots}/${name}.png`, fullPage });
};

const browser = await chromium.launch(CHANNEL ? { channel: CHANNEL } : {});
const errors = [];
const watch = (page) => {
  page.on('pageerror', (e) => errors.push(String(e)));
  page.on('console', (m) => m.type() === 'error' && !/favicon|404/.test(m.text()) && errors.push(m.text()));
};

try {
  const desk = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const phone = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, deviceScaleFactor: 2 });

  // ── search ──────────────────────────────────────────────────────────────────
  let page = await desk.newPage();
  watch(page);
  await page.goto(`${base}/`);
  const box = page.getByRole('combobox');
  await box.fill('قانون المالية');
  await page.getByRole('listbox').waitFor();
  // The topic the words name comes first, then the laws by name, one line each (P8 of the polish review).
  await page.getByRole('option').first().getByText('الضرائب').waitFor();
  await shot(page, '01-home-suggestions');
  await box.press('ArrowDown');
  await box.press('ArrowDown');
  await box.press('Enter');
  await page.waitForURL('**/ma/**');

  await page.goto(`${base}/search?q=${encodeURIComponent('الصفقات العمومية')}`);
  await page.locator('main ol > li').first().waitFor();
  assert.ok(await page.locator('main ol mark').count() > 0, 'matched words are marked');
  await shot(page, '02-search-words', true);

  await page.goto(`${base}/search?q=${encodeURIComponent('2.26.453')}`);
  await page.getByRole('link', { name: 'فتح النص' }).waitFor();
  await shot(page, '03-search-citation');

  await page.goto(`${base}/search?q=hgqvdfm`);
  await page.getByText('كُتب البحث بلوحة مفاتيح غير عربية').waitFor();
  await shot(page, '04-search-keyboard-repaired');

  await page.goto(`${base}/search?q=${encodeURIComponent('المسطرة الجنائية 53')}`);
  await page.getByText('ليس في «قانون» بعد').first().waitFor();
  await shot(page, '05-search-code-not-loaded');

  // «عقد الكراء» is the home's lease: law 67.12 (read from Adala), opened in one tap.
  await page.goto(`${base}/search?q=${encodeURIComponent('عقد الكراء')}`);
  await page.getByText('قانون كراء المحلات المعدة للسكنى').first().waitFor();
  await page.getByRole('link', { name: 'فتح النص' }).waitFor();

  // ── reading ─────────────────────────────────────────────────────────────────
  await page.goto(`${base}/ma/loi/50-25/art_6`);
  await page.locator('#art_6').waitFor();
  assert.ok(await page.locator('#art_6').evaluate((el) => el.getBoundingClientRect().top < 400), 'opens on the article');
  await shot(page, '06-text-opens-on-article');
  // A desk keeps the outline, the search in the text and the jump beside the law (P10–P12 of the polish review).
  const outline = page.getByRole('navigation', { name: 'الفهرس' });
  await outline.locator('[aria-current="location"]').waitFor();
  await shot(page, '07-outline');
  await page.getByPlaceholder('رقمها').fill('42');
  await page.getByRole('button', { name: 'انتقال', exact: true }).click();
  await page.waitForURL('**/art_42');
  await page.getByRole('searchbox', { name: 'بحث في هذا النص' }).fill('الضريبة');
  await page.getByText(/«الضريبة» في \d+ (مادة|مواد)/).waitFor();
  await page.getByRole('searchbox', { name: 'بحث في هذا النص' }).fill('');
  await page.getByRole('button', { name: 'إعدادات القراءة' }).click();
  await shot(page, '08-reading-settings');
  await page.getByRole('button', { name: 'ليل' }).click();
  assert.equal(await page.evaluate(() => document.documentElement.dataset.theme), 'dark');
  await page.keyboard.press('Escape');
  await shot(page, '09-night');
  await page.getByRole('button', { name: 'إعدادات القراءة' }).click();
  await page.getByRole('button', { name: 'نهار' }).click();
  await page.keyboard.press('Escape');

  // A link inside an article: a preview on the desk (article 19 of the 2026 finance law cites its article 21).
  await page.goto(`${base}/ma/loi/50-25/art_19`);
  const link = page.locator('#art_19 a[href$="/art_21"]').first();
  await link.scrollIntoViewIfNeeded();
  await link.hover();
  await page.getByRole('dialog', { name: 'معاينة' }).getByText('المادة 21').waitFor();
  await shot(page, '10-link-preview');

  // Defined terms (the press council law defines «الناشر»…).
  await page.goto(`${base}/ma/loi/9-26/art_2`);
  const term = page.locator('#art_2 div[lang] button[aria-expanded]').first();
  await term.waitFor();
  await term.click();
  await page.getByText('يعرّفه هذا النص:').waitFor();
  await shot(page, '11-defined-term');
  await page.keyboard.press('Escape');

  // Reporting an error: the words concerned, a note, sent to the review queue. The article the address opened on
  // has its tools out on a desk; the rest of them are behind «⋯».
  await page.locator('#art_2').getByRole('button', { name: 'إجراءات أخرى' }).click();
  await page.locator('#art_2').getByRole('button', { name: 'تبليغ عن خطأ' }).click();
  await page.getByRole('radio', { name: 'كلمة أو رقم خطأ' }).click();
  await page.getByLabel('الكلمات المعنية').fill('المجلس الوطني');
  await page.getByLabel('ما الصواب، أو ما الذي لاحظته').fill('اختبار آلي: تُحذف هذه الملاحظة.');
  await shot(page, '19-report-error');
  await page.getByLabel('خطأ في المادة').getByRole('button', { name: 'إرسال' }).click();
  await page.getByText('وصل التبليغ. يراجعه شخص قبل أي تصحيح.').waitFor();
  await page.keyboard.press('Escape');

  // Choosing articles, the export bar, the Word file: under «⋯» (P10).
  await page.getByRole('button', { name: 'أدوات أخرى' }).click();
  await page.getByRole('button', { name: 'اختيار مواد' }).click();
  for (const n of [1, 2]) await page.getByRole('checkbox').nth(n).check();
  await page.getByText('مادتان مختارتان').waitFor();
  await shot(page, '12-select-export');
  const download = page.waitForEvent('download');
  await page.getByRole('button', { name: 'ملف Word' }).click();
  assert.match((await download).suggestedFilename(), /\.docx$/);

  // A table with its total checked (the 2024 settlement law).
  await page.goto(`${base}/ma/loi/4-26/art_1`);
  await page.getByRole('button', { name: 'نسخ الجدول' }).first().waitFor();
  await page.locator('#art_1 figure').first().scrollIntoViewIfNeeded();
  await shot(page, '13-table');

  // The citation checker.
  await page.goto(`${base}/check`);
  await page.getByLabel('نص الوثيقة').fill(
    'طبقا للفصل 230 من ق.ل.ع، وللمادة 6 من القانون رقم 50.25 للسنة المالية 2026، وبالمرسوم رقم 2.26.453، كما نشر بالجريدة الرسمية عدد 7465 مكرر.');
  await page.getByLabel('تاريخ الوثيقة (اختياري)').fill('2025-01-01');
  await page.getByRole('button', { name: 'تحقق', exact: true }).click();
  await page.locator('main section ol > li').first().waitFor();
  await shot(page, '14-checker', true);

  // An issue's reading quality: its pages, the texts its contents list that were not found.
  await page.goto(`${base}/bo/general_ar/7520/quality`);
  await page.getByRole('heading', { name: 'جودة القراءة' }).waitFor();
  await shot(page, '20-issue-quality', true);

  // Open data: the page, an article's embed code, the embedded article.
  await page.goto(`${base}/data`);
  await page.getByRole('heading', { name: 'البيانات المفتوحة' }).waitFor();
  await page.getByText('texts.jsonl.gz').waitFor();
  await shot(page, '24-open-data', true);
  await page.goto(`${base}/ma/loi/9-26/art_2`);
  await page.locator('#art_2').getByRole('button', { name: 'إجراءات أخرى' }).click();
  await page.locator('#art_2').getByRole('button', { name: 'تضمين' }).click();
  await page.getByText('الصق هذا الرمز في صفحتك').waitFor();
  await shot(page, '25-embed-code');
  await page.keyboard.press('Escape');
  const embed = await desk.newPage();
  await embed.setViewportSize({ width: 640, height: 480 });
  await embed.goto(`${base}/embed/ma/loi/9-26/art_2`);
  await embed.getByRole('heading', { name: 'المادة 2' }).waitFor();
  assert.equal(await embed.locator('header').count(), 0, 'an embedded article has no site header');
  await shot(embed, '26-embedded-article');
  await embed.close();

  // The old address is sent on to the stable one.
  const id = await page.evaluate(async () => (await (await fetch('/api/corpus/at/ma/loi/50-25/')).json()).id);
  await page.goto(`${base}/texts/${id}#art_6`);
  await page.waitForURL('**/ma/loi/50-25/art_6');

  // ── phone ───────────────────────────────────────────────────────────────────
  page = await phone.newPage();
  watch(page);
  await page.goto(`${base}/`);
  await page.getByRole('combobox').fill('الصفقات');
  await page.getByRole('listbox').waitFor();
  await shot(page, '15-phone-home-suggestions');
  await page.goto(`${base}/search?q=${encodeURIComponent('الصفقات العمومية')}`);
  await page.locator('ol li').first().waitFor();
  await shot(page, '16-phone-search');
  await page.goto(`${base}/ma/loi/9-26/art_5`);
  await page.locator('#art_5').waitFor();
  await shot(page, '17-phone-article');
  // On a phone the number opens the article's other tools as a sheet from the bottom; «شارك» its four ways (P13).
  await page.locator('#art_5').getByRole('button', { name: 'المادة 5' }).click();
  await page.getByRole('dialog', { name: 'أدوات المادة 5' }).getByRole('button', { name: 'تبليغ عن خطأ' }).waitFor();
  await shot(page, '17b-phone-article-tools');
  await page.keyboard.press('Escape');
  await page.locator('#art_5').getByRole('button', { name: 'مشاركة' }).click();
  await page.getByRole('button', { name: /نسخ الرابط/ }).waitFor();
  await shot(page, '17c-phone-share');
  await page.keyboard.press('Escape');
  await page.getByRole('button', { name: 'الفهرس' }).click();
  await page.getByRole('navigation', { name: 'الفهرس' }).waitFor();
  await shot(page, '18-phone-outline');
  await page.keyboard.press('Escape');
  await page.getByRole('button', { name: 'بحث في هذا النص' }).click();
  await page.getByRole('searchbox', { name: 'بحث في هذا النص' }).fill('المجلس');
  await page.getByRole('dialog', { name: 'بحث في هذا النص' }).getByRole('button').nth(2).waitFor();
  await shot(page, '18b-phone-find');
  await page.keyboard.press('Escape');
  const wide = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
  assert.equal(wide, false, 'no sideways scroll on a phone');

  assert.deepEqual(errors, [], `page errors: ${errors.join(' | ')}`);
  console.log('reading e2e: ok');
} finally {
  await browser.close();
}
