// Access on request end to end, in a real browser: a visitor reads /data, a person signs up and asks, the staff asks a
// question and the person answers it on «وصولي» (/data/access), the staff accepts, the person makes a key and sees it
// once with a first call that holds it, uses it, asks to change the access (the database and a bigger size), answers
// the staff's question about it, the staff accepts and the same key works on with the new limits, takes a file of the
// edition and its receipt, makes a second key and ends the first, and ends the access; then a decline. Each state of
// the page is drawn at 360 and 1280 px, in both languages and both themes. The staff's answers are the backend's own
// services, called through `manage.py shell -c` on the same throwaway database.
// Needs both dev servers on a throwaway database with requests open, and the same variables in this script's
// environment (its shell commands reach that database):
//   export DATABASE_URL=sqlite:////<scratch>/e2e.sqlite3 OPEN_DATA=request OPEN_DATA_DIR=<scratch>/open REDIS_URL=
//   (cd back && python manage.py migrate && python manage.py load_sample && python manage.py export_open_data)
//   (cd back && python manage.py runserver 8071)
//   (cd web && WEB_PORT=5271 API_TARGET=http://localhost:8071 npx vite)
//   BASE_URL=http://localhost:5271 node e2e/access.e2e.mjs      (SHOTS=<dir> also saves screenshots of each page)
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { randomBytes } from 'node:crypto';
import path from 'node:path';
import { chromium } from 'playwright';

const base = process.env.BASE_URL ?? 'http://localhost:5190';
const back = path.resolve(import.meta.dirname, '../../back');
const shots = process.env.SHOTS;
const shot = async (page, name, fullPage = true) => {
  if (shots) await page.screenshot({ path: `${shots}/${name}.png`, fullPage });
};
assert.equal(process.env.OPEN_DATA, 'request', 'run with OPEN_DATA=request, as the backend is');
assert.ok(process.env.DATABASE_URL, 'run with the DATABASE_URL the backend uses');

/** Python run by the backend's manage.py on the throwaway database: the staff's side of a request. */
const shell = (code) => execFileSync(path.join(back, '.venv/bin/python'), ['manage.py', 'shell', '-c', code],
  { cwd: back, env: process.env, encoding: 'utf8' });

const username = `e2eaccess${String(Date.now()).slice(-7)}`;
const email = `${username}@example.org`;
const password = `pw-${randomBytes(12).toString('base64url')}`;   // drawn for each run
const who = 'مختبر القانون الرقمي';

const chief = `
from django.conf import settings
assert settings.DEBUG, 'a development database only: this makes a superuser'
from django.contrib.auth import get_user_model
from apps.opendata.models import Request
from apps.opendata.services import requests
U = get_user_model()
by, _ = U.objects.get_or_create(username='chief-e2e', defaults={'email': 'chief-e2e@example.org'})
U.objects.filter(pk=by.pk).update(is_superuser=True, is_staff=True)
by.refresh_from_db()
r = Request.objects.filter(user__username='${username}').order_by('-pk').first()
`;

const browser = await chromium.launch();
const pageErrors = [];
const watch = (page) => page.on('pageerror', (e) => pageErrors.push(String(e)));

/** At 360 px nothing is wider than the phone, and no words under 14 px. */
async function fits(page, width, within = 'main') {
  const wide = await page.evaluate(() => document.documentElement.scrollWidth);
  assert.ok(wide <= width, `${page.url()} is ${wide} px wide at ${width}`);
  const small = await page.evaluate((sel) => [...document.querySelectorAll(`${sel} *`)].filter((e) => e.checkVisibility?.()
    && [...e.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim())
    && parseFloat(getComputedStyle(e).fontSize) < 14).map((e) => `${e.tagName}: ${e.textContent.trim().slice(0, 40)}`), within);
  assert.deepEqual(small, [], `${page.url()}: words under 14 px`);
}

/** Each page at a phone's width and a desk's, in both languages and both themes. */
async function matrix(name, to, { session, within = 'main', element } = {}) {
  for (const [width, height] of [[360, 780], [1280, 900]]) {
    for (const lang of ['ar', 'fr']) {
      for (const colorScheme of ['light', 'dark']) {
        const ctx = await browser.newContext({ viewport: { width, height }, colorScheme, storageState: session });
        await ctx.addInitScript((l) => localStorage.setItem('law.lang', l), lang);
        const page = await ctx.newPage();
        watch(page);
        await page.goto(`${base}${to}`);
        await page.locator(element ?? 'h1').first().waitFor();
        await page.waitForLoadState('networkidle');
        await fits(page, width, within);
        if (shots) {
          const file = `${shots}/m-${name}-${width}-${lang}-${colorScheme}.png`;
          if (element) await page.locator(element).screenshot({ path: file });
          else await page.screenshot({ path: file, fullPage: true });
        }
        await ctx.close();
      }
    }
  }
}

try {
  // A visitor: the programme's page, in its order, with the edition and its hash.
  let ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  let page = await ctx.newPage();
  watch(page);
  await page.goto(`${base}/data`);
  await page.getByRole('heading', { level: 1, name: 'البيانات والواجهة البرمجية' }).waitFor();
  await page.getByText('رخصة مفتوحة، بطلب', { exact: true }).waitFor();
  await page.locator('#ask').waitFor();
  await page.locator('#how').waitFor();
  await page.locator('#api').waitFor();
  await page.getByText('طلبات في الدقيقة').first().waitFor();
  for (const read of ['/api/v1/search?q=', '/api/v1/texts/<path>', '/api/v1/references', '/api/v1/changes?since=']) {
    await page.getByText(read, { exact: true }).waitFor();
  }
  assert.equal(await page.getByText('120 طلبا في الدقيقة').count(), 0, 'the old notes of the site\'s own API are gone');
  const sha = await page.locator('.ax-hash code').innerText();
  assert.match(sha, /^[0-9a-f]{64}$/);
  await page.getByRole('link', { name: '/api/v1/openapi.yaml' }).waitFor();
  await shot(page, '01-data-visitor-ar');

  // The door asks to sign in first, and the terms are a page of their own.
  await page.getByRole('link', { name: 'اطلب الوصول' }).first().click();
  await page.waitForURL('**/login');
  await page.goto(`${base}/data/terms`);
  await page.getByRole('heading', { level: 1, name: 'شروط الوصول' }).waitFor();
  assert.equal(await page.locator('.ax-terms li').count(), 10);

  // /privacy says what a request keeps, and for how long, on its ruler and among what an account leaves.
  await page.goto(`${base}/privacy#write`);
  await page.locator('#write').getByRole('heading', { name: 'طلب الوصول إلى البيانات' }).waitFor();
  await page.locator('.pv-row', { hasText: 'طلب الوصول إلى البيانات: أجوبتك والقرار' }).getByText('ما دام الوصول، و12 شهرا بعده').first().waitFor();
  await page.locator('.pv-row', { hasText: 'طلب وصول لم نقبله' }).getByText('6 أشهر، ثم بلا أجوبتك').first().waitFor();
  await shot(page, '07-privacy-ar');
  await ctx.close();

  // Sign-up, then the form: the unproven address is said with the way to prove it.
  ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  page = await ctx.newPage();
  watch(page);
  await page.goto(`${base}/register`);
  await page.getByLabel('اسم المستخدم', { exact: true }).fill(username);
  await page.getByLabel('البريد الإلكتروني', { exact: true }).fill(email);
  await page.getByLabel('كلمة السر', { exact: true }).fill(password);
  await page.getByRole('button', { name: 'إنشاء الحساب' }).click();
  await page.waitForURL('**/account');
  // «أنا» has no «وصولي» for an account that never asked.
  await page.getByRole('link', { name: /^اطرح سؤالك الأول/ }).waitFor();
  await page.waitForLoadState('networkidle');
  assert.equal(await page.getByRole('link', { name: /^وصولي/ }).count(), 0);
  // «وصولي» before asking: one line and the way to ask.
  await page.goto(`${base}/data/access`);
  await page.getByRole('heading', { level: 1, name: 'وصولي' }).waitFor();
  await page.getByText('لم تطلب الوصول إلى قاعدة البيانات ولا إلى الواجهة البرمجية.').waitFor();
  await page.locator('main').getByRole('link', { name: 'اطلب الوصول' }).waitFor();
  assert.equal(await page.title(), 'وصولي — قانون');
  await matrix('none', '/data/access', { session: await ctx.storageState() });
  await page.goto(`${base}/data/request`);
  await page.getByText('بريد حسابك غير مؤكد بعد').waitFor();
  await page.getByRole('link', { name: 'أكّد بريدك' }).waitFor();

  // Sent empty, every missing answer is said beside its question.
  await page.getByRole('button', { name: 'أرسل الطلب' }).click();
  for (const words of ['اكتب اسمك أو اسم الجهة.', 'اختر من أنت.', 'قل لنا ما ستصنع أو تدرس.', 'اختر الواجهة البرمجية أو قاعدة البيانات، أو كلتيهما.',
    'اختر كم تحتاج.', 'قل لنا هل يدرّ عليك مالا.', 'اقبل الشروط لترسل طلبك.', 'وافق على حفظ أجوبتك لترسل طلبك.']) {
    await page.getByText(words, { exact: true }).waitFor();
  }
  await shot(page, '02-request-refused-ar');

  // Sent before the address is proven, the server says so.
  await page.getByLabel('الاسم', { exact: true }).fill(who);
  await page.getByRole('radio', { name: 'جامعة أو مدرسة' }).check();
  await page.getByLabel('صِف عملك').fill('درس عن قانون الشغل في الكلية، يعرض المواد بمصدرها ورابطها.');
  await page.getByText(/^بقي \d+ حرفا$/).waitFor();
  await page.getByRole('checkbox', { name: /^الواجهة البرمجية/ }).check();
  await page.getByRole('checkbox', { name: /^قاعدة البيانات كاملة/ }).check();
  await page.getByRole('radio', { name: /^بضع مئات/ }).check();
  await page.getByRole('radio', { name: 'لا', exact: true }).check();
  await page.getByRole('checkbox', { name: /^قرأت الشروط/ }).check();
  const consent = page.getByRole('checkbox', { name: /^أوافق على/ });
  assert.equal(await consent.isChecked(), false, 'the consent is never ticked for the person');
  await consent.check();
  await page.getByRole('button', { name: 'أرسل الطلب' }).click();
  await page.getByText('أكّد بريد حسابك قبل أن تطلب الوصول.').waitFor();

  // Proven (the letter's code stands in for here), the request goes and stands as sent.
  shell(`from django.utils import timezone\nfrom django.contrib.auth import get_user_model\nget_user_model().objects.filter(username='${username}').update(email_proven_at=timezone.now())`);
  await page.getByRole('button', { name: 'أرسل الطلب' }).click();
  await page.getByText(/^أرسلت طلبك يوم .+، وهو ينتظر جوابنا/).waitFor();
  await shot(page, '03-request-sent-ar');
  // «وصولي» says when it was sent and the day the answer is due, and folds what was sent.
  await page.getByRole('link', { name: 'طلبك في صفحة وصولك' }).click();
  await page.waitForURL('**/data/access');
  await page.locator('.ax-mark', { hasText: 'ينتظر جوابنا' }).waitFor();
  await page.getByText(/^أرسلت طلبك يوم .+، ونجيبك برسالة في أجل أقصاه .+\.$/).waitFor();
  await page.locator('.ax-sent summary', { hasText: 'ما أرسلته يوم' }).click();
  await page.locator('.ax-sent').getByText(who).waitFor();
  await page.locator('.ax-terms-line').getByRole('link', { name: 'الشروط' }).waitFor();
  await matrix('waiting', '/data/access', { session: await ctx.storageState() });

  // The staff asks one line: «أنا» sets it apart, as what needs the person now, and leads to «وصولي», which opens on
  // the question and the box to answer it; the request waits again.
  shell(`${chief}requests.ask(r, by, 'ما اسم الكلية؟')`);
  await page.goto(`${base}/account`);
  await page.locator('.ac-now').getByRole('link', { name: /^وصولي.*سألناك سؤالا/ }).waitFor();
  // The letter's link, /account#access, leads there too.
  await page.goto(`${base}/account#access`);
  await page.waitForURL('**/data/access');
  await page.locator('.ax-mark', { hasText: 'سؤال ينتظر جوابك' }).waitFor();
  const question = page.locator('.ax-now');
  await question.locator('q').getByText('ما اسم الكلية؟').waitFor();
  await matrix('more', '/data/access', { session: await ctx.storageState() });
  await question.getByLabel('جوابك', { exact: true }).fill('كلية الحقوق بالرباط.');
  await question.getByRole('button', { name: 'أرسل الجواب' }).click();
  await page.locator('.ax-mark', { hasText: 'ينتظر جوابنا' }).waitFor();
  assert.equal(await page.locator('.ax-now').count(), 0);

  // Accepted, the API alone: the page says what is held in one line, and opens on «أنشئ مفتاحك».
  shell(`${chief}requests.accept(r, by, api=True, data=False, size='try')`);
  await page.goto(`${base}/`);
  await page.goto(`${base}/account#access`);
  await page.waitForURL('**/data/access');
  await page.locator('.ax-mark', { hasText: 'وصولك قائم' }).waitFor();
  await page.locator('.ax-held').getByText(/^الواجهة البرمجية · حجم «تجربة» · حتى .+ 20\d\d$/).waitFor();
  const first = page.locator('.ax-now', { hasText: 'أنشئ مفتاحك' });
  await first.waitFor();
  assert.equal(await page.getByRole('heading', { name: 'قاعدة البيانات' }).count(), 0, 'no database part for the API alone');
  assert.equal(await page.getByRole('heading', { name: 'الاستعمال' }).count(), 0, 'no use before a key');
  await matrix('first-key', '/data/access', { session: await ctx.storageState() });

  // A key: made with a name, shown once with its copy button and a first call that already holds it.
  await first.getByLabel(/^اسم المفتاح/).fill('الخادم');
  await first.getByRole('button', { name: 'أنشئ مفتاحك' }).click();
  const fresh = page.locator('.ax-fresh');
  const key = (await fresh.locator('code.key').innerText()).trim();
  assert.match(key, /^law_[0-9A-Za-z]{38}$/);
  await fresh.getByText('لن نعرضه مرة أخرى: انسخه الآن واحفظه في خادمك.').waitFor();
  await fresh.getByRole('button', { name: 'نسخ المفتاح' }).waitFor();
  const call = await fresh.locator('.lb-code').innerText();
  assert.ok(call.startsWith('curl ') && call.includes(`X-Api-Key: ${key}`) && call.includes('/api/v1/search'), call);
  await fresh.getByRole('button', { name: 'نسخ الطلب' }).waitFor();
  await shot(page, '04-access-new-key-ar');
  // The key never reaches the query cache: gone with «حفظته», and never in the page again.
  await fresh.getByRole('button', { name: 'حفظته' }).click();
  assert.equal(await page.locator('.ax-fresh').count(), 0);
  assert.ok(!(await page.content()).includes(key), 'the key is never shown again');

  // The key opens the API, on its access's own limits.
  let answer = await ctx.request.get(`${base}/api/v1/bulletin/`, { headers: { 'X-Api-Key': key } });
  assert.equal(answer.status(), 200);
  assert.match(answer.headers()['ratelimit-policy'] ?? '', /"minute";q=30/);

  // Live: the key's row first, «مفتاح ثان» a quiet button, then today against the limits.
  await page.reload();
  const keyRow = page.locator('.ax-key', { hasText: 'الخادم' });
  await keyRow.getByText(`${key.slice(0, 12)}…`).waitFor();
  await keyRow.getByText('آخر استعمال: اليوم').waitFor();
  assert.ok(!(await page.content()).includes(key), 'the key is never shown again');
  await page.getByRole('button', { name: 'مفتاح ثان' }).waitFor();
  assert.equal(await page.locator('.ax-make').count(), 0, 'the form to make a key is closed at rest');
  await page.locator('.ax-meter').getByText('طلبات اليوم').waitFor();
  await page.getByText('طلبات في الدقيقة: 30 على الأكثر').waitFor();
  await page.waitForTimeout(300);
  const keysTop = (await page.getByRole('heading', { name: 'مفاتيحك' }).boundingBox()).y;
  const useTop = (await page.getByRole('heading', { name: 'الاستعمال' }).boundingBox()).y;
  assert.ok(keysTop < useTop, 'the key comes before the use');
  await shot(page, '05-access-live-ar');
  // «أنا» says where the access stands in one row, and so does the header's menu; both lead to /data/access.
  await page.goto(`${base}/account`);
  await page.locator('.ac-body').getByRole('link', { name: /^وصولي.*وصولك قائم حتى/ }).waitFor();
  await page.locator('.ac-trigger').click();
  await page.locator('.ac-menu').getByRole('link', { name: /^وصولي.*وصولك قائم حتى/ }).click();
  await page.waitForURL('**/data/access');
  await page.locator('.ax-mark', { hasText: 'وصولك قائم' }).waitFor();
  // On a desk the API's six reads sit beside the key; a phone has one link to /data instead.
  await page.locator('.ax-side').getByRole('link', { name: '/api/v1/openapi.yaml' }).waitFor();
  assert.equal(await page.locator('.ax-side li').count(), 6);
  assert.ok(!(await page.getByRole('link', { name: 'القراءات الست وعناوينها' }).isVisible()));
  const session = await ctx.storageState();
  await matrix('live', '/data/access', { session });
  await matrix('account', '/account', { session });
  await matrix('settings', '/account/settings', { session });
  await matrix('data', '/data');
  await matrix('terms', '/data/terms');
  {
    const phone = await browser.newContext({ viewport: { width: 390, height: 844 }, storageState: session });
    const p = await phone.newPage();
    watch(p);
    await p.goto(`${base}/data/access`);
    await p.locator('.ax-key').first().waitFor();
    await p.waitForLoadState('networkidle');
    assert.ok(await p.getByRole('link', { name: 'القراءات الست وعناوينها' }).isVisible());
    assert.ok(!(await p.locator('.ax-side').isVisible()));
    const tall = await p.evaluate(() => ({ page: document.documentElement.scrollHeight, main: document.querySelector('main').getBoundingClientRect().height }));
    console.log(`«وصولي» at 390 px, a live holder of the API with one key: ${Math.round(tall.main)} px of page, ${tall.page} px with the site's header and footer`);
    await phone.close();
  }

  // Asking for a change: refused in words when it asks for nothing new or says no reason, then sent; it waits beside
  // the live access, and the way to ask again is gone until it is answered.
  await page.getByRole('button', { name: 'طلب تعديل' }).click();
  const change = page.locator('form.ax-change');
  await change.getByRole('button', { name: 'أرسل طلب التعديل' }).click();
  await change.getByText('قل لنا لماذا تطلب التعديل.').waitFor();
  await change.getByLabel('لماذا', { exact: true }).fill('نبني فهرسا للمواد في مكتبة الكلية.');
  await change.getByRole('button', { name: 'أرسل طلب التعديل' }).click();
  await change.getByText('هذا ما يشمله وصولك الآن: اختر ما تريد أن يتغيّر.').waitFor();
  await change.getByRole('checkbox', { name: /^قاعدة البيانات/ }).check();
  await change.getByRole('radio', { name: /^تطبيق/ }).check();
  await shot(page, '06-access-change-form-ar');
  await change.getByRole('button', { name: 'أرسل طلب التعديل' }).click();
  const changeLine = page.locator('.ax-change-line');
  await changeLine.locator('.ax-mark', { hasText: 'طلب تعديل ينتظر جوابنا' }).waitFor();
  await changeLine.getByText(/الواجهة البرمجية وقاعدة البيانات، بحجم «تطبيق»\. نجيبك في أجل أقصاه .+، ويبقى وصولك كما هو/).waitFor();
  assert.equal(await page.getByRole('button', { name: 'طلب تعديل' }).count(), 0);
  await page.locator('.ax-sent summary', { hasText: 'طلب التعديل، يوم' }).waitFor();
  await matrix('change', '/data/access', { session: await ctx.storageState() });
  // The server refuses a second one while the first is open.
  answer = await ctx.request.post(`${base}/api/access/change/`, {
    headers: { Authorization: `Bearer ${await page.evaluate(() => JSON.parse(localStorage.getItem('law.session') ?? '{}').access ?? '')}` },
    data: { wants_api: true, wants_data: true, why: 'x' },
  });
  assert.equal(answer.status(), 409);
  assert.deepEqual((await answer.json()).errors, [{ field: 'request', code: 'open' }]);

  // The staff asks about it: the question comes first, above the live access's key; answered, it waits again.
  shell(`${chief}requests.ask(r, by, 'لأي جمهور؟')`);
  await page.reload();
  const asked = page.locator('.ax-now', { hasText: 'سألناك عن طلب التعديل:' });
  await asked.locator('q').getByText('لأي جمهور؟').waitFor();
  await page.locator('.ax-mark', { hasText: 'وصولك قائم' }).waitFor();
  assert.ok((await asked.boundingBox()).y < (await page.getByRole('heading', { name: 'مفاتيحك' }).boundingBox()).y);
  await matrix('change-more', '/data/access', { session: await ctx.storageState() });
  await asked.getByLabel('جوابك', { exact: true }).fill('طلبة الحقوق وأساتذتهم.');
  await asked.getByRole('button', { name: 'أرسل الجواب' }).click();
  await changeLine.locator('.ax-mark', { hasText: 'طلب تعديل ينتظر جوابنا' }).waitFor();

  // Accepted: the access changes in place, the same key works on at once with the new limits, and the database's rows
  // appear.
  shell(`${chief}requests.accept(r, by, api=True, data=True, size='app')`);
  await page.reload();
  await page.locator('.ax-held').getByText(/^الواجهة البرمجية وقاعدة البيانات · حجم «تطبيق»/).waitFor();
  assert.equal(await page.locator('.ax-change-line').count(), 0);
  await page.locator('.ax-key', { hasText: 'الخادم' }).waitFor();
  answer = await ctx.request.get(`${base}/api/v1/bulletin/`, { headers: { 'X-Api-Key': key } });
  assert.equal(answer.status(), 200);
  assert.match(answer.headers()['ratelimit-policy'] ?? '', /"minute";q=120/);
  await page.getByText('طلبات في الدقيقة: 120 على الأكثر').waitFor();
  await page.getByRole('button', { name: 'طلب تعديل' }).waitFor();

  // The database: two rows, the rest on demand, the receipt, a file through its ticket.
  const files = page.locator('.ax-part', { has: page.getByRole('heading', { name: 'قاعدة البيانات' }) });
  await files.locator('.ax-part-aside').getByText(/^نسخة .+ · .+B/).waitFor();
  assert.deepEqual(await files.locator(':scope > .ax-rows .ax-file code').allInnerTexts(), ['texts.jsonl.gz', 'akn.zip']);
  await files.getByText('كل الملفات (7)').click();
  assert.equal(await files.locator('.ax-fold .ax-file').count(), 5);
  await files.getByRole('link', { name: 'ما في كل ملف' }).waitFor();
  const [download] = await Promise.all([
    page.waitForEvent('download'),
    files.getByRole('button', { name: 'تحميل texts.jsonl.gz' }).click(),
  ]);
  assert.match(download.suggestedFilename(), /texts\.jsonl\.gz$/);
  await files.getByRole('button', { name: 'الإيصال' }).click();
  await files.locator('.ax-pre').getByText(who).first().waitFor();
  await shot(page, '07-access-changed-ar');

  // A second key, from the quiet button; with two, no third is offered. Then the first one ends, asked inside the page,
  // and opens nothing after.
  await page.getByRole('button', { name: 'مفتاح ثان' }).click();
  await page.locator('.ax-make').getByLabel(/^اسم المفتاح/).fill('الحاسوب');
  await page.locator('.ax-make').getByRole('button', { name: 'أنشئ مفتاحا' }).click();
  await page.locator('.ax-fresh code.key').waitFor();
  await page.getByRole('button', { name: 'حفظته' }).click();
  await page.locator('.ax-key', { hasText: 'الحاسوب' }).waitFor();
  assert.equal(await page.getByRole('button', { name: 'مفتاح ثان' }).count(), 0);
  await page.getByRole('button', { name: 'إنهاء المفتاح «الخادم»' }).click();
  await page.getByText('يتوقف هذا المفتاح الآن، ولا يفتح شيئا بعدها.').waitFor();
  await page.getByRole('button', { name: 'نعم، أنهِ المفتاح' }).click();
  await page.locator('.ax-key', { hasText: 'الخادم' }).waitFor({ state: 'detached' });
  answer = await ctx.request.get(`${base}/api/v1/bulletin/`, { headers: { 'X-Api-Key': key } });
  assert.equal(answer.status(), 401);
  assert.deepEqual((await answer.json()).errors, [{ field: 'key', code: 'ended' }]);

  // Ending the access, asked inside the page: the reason, and the way to ask again.
  await page.getByRole('button', { name: 'إنهاء الوصول' }).click();
  await page.getByRole('button', { name: 'نعم، أنهِ الوصول' }).click();
  await page.locator('.ax-mark', { hasText: 'انتهى وصولك' }).waitFor();
  await page.getByText('السبب: أنهيته بنفسك.').waitFor();
  await page.getByRole('link', { name: 'اطلب من جديد' }).waitFor();
  assert.equal(await page.locator('.ax-key').count(), 0);
  await shot(page, '08-access-ended-ar');
  await matrix('ended', '/data/access', { session: await ctx.storageState() });
  await page.goto(`${base}/data`);
  await page.locator('.ax-door').getByText('انتهى وصولك').waitFor();
  await matrix('request', '/data/request', { session: await ctx.storageState() });

  // Declined: the reason in words and the day one may ask again; no button before it.
  shell(`${chief}
from django.utils import timezone
Request.objects.create(user=r.user, name=r.name, kind=r.kind, purpose=r.purpose, wants_api=True, wants_data=True,
    volume=r.volume, commercial=False, terms=r.terms, state='declined', reason='scope', decided_at=timezone.now())`);
  await page.goto(`${base}/data/access`);
  await page.locator('.ax-mark', { hasText: 'لم نقبل طلبك' }).waitFor();
  await page.getByText(/^السبب: المطلوب أكثر مما يحتاجه الاستعمال الذي وصفته\. يمكنك أن تطلب من جديد ابتداء من .+\.$/).waitFor();
  assert.equal(await page.getByRole('link', { name: 'اطلب من جديد' }).count(), 0);
  await matrix('declined', '/data/access', { session: await ctx.storageState() });
  await ctx.close();

  assert.deepEqual(pageErrors, []);
  console.log('access e2e: ok');
} finally {
  await browser.close();
}
