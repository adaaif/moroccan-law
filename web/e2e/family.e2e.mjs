// The family topic end to end (F3–F16 of the family plan), on a phone and a desk. Needs a backend in development
// (DEBUG: drafts and unchecked tools show) behind the web dev server: BASE_URL (default http://localhost:5194, the
// family pair: WEB_PORT=5194 API_TARGET=http://localhost:8024). SHOTS=<dir> saves a screenshot of each step.
import assert from 'node:assert/strict';
import { chromium } from 'playwright';
const CHANNEL = process.env.CHANNEL; // e.g. CHANNEL=chrome where the bundled browser is not installed

const base = process.env.BASE_URL ?? 'http://localhost:5194';
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

  // The hub: doors by what is happening, the reform's line, the tools.
  await page.goto(`${base}/topics/family`);
  await page.getByRole('link', { name: /غادي نتزوج/ }).waitFor();
  await page.getByText('إصلاح المدونة').first().waitFor();
  // Nine doors and no fold (G2 of the family-papers review): protection is in view, and the question speaks as «we».
  await page.getByRole('link', { name: /محتاج حماية/ }).waitFor();
  assert.equal(await page.getByRole('button', { name: /حالات? أخر/ }).count(), 0, 'no fold over the doors');
  await page.getByRole('button', { name: 'شنو وضعكم؟' }).click();
  await page.getByRole('radio', { name: 'تفارقنا وعندنا ولاد' }).click();
  await page.getByRole('button', { name: /حنا: تفارقنا وعندنا ولاد/ }).waitFor();
  await page.getByText('سنة: يختار الولد من يحضنه من أبيه أو أمه').waitFor();
  await shot(page, '01-hub');

  // A journey: numbered steps on their articles, the time limit, the papers.
  await page.getByRole('link', { name: /غادي نتزوج/ }).click();
  await page.waitForURL('**/topics/family/journeys/marry');
  await page.getByRole('heading', { name: 'الخطوة 3: الملف' }).waitFor();
  assert.ok(await page.getByRole('button', { name: 'المادة 65' }).count() > 0, 'the steps cite art. 65');
  await page.getByRole('link', { name: 'الوثائق المطلوبة' }).click();
  await page.waitForURL('**/checklists/marriage-file');
  // A tick stays on the phone, and only there.
  await page.getByRole('checkbox').first().check();
  await page.reload();
  assert.ok(await page.getByRole('checkbox').first().isChecked(), 'the tick survives a reload');
  await page.getByText('1 من 7').waitFor();
  await shot(page, '02-papers');

  // The calculator asks the family a question at a time (IR13 of the inheritance review): the review's first family
  // (a wife, three daughters, two full brothers) by its questions, each share said in words, the tree drawn from the
  // answers, the family kept in the address through a reload and on the phone under a name.
  await page.goto(`${base}/topics/family/tools/inheritance`);
  await page.getByRole('link', { name: 'كيفاش حسبنا؟' }).waitFor();   // open before a check; «عن «قانون»» says so (#ab-tools)
  await page.getByRole('heading', { name: 'شكون مات؟' }).waitFor();
  const ask = page.locator('#inh-ask');
  const tree = page.locator('#inh-tree');
  const next = () => ask.getByRole('button', { name: 'التالي', exact: true }).click();
  const plus = async (group, n = 1) => {
    for (let i = 0; i < n; i++) await ask.getByRole('group', { name: group, exact: true }).getByRole('button', { name: '+' }).click();
  };
  await next();                                                                  // a man, the death after 2004
  await ask.getByRole('radio', { name: '1', exact: true }).click();              // one wife: the children's question opens
  await plus('البنات', 3);
  await next();                                                                  // no dead child
  await next();                                                                  // no father, no mother
  await next();                                                                  // no grandparent
  await plus('خوتو من الأب والأم', 2);
  // Every tap shows its effect under the question, in words.
  await ask.getByText('الزوجة: الثمن').waitFor();
  await ask.getByText('كل بنت: 2 من 9').waitFor();
  await next();
  await ask.getByRole('button', { name: 'إنهاء الأسئلة' }).click();
  await tree.getByText('كل وحدة: 2 من 9').waitFor();
  await tree.getByText('كل واحد: 5 من 48').waitFor();
  assert.equal(new URL(page.url()).hash, '#v2~m~w1~d3~fb2', 'the family is in the address');
  // A tap on a relative says why, with the article.
  await tree.getByRole('button', { name: /الزوجة/ }).click();
  await tree.getByText('حيت كاينين ولاد، الزوجة كتاخد الثمن', { exact: false }).waitFor();
  await tree.getByRole('button', { name: 'المادة 344' }).waitFor();
  await shot(page, '03-inheritance');

  // A reload keeps the family, every question folded to its answer.
  await page.reload();
  await page.getByRole('button', { name: /الولاد: 3 بنات/ }).waitFor();
  await tree.getByText('كل وحدة: 2 من 9').waitFor();
  // Kept under a name, it is listed in «محفوظاتي» and opens the calculator on it.
  await ask.getByRole('button', { name: 'احفظ هذه العائلة' }).click();
  await ask.getByRole('textbox', { name: 'سمّي هاد العائلة' }).fill('تركة الوالد');
  await ask.getByRole('button', { name: 'حفظ', exact: true }).click();
  await ask.getByText('تحفظات «تركة الوالد»', { exact: false }).waitFor();
  await page.goto(`${base}/saved`);
  await page.getByRole('link', { name: 'تركة الوالد' }).click();
  await page.waitForURL('**/tools/inheritance#v2~m~w1~d3~fb2');
  await tree.getByText('كل واحد: 5 من 48').waitFor();

  // A grandchild is entered through their dead father (IR1): his son and daughter get the compulsory bequest, on the tree.
  await ask.getByRole('button', { name: 'ابدأ من جديد' }).click();
  await next();
  await ask.getByRole('radio', { name: '1', exact: true }).click();
  await plus('الأبناء (ذكور)');
  await plus('البنات');
  await ask.getByRole('radiogroup', { name: 'شي ولد مات قبل منو وخلّى ولادو؟' }).getByRole('radio', { name: 'نعم' }).click();
  await plus('ولادو الذكور');
  await plus('بناتو');
  await ask.getByRole('radiogroup', { name: 'مراتو باقية حية؟' }).getByRole('radio', { name: 'نعم' }).click();
  assert.equal(new URL(page.url()).hash, '#v2~m~w1~s1~d1~xm1a1wp', 'the dead son, his widow alive, his mother the wife');
  await ask.getByText('الحفيد (وصية واجبة): 119 من 720').waitFor();
  await tree.getByRole('button', { name: 'عرض الشجرة' }).first().click();
  await tree.getByText('ولاد الابن اللي مات قبل منو').waitFor();
  assert.equal(await tree.getByText('وصية واجبة', { exact: true }).count(), 2, 'a bequest line under each of his children');
  await tree.getByText('119 من 720').waitFor();
  await tree.getByText('119 من 1440').waitFor();

  // The Minbariyya, as art. 368 writes it: the shares rise to 27.
  await page.goto(`${base}/topics/family/tools/inheritance#v2~m~w1~d2~fa~mo`);
  await page.reload();
  await tree.getByText('كل وحدة: 8 من 27').waitFor();
  await tree.getByText('4 من 27').first().waitFor();

  // Dates from the day of a birth.
  await page.goto(`${base}/topics/family/tools/dates`);
  await page.getByRole('button', { name: 'يوم آخر' }).click();
  await page.locator('input[type=date]').fill('2026-10-19');
  // 30 days end on 18 Nov, Independence Day: the declaration runs to the next working day (decree 2.22.04, art. 40;
  // U12 of the Moroccan-design review).
  await page.getByText('19 نونبر 2026').first().waitFor();
  await page.getByText(/عيد الاستقلال/).first().waitFor();
  await page.getByText('19 أبريل 2027').waitFor();

  // Protection: the quick exit leaves and takes the page out of the history.
  await page.goto(`${base}/topics/family`);
  await page.goto(`${base}/topics/family/pages/protection`);
  await page.getByRole('heading', { name: 'الحماية من العنف' }).waitFor();
  // Each number with the official page that gives it; 177 waits for its own (C1).
  await page.getByRole('link', { name: /اتصال: 19/ }).waitFor();
  await page.getByText('الرقم 19 من dgsn.gov.ma').waitFor();
  assert.equal(await page.getByText('177').count(), 0, 'no number without its page');
  assert.equal(await page.title(), 'صفحة — قانون', 'a neutral tab title');
  await page.route('https://www.google.com/**', (route) => route.fulfill({ body: '<title>neutral</title>' }));
  await page.getByRole('button', { name: /خروج سريع/ }).click();
  await page.waitForURL('https://www.google.com/**');
  await page.goBack();
  assert.ok(!page.url().includes('/pages/protection'), `back does not return to the protection page: ${page.url()}`);

  // Separating as a choice (G9): the wife's answer opens the husband's way only on its condition.
  await page.goto(`${base}/topics/family/pages/ways`);
  await page.getByRole('radio', { name: 'الزوجة' }).click();
  await page.locator('article').getByText('حكما بالتطليق للشقاق', { exact: false }).waitFor();
  await shot(page, '03b-ways');

  // The reform: its stage said first, and «تابع».
  await page.goto(`${base}/topics/family/reform`);
  await page.getByText('لم يصدر بعد أي قانون جديد للأسرة', { exact: false }).first().waitFor();
  assert.equal(await page.locator('[aria-current="step"]').innerText(), 'مقترحات معلنة');
  await shot(page, '04-reform');

  // The numbers: the chart and its table.
  const desk = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const d = await desk.newPage();
  watch(d);
  await d.goto(`${base}/topics/family/pages/numbers`);
  await d.getByText('الأرقام في جدول').first().click();
  await d.getByRole('cell', { name: '15.425' }).waitFor();
  await shot(d, '05-numbers');

  assert.deepEqual(errors, [], 'no errors in the page');
  console.log('family: ok');
} finally {
  await browser.close();
}
