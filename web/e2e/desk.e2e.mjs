// The access desk end to end, in a real browser. A person signs up and asks for access; a superuser opens the desk from
// the header's menu, sees the request with the day its answer is due, opens it, reads the letter and accepts it in two
// steps; the person makes a key; the superuser changes the size, ends the key, renews and ends the access, asks one
// request a question and declines another, and reads it all in the log. A reader who opens /data/desk is shown nothing
// of it, and the server refuses them. The person's request and key go through the API (the holder's page is tested by
// access.e2e.mjs); the superuser and the desk's rows are made by `manage.py shell -c` on the same throwaway database.
// Needs both dev servers on a throwaway database with requests open, and the same variables in this script's
// environment (its shell commands reach that database):
//   export DATABASE_URL=sqlite:////<scratch>/e2e.sqlite3 OPEN_DATA=request OPEN_DATA_DIR=<scratch>/open REDIS_URL=
//   export ACCESS_LETTER_TO=staff@example.org EMAIL_BACKEND=django.core.mail.backends.filebased.EmailBackend EMAIL_FILE_PATH=<scratch>/mail
//   (cd back && python manage.py migrate && python manage.py load_sample && python manage.py export_open_data)
//   (cd back && python manage.py runserver 8074)
//   (cd web && WEB_PORT=5274 API_TARGET=http://localhost:8074 npx vite --port 5274)
//   BASE_URL=http://localhost:5274 node e2e/desk.e2e.mjs      (SHOTS=<dir> also saves screenshots of each part and sheet)
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { randomBytes } from 'node:crypto';
import path from 'node:path';
import { chromium } from 'playwright';

const base = process.env.BASE_URL ?? 'http://localhost:5274';
const back = path.resolve(import.meta.dirname, '../../back');
const shots = process.env.SHOTS;
const shot = async (page, name, fullPage = true) => {
  if (shots) await page.screenshot({ path: `${shots}/${name}.png`, fullPage });
};
assert.equal(process.env.OPEN_DATA, 'request', 'run with OPEN_DATA=request, as the backend is');
assert.ok(process.env.DATABASE_URL, 'run with the DATABASE_URL the backend uses');

/** Python run by the backend's manage.py on the throwaway database. */
const shell = (code) => execFileSync(path.join(back, '.venv/bin/python'), ['manage.py', 'shell', '-c', code],
  { cwd: back, env: process.env, encoding: 'utf8' });
// The superuser «chief-desk» and the desk's other rows: a late request, one answered, a change request, two holders.
// Their password is drawn for this run and handed to the seed, which refuses a database that is not a development one.
process.env.E2E_PASSWORD = `pw-${randomBytes(12).toString('base64url')}`;
shell(`exec(open(${JSON.stringify(path.resolve(import.meta.dirname, 'fixtures/desk-seed.py'))}).read())`);
const chief = { username: 'chief-desk', password: process.env.E2E_PASSWORD };

const username = `e2edesk${String(Date.now()).slice(-7)}`;
const email = `${username}@example.org`;
const password = `pw-${randomBytes(12).toString('base64url')}`;   // drawn for each run
const who = `مكتبة الحقوق ${username.slice(-4)}`;

const browser = await chromium.launch();
const pageErrors = [];
const watch = (page) => page.on('pageerror', (e) => pageErrors.push(String(e)));

/** The site's API as an account: a JWT asked for with its password. */
async function asAccount(request, login, secret) {
  const answer = await request.post(`${base}/api/auth/token/`, { data: { username: login, password: secret } });
  assert.equal(answer.status(), 200, await answer.text());
  const { access } = await answer.json();
  return { Authorization: `Bearer ${access}` };
}

/** Signs in through the sign-in page and keeps the session for the next contexts. */
async function signIn(login, secret, lang = 'ar') {
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  await ctx.addInitScript((l) => localStorage.setItem('law.lang', l), lang);
  const page = await ctx.newPage();
  watch(page);
  await page.goto(`${base}/login`);
  await page.getByLabel('اسم المستخدم أو البريد الإلكتروني', { exact: true }).fill(login);
  await page.getByLabel('كلمة السر', { exact: true }).fill(secret);
  await page.getByRole('button', { name: 'دخول', exact: true }).last().click();
  await page.waitForURL('**/account');
  return { ctx, page };
}

/** Waits until a line in `scope` says `re`, read without the marks that keep a typed name in its own direction. */
async function says(scope, re, timeout = 15000) {
  const end = Date.now() + timeout;
  for (;;) {
    const lines = (await scope.allInnerTexts()).flatMap((t) => t.split('\n')).map((l) => l.replace(/[\u2066-\u2069]/g, '').trim());
    if (lines.some((l) => re.test(l))) return;
    if (Date.now() > end) throw new Error(`nothing says ${re}: ${lines.slice(0, 8).join(' | ')}`);
    await new Promise((r) => setTimeout(r, 200));
  }
}

/** Nothing wider than the screen, and no words under 14 px. */
async function fits(page, width, within = 'main') {
  const wide = await page.evaluate(() => document.documentElement.scrollWidth);
  assert.ok(wide <= width, `${page.url()} is ${wide} px wide at ${width}`);
  const small = await page.evaluate((sel) => [...document.querySelectorAll(`${sel} *`)].filter((e) => e.checkVisibility?.()
    && [...e.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim())
    && parseFloat(getComputedStyle(e).fontSize) < 14).map((e) => `${e.tagName}: ${e.textContent.trim().slice(0, 40)}`), within);
  assert.deepEqual(small, [], `${page.url()}: words under 14 px`);
}

/** Targets a finger can hit: the desk's buttons and links are 44 px high at least. */
async function targets(page, within) {
  const low = await page.evaluate((sel) => [...document.querySelectorAll(`${sel} button, ${sel} a, ${sel} summary, ${sel} input:not([type=radio]):not([type=checkbox])`)]
    .filter((e) => e.checkVisibility?.() && e.getBoundingClientRect().height < 44)
    .map((e) => `${e.tagName}.${e.className}: ${e.textContent.trim().slice(0, 30)} (${Math.round(e.getBoundingClientRect().height)})`), within);
  assert.deepEqual(low, [], `${page.url()}: targets under 44 px`);
}

try {
  // A person signs up, proves the address and asks for the API.
  let ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  let page = await ctx.newPage();
  watch(page);
  await page.goto(`${base}/register`);
  await page.getByLabel('اسم المستخدم', { exact: true }).fill(username);
  await page.getByLabel('البريد الإلكتروني', { exact: true }).fill(email);
  await page.getByLabel('كلمة السر', { exact: true }).fill(password);
  await page.getByRole('button', { name: 'إنشاء الحساب' }).click();
  await page.waitForURL('**/account');
  shell(`from django.utils import timezone\nfrom django.contrib.auth import get_user_model\nget_user_model().objects.filter(username='${username}').update(email_proven_at=timezone.now())`);
  const person = await asAccount(ctx.request, username, password);
  const terms = (await (await ctx.request.get(`${base}/api/access/`)).json()).terms;
  let answer = await ctx.request.post(`${base}/api/access/request/`, { headers: person, data: {
    name: who, kind: 'school', purpose: 'درس عن قانون الشغل في الكلية، يعرض المواد بمصدرها ورابطها.', wants_api: true,
    wants_data: false, runs_at: 'https://cours.example.ma', volume: 'small', commercial: false, terms, consent: true } });
  assert.equal(answer.status(), 201, await answer.text());

  // A reader is shown nothing of the desk: no line in the menu, the page an unknown address shows, and a refusal.
  await page.reload();
  await page.locator('.ac-trigger').click();
  await page.locator('.ac-menu').getByRole('link', { name: /^وصولي/ }).waitFor();
  assert.equal(await page.locator('.ac-menu').getByRole('link', { name: /إدارة الوصول/ }).count(), 0);
  await page.keyboard.press('Escape');
  await page.goto(`${base}/data/desk`);
  await page.getByRole('heading', { level: 1, name: 'لم نجد هذه الصفحة' }).waitFor();
  assert.equal(await page.getByText('إدارة الوصول').count(), 0);
  answer = await ctx.request.get(`${base}/api/access/desk/`, { headers: person });
  assert.equal(answer.status(), 403);
  assert.deepEqual((await answer.json()).errors, [{ field: 'desk', code: 'forbidden' }]);
  await shot(page, '01-reader-desk-ar');
  await ctx.close();

  // The superuser: «أنا» opens on the requests waiting, and the menu's line leads to the desk with their number.
  ({ ctx, page } = await signIn(chief.username, chief.password));
  const line = page.locator('.ac-now').getByRole('link', { name: /طلبات تنتظر جوابك/ });
  await line.waitFor();
  const waiting = Number((await line.innerText()).match(/\d+/)?.[0]);
  assert.ok(waiting >= 5, `«أنا» says ${waiting} requests wait`);
  await page.locator('.ac-trigger').click();
  const item = page.locator('.ac-menu').getByRole('link', { name: /^إدارة الوصول/ });
  await item.waitFor();
  assert.equal(Number(await item.locator('.ac-n').innerText()), waiting);
  await item.click();
  await page.waitForURL('**/data/desk');
  await page.getByRole('heading', { level: 1, name: 'إدارة الوصول' }).waitFor();
  // The strip: requests open, where the letters go, the terms, the edition and the next.
  const strip = page.locator('.dk-strip');
  await strip.getByText('الطلبات مفتوحة').waitFor();
  await strip.getByText(/رسائلك تصل إلى .*staff@example\.org/).waitFor();
  await strip.getByText(/^الشروط: /).waitFor();
  await strip.getByText(/^آخر نسخة: /).waitFor();

  // What waits, the longest-waiting first: the late one marked, the answered one marked, the change request named;
  // the person's request is last, its answer due in days.
  const rows = page.locator('.dk-block').first().locator('.dk-row');
  assert.equal(await rows.count(), waiting);
  await rows.first().locator('.dk-due.late').getByText(/^تأخر /).waitFor();
  await page.locator('.dk-row', { hasText: 'مختبر القانون الرقمي' }).getByText('أجاب عن سؤالك').waitFor();
  await page.locator('.dk-row', { hasText: 'Juris Atlas' }).getByText('طلب تعديل').first().waitFor();
  const mine = rows.last();
  await mine.getByText(who).waitFor();
  await mine.locator('.dk-due').getByText(/^(بقي|اليوم)/).waitFor();
  await page.locator('.dk-block', { hasText: 'تنتظر جواب أصحابها' }).getByText('Lexa SARL').waitFor();
  await page.getByText('آخر 30 يوما').waitFor();
  await shot(page, '02-desk-waiting-ar');
  // «تجديد» beside an access that ends soon opens its sheet on renewing, a year ahead; nothing goes until its button.
  await page.locator('.dk-block', { hasText: 'وصولات تنتهي خلال 30 يوما' }).getByRole('button', { name: /^تجديد/ }).click();
  await page.locator('.dk-side').getByRole('heading', { name: 'تجديد الوصول' }).waitFor();
  await page.locator('.dk-side').getByRole('button', { name: /^جدّد حتى / }).waitFor();
  await page.keyboard.press('Escape');
  await page.locator('.dk-side').waitFor({ state: 'detached' });

  // The request's sheet: the answers, the account, and the three acts at its foot.
  await mine.click();
  const sheet = page.locator('.dk-side');
  await sheet.getByRole('heading', { level: 2, name: who }).waitFor();
  await sheet.getByRole('link', { name: 'https://cours.example.ma' }).waitFor();
  await sheet.getByText(`@${username}`).waitFor();
  await sheet.getByText('✓ بريد مؤكد').waitFor();
  await sheet.getByText('لم يكتب في النقاش').waitFor();
  // Accepting: the ticks and the size start from what was asked; the letter, then the sentence that restates it.
  await sheet.getByRole('button', { name: 'قبول', exact: true }).click();
  assert.ok(await sheet.getByRole('checkbox', { name: 'الواجهة البرمجية' }).isChecked());
  assert.ok(!(await sheet.getByRole('checkbox', { name: 'قاعدة البيانات' }).isChecked()));
  assert.ok(await sheet.getByRole('radio', { name: /^تجربة/ }).isChecked());
  assert.equal(await sheet.getByLabel('طلبات في الدقيقة').count(), 0, 'a partner\'s numbers only for that size');
  await sheet.getByRole('radio', { name: /^شريك/ }).check();
  await sheet.getByLabel('طلبات في الدقيقة').waitFor();
  await sheet.getByRole('radio', { name: /^تجربة/ }).check();
  await sheet.getByRole('button', { name: 'التالي: الرسالة' }).click();
  const letter = sheet.locator('.dk-letter');
  await letter.waitFor();
  assert.equal(await letter.getAttribute('lang'), 'ar');
  await letter.getByText(who).first().waitFor();
  await sheet.locator('.dk-restate').getByText(/^ستعطي: الواجهة البرمجية، حجم «تجربة»، حتى .+\.$/).waitFor();
  await shot(page, '03-desk-accept-letter-ar');
  await sheet.getByRole('button', { name: 'أعطِ الوصول' }).click();
  await sheet.getByText('قُبل الطلب، وذهبت الرسالة.').waitFor();
  assert.equal(await sheet.getByRole('button', { name: 'قبول', exact: true }).count(), 0);
  await says(sheet.locator('.dk-history li > span'), /^قبل chief-desk طلب /);
  // The list is asked again: one fewer waits.
  await page.waitForFunction((n) => document.querySelectorAll('.dk-block:first-child .dk-row').length === n, waiting - 1);

  // The person makes a key; it opens the API at the size given.
  const made = await ctx.request.post(`${base}/api/access/keys/`, { headers: person, data: { name: 'الخادم' } });
  assert.equal(made.status(), 201, await made.text());
  const key = (await made.json()).key;
  answer = await ctx.request.get(`${base}/api/v1/bulletin/`, { headers: { 'X-Api-Key': key } });
  assert.equal(answer.status(), 200);
  assert.match(answer.headers()['ratelimit-policy'] ?? '', /"minute";q=30/);

  // The access in the ledger: found by the search box, its sheet with the key.
  await page.getByRole('link', { name: 'الوصولات', exact: true }).click();
  await page.waitForURL('**/data/desk?part=accesses');
  await page.getByLabel('ابحث بالاسم أو اسم المستخدم أو البريد').fill(username);
  const accessRow = page.locator('.dk-row', { hasText: who });
  // The search is asked a moment after the typing stops: then one row is left.
  await page.waitForFunction(() => document.querySelectorAll('.dk-list .dk-row').length === 1);
  await accessRow.waitFor();
  await accessRow.click();
  const asheet = page.locator('.dk-side');
  await asheet.getByRole('heading', { level: 2, name: who }).waitFor();
  await asheet.getByText(`${key.slice(0, 12)}…`).waitFor();
  await shot(page, '04-desk-access-ar');

  // Changing the size: one form, a second step that restates it; the key works with the new limits at once.
  await asheet.getByRole('button', { name: 'تغيير', exact: true }).click();
  await asheet.getByRole('radio', { name: /^تطبيق/ }).check();
  await asheet.getByRole('button', { name: 'التالي', exact: true }).click();
  await asheet.locator('.dk-restate').getByText('سيصير: الواجهة البرمجية، حجم «تطبيق»، بدل الواجهة البرمجية، حجم «تجربة».').waitFor();
  await asheet.getByText('تخبر رسالة صاحبه بذلك.').waitFor();
  await asheet.getByRole('button', { name: 'نعم، غيّر' }).click();
  await asheet.getByText('تغيّر الوصول، وذهبت الرسالة.').waitFor();
  answer = await ctx.request.get(`${base}/api/v1/bulletin/`, { headers: { 'X-Api-Key': key } });
  assert.match(answer.headers()['ratelimit-policy'] ?? '', /"minute";q=120/);

  // Ending the leaked key, asked once more: it opens nothing after.
  await asheet.getByRole('button', { name: 'إنهاء المفتاح' }).click();
  await asheet.getByText('يتوقف هذا المفتاح الآن، وتخبر رسالة صاحبه أن ينشئ مفتاحا جديدا.').waitFor();
  await asheet.getByRole('button', { name: 'نعم، أنهِ المفتاح' }).click();
  await asheet.getByText('انتهى المفتاح، وذهبت الرسالة.').waitFor();
  answer = await ctx.request.get(`${base}/api/v1/bulletin/`, { headers: { 'X-Api-Key': key } });
  assert.equal(answer.status(), 401);
  assert.deepEqual((await answer.json()).errors, [{ field: 'key', code: 'ended' }]);

  // Renewing: a year ahead unless another day is chosen; the button says the day.
  await asheet.getByRole('button', { name: 'تجديد', exact: true }).click();
  await asheet.getByLabel('حتى').fill('2028-03-31');
  await asheet.getByRole('button', { name: 'جدّد حتى 31 مارس 2028' }).click();
  await asheet.getByText('جُدّد الوصول، وذهبت الرسالة.').waitFor();
  await asheet.getByText(/حتى 31 مارس 2028/).first().waitFor();

  // Ending the access with a reason, in a second step.
  await asheet.getByRole('button', { name: 'إنهاء', exact: true }).click();
  await asheet.getByRole('radio', { name: /^تسرّب أحد مفاتيحه/ }).check();
  await asheet.getByRole('button', { name: 'التالي', exact: true }).click();
  await says(asheet.locator('.dk-restate'), /^سينتهي وصول .+ الآن، وتتوقف مفاتيحه كلها\.$/);
  await asheet.getByRole('button', { name: 'نعم، أنهِ الوصول' }).click();
  await asheet.getByText('انتهى الوصول، وذهبت الرسالة.').waitFor();
  await asheet.getByText(/^انتهى .+: تسرّب أحد مفاتيحه$/).waitFor();
  assert.equal(await asheet.getByRole('button', { name: 'تغيير', exact: true }).count(), 0, 'an ended access has no acts');

  // Back to what waits: a question to one request, with the letter; a decline of another, each reason with its sentence.
  await page.getByRole('link', { name: /^ينتظرك/ }).click();
  await page.waitForURL(/\/data\/desk$/);
  await page.locator('.dk-row', { hasText: 'جمعية الحق في المعلومة' }).click();
  await sheet.getByRole('button', { name: 'سؤال', exact: true }).click();
  await sheet.getByRole('button', { name: 'ما اسم الكلية؟' }).click();
  assert.equal(await sheet.getByLabel('سؤالك، في سطر').inputValue(), 'ما اسم الكلية؟', 'a last question is offered again');
  await sheet.getByLabel('سؤالك، في سطر').fill('من يقف وراء الجمعية، وما رقم تسجيلها؟');
  await sheet.getByRole('button', { name: 'التالي: الرسالة' }).click();
  await sheet.locator('.dk-letter').getByText('من يقف وراء الجمعية، وما رقم تسجيلها؟').waitFor();
  await sheet.getByRole('button', { name: 'أرسل السؤال' }).click();
  await sheet.getByText('ذهب السؤال، والطلب ينتظر جوابه.').waitFor();

  await page.locator('.dk-list .dk-row', { hasText: 'Rédaction Exemple' }).click();
  await sheet.getByRole('heading', { level: 2, name: 'Rédaction Exemple' }).waitFor();
  await sheet.getByText('حذف المراجعون منها 1').waitFor();
  await sheet.getByRole('button', { name: 'رفض', exact: true }).click();
  await sheet.getByText('المطلوب أكثر مما يحتاجه الاستعمال الذي وصفته.').waitFor();
  await sheet.getByRole('button', { name: 'التالي: الرسالة' }).click();
  await sheet.getByText('اختر سببا.').waitFor();
  await sheet.getByRole('radio', { name: /^لا نعرف من يطلب/ }).check();
  await sheet.getByRole('button', { name: 'التالي: الرسالة' }).click();
  // Its account reads French: the letter is in French, as it will be sent.
  await sheet.locator('.dk-letter[lang="fr"]').getByText('nous ne pouvons pas savoir qui demande.', { exact: false }).waitFor();
  await sheet.getByRole('button', { name: 'أرسل الرفض' }).click();
  await sheet.getByText('رُفض الطلب، وذهبت الرسالة.').waitFor();

  // The change request: what it holds against what it asks; accepting changes it in place.
  await page.locator('.dk-list .dk-row', { hasText: 'Juris Atlas' }).first().click();
  await sheet.getByText('ما يملكه الآن وما يطلبه').waitFor();
  await sheet.locator('.dk-compare td.moved').first().waitFor();
  await sheet.getByRole('button', { name: 'قبول', exact: true }).click();
  await sheet.getByRole('heading', { name: 'قبول التعديل' }).waitFor();
  await shot(page, '05-desk-change-request-ar');
  await sheet.getByRole('button', { name: 'التالي: الرسالة' }).click();
  await sheet.locator('.dk-restate').getByText(/^سيصير وصوله: الواجهة البرمجية وقاعدة البيانات، حجم «تطبيق»/).waitFor();
  await sheet.getByRole('button', { name: 'غيّر وصوله' }).click();
  await sheet.getByText('قُبل الطلب، وذهبت الرسالة.').waitFor();

  // The log: every act, newest first, a sentence each.
  await page.getByRole('link', { name: 'السجل', exact: true }).click();
  await page.waitForURL('**/data/desk?part=log');
  const log = page.locator('.dk-log .who > span');
  await says(log, /^قبل chief-desk تعديل وصول Juris Atlas: الواجهة البرمجية وقاعدة البيانات، حجم «تطبيق»/);
  await says(log, /^رفض chief-desk طلب Rédaction Exemple: لا نعرف من يطلب$/);
  await says(log, /^سأل chief-desk جمعية الحق في المعلومة: «من يقف وراء الجمعية، وما رقم تسجيلها؟»$/);
  await says(log, /^أنهى chief-desk وصول .+: تسرّب أحد مفاتيحه$/);
  await says(log, /^جدّد chief-desk وصول .+ حتى 31 مارس 2028، بدل /);
  await says(log, /^غيّر chief-desk وصول .+: الواجهة البرمجية، حجم «تطبيق»، بدل الواجهة البرمجية، حجم «تجربة»$/);
  await says(log, /^أنهى chief-desk مفتاحا لوصول /);
  await says(log, /^قبل chief-desk طلب .+: الواجهة البرمجية، حجم «تجربة»، حتى /);
  // The back button walks the parts back, and closes an open sheet first.
  await page.locator('.dk-log .dk-row').first().click();
  await page.locator('.dk-side .dk-sheet h2').waitFor();
  await page.goBack();
  await page.locator('.dk-side').waitFor({ state: 'detached' });
  assert.ok(page.url().endsWith('?part=log'));
  await page.goBack();
  await page.waitForURL(/\/data\/desk$/);
  await page.getByText('طلبات تنتظر جوابك').waitFor();

  // The use and the editions.
  await page.getByRole('link', { name: 'الاستعمال', exact: true }).click();
  await page.getByText('الطلبات حسب الباب').waitFor();
  await page.locator('.dk-doors').getByText('البحث').waitFor();
  await page.getByText('الأكثر استعمالا').waitFor();
  await page.getByRole('link', { name: 'النسخ', exact: true }).click();
  await page.getByText(/^تُبنى النسخة التالية يوم /).waitFor();
  assert.match(await page.locator('.dk-hash code').first().innerText(), /^[0-9a-f]{64}$/);
  await page.locator('.dk-table').getByText('texts.jsonl.gz').waitFor();
  const session = await ctx.storageState();
  await ctx.close();

  // Every part and both sheets at a phone's width and a desk's, in both languages and both themes: nothing wider than
  // the screen, no words under 14 px, targets of 44 px; on a phone a sheet comes from the bottom with its acts at the
  // foot, on a desk it sits beside the list.
  const views = [['waiting', ''], ['request', ''], ['accesses', '?part=accesses'], ['access', '?part=accesses'],
    ['use', '?part=use'], ['editions', '?part=editions'], ['log', '?part=log']];
  for (const [width, height] of [[360, 780], [1280, 900]]) {
    for (const lang of ['ar', 'fr']) {
      for (const colorScheme of ['light', 'dark']) {
        const view = await browser.newContext({ viewport: { width, height }, colorScheme, storageState: session });
        await view.addInitScript((l) => localStorage.setItem('law.lang', l), lang);
        const p = await view.newPage();
        watch(p);
        for (const [name, search] of views) {
          await p.goto(`${base}/data/desk${search}`);
          await p.locator('.dk-list .dk-block, .dk-list .dk-parts').first().waitFor();
          await p.waitForLoadState('networkidle');
          let within = 'main';
          if (name === 'request' || name === 'access') {
            await p.locator('.dk-list .dk-row').first().click();
            within = width < 1024 ? '[role="dialog"]' : '.dk-side';
            await p.locator(`${within} .dk-sheet h2`).waitFor();
            await p.waitForLoadState('networkidle');
            const foot = p.locator(`${within} .dk-foot`);
            if (await foot.count()) {
              const box = await foot.boundingBox();
              assert.ok(box.y + box.height <= height + 1, `${name} ${width}: the acts are in reach (${box.y})`);
            }
          }
          await fits(p, width, within);
          await targets(p, within === 'main' ? '.dk-list' : within);
          if (shots) {
            const file = `${shots}/m-${name}-${width}-${lang}-${colorScheme}.png`;
            if (within === '[role="dialog"]') await p.locator(within).screenshot({ path: file });
            else await p.screenshot({ path: file, fullPage: width >= 1024 || within === 'main' });
          }
        }
        await view.close();
      }
    }
  }

  assert.deepEqual(pageErrors, []);
  console.log('desk e2e: ok');
} finally {
  await browser.close();
}
