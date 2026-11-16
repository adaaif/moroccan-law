// The discussion in the topics end to end (the choices of 29 Oct 2026), in a real browser: the hub, a topic, a
// post, an article's page, writing with the consent, a post the check returns and one it holds, a moderator's desk,
// staff choosing a topic's moderators, karma on a person's page, the rules and the privacy page, a phone and French.
// Needs both dev servers with the demo seeded (manage.py seed_demo_talk) and the check's stand-in on
// (DISCUSSION_CHECK=markers), and the account demo-tester (proven, no consent yet). BASE_URL (default 5190), SHOTS=<dir>.
// DEMO_PASSWORD: the demo accounts' password, the one seed_demo_talk was given or printed.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { chromium } from 'playwright';

const base = process.env.BASE_URL ?? 'http://localhost:5190';
const shots = process.env.SHOTS;
const PASSWORD = process.env.DEMO_PASSWORD;
if (!PASSWORD) {
  console.error('talk e2e: set DEMO_PASSWORD to the password seed_demo_talk printed.');
  process.exit(1);
}
const words = JSON.parse(readFileSync(new URL('../src/features/discussion/locales/ar.json', import.meta.url), 'utf8'));
const t = (key) => key.split('.').reduce((o, k) => o[k], words);

const browser = await chromium.launch();
const pageErrors = [];
const shot = async (page, name, fullPage = false) => {
  if (shots) await page.screenshot({ path: `${shots}/${name}.png`, fullPage });
};

async function open(viewport = { width: 1280, height: 900 }, who = null, lang = 'ar') {
  const ctx = await browser.newContext({ viewport, locale: lang === 'fr' ? 'fr-MA' : 'ar-MA' });
  const page = await ctx.newPage();
  page.on('pageerror', (e) => pageErrors.push(String(e)));
  await page.goto(`${base}/`);
  const session = who ? await (await fetch(`${base}/api/auth/token/`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ username: who, password: PASSWORD }),
  })).json() : null;
  await page.evaluate(([s, l]) => {
    if (s) localStorage.setItem('law.session', JSON.stringify({ access: s.access, refresh: s.refresh }));
    localStorage.setItem('law.lang', l);
  }, [session, lang]);
  return { ctx, page };
}

const postId = (url) => Number(url.match(/\/talk\/[^/]+\/(\d+)/)[1]);

try {
  // A reader: the hub, a topic, its unanswered questions, a post, an article's page.
  let { ctx, page } = await open();
  await page.goto(`${base}/talk`);
  await page.getByRole('heading', { name: t('talk.title'), level: 1 }).waitFor();
  await page.getByRole('link', { name: 'الأسرة' }).first().waitFor();
  await shot(page, '01-hub', true);

  await page.goto(`${base}/talk/family`);
  await page.getByRole('heading', { name: 'الأسرة', level: 1 }).waitFor();
  assert.ok(await page.getByText(t('talk2.moderators')).isVisible());
  await shot(page, '02-topic');
  await page.getByRole('tab', { name: new RegExp(t('talk2.sorts.open')) }).click();
  await page.locator('article h3 a').first().waitFor();
  await shot(page, '03-topic-unanswered');
  await page.getByRole('tab', { name: t('talk2.sorts.active') }).click();
  await page.locator('article h3 a').first().click();
  await page.waitForURL(/\/talk\/family\/\d+$/);
  await page.locator('.tk-crumb').getByRole('link', { name: 'الأسرة' }).waitFor();
  await shot(page, '04-post', true);

  await page.goto(`${base}/discussion/ma/loi/70-03/art_49`);
  await page.getByRole('heading', { name: t('talk2.citedTitle') }).waitFor();
  assert.ok(await page.locator('article h3 a').count() > 3);
  await shot(page, '05-article', true);
  await ctx.close();

  // A writer's first post: the consent, a post the check returns, sent as it is, and a clean one.
  ({ ctx, page } = await open(undefined, 'demo-tester'));
  await page.goto(`${base}/talk/housing`);
  await page.getByRole('button', { name: t('composer.start') }).click();
  await page.getByText(t('check.consent')).waitFor();
  await page.getByPlaceholder(t('talk2.titleQuestion')).fill('جاري ما خلصش الكرا');
  await page.getByPlaceholder(t('composer.placeholder')).fill('جاري أحمد بنعلي فالطابق الثاني ما خلصش الكرا هادي ستة شهور [return:privacy]');
  await shot(page, '06-composer-consent');
  assert.ok(await page.getByRole('button', { name: t('composer.send') }).isDisabled());
  await page.getByText(t('check.consent')).click();
  await page.getByRole('button', { name: t('composer.send') }).click();
  await page.getByRole('button', { name: t('check.insist') }).scrollIntoViewIfNeeded();
  await shot(page, '07-returned');
  await page.getByRole('button', { name: t('check.insist') }).click();
  await page.waitForURL(/\/talk\/housing\/\d+$/);
  const held = postId(page.url());
  await page.getByText(t('held').split('.')[0]).first().waitFor();
  await shot(page, '08-held');

  await page.goto(`${base}/talk/housing`);
  await page.getByRole('button', { name: t('composer.start') }).click();
  await page.getByPlaceholder(t('talk2.titleQuestion')).fill('واش مول الدار يقدر يرفض يرجع الضمانة؟');
  await page.getByPlaceholder(t('composer.placeholder')).fill('خرجت من الشقة ونقيتها، ومول الدار بغا يخلي الضمانة كاملة. شنو كيقول القانون 67.12؟');
  await page.getByRole('button', { name: t('composer.send') }).click();
  await page.waitForURL(/\/talk\/housing\/\d+$/);
  const clean = postId(page.url());
  await page.getByRole('heading', { name: 'واش مول الدار يقدر يرفض يرجع الضمانة؟', level: 1 }).waitFor();
  await shot(page, '09-published');
  await ctx.close();

  // Someone else comments under it.
  ({ ctx, page } = await open(undefined, 'demo-karim'));
  await page.goto(`${base}/talk/housing/${clean}`);
  await page.getByRole('button', { name: t('composer.startReply') }).last().click();
  await page.getByPlaceholder(t('talk2.commentPlaceholder')).fill('الضمانة كترجع ملي كتسلم المفاتيح، من غير إلا كان شي ضرر مثبت فمحضر المعاينة.');
  await page.getByRole('button', { name: t('composer.send') }).click();
  await page.locator('article', { hasText: 'الضمانة كترجع ملي كتسلم المفاتيح' }).last().waitFor();
  await shot(page, '10-commented', true);
  await ctx.close();

  // A phone.
  ({ ctx, page } = await open({ width: 390, height: 844 }));
  await page.goto(`${base}/talk/family`);
  await page.getByRole('heading', { name: 'الأسرة', level: 1 }).waitFor();
  await shot(page, '11-phone-topic');
  await page.goto(`${base}/talk/housing/${clean}`);
  await page.getByText('الضمانة كترجع ملي كتسلم المفاتيح').waitFor();
  await shot(page, '12-phone-post', true);
  await ctx.close();

  // The housing topic's moderator finds the held post with its rule, and publishes it.
  ({ ctx, page } = await open(undefined, 'demo-khadija'));
  await page.goto(`${base}/review`);
  await page.getByText('جاري ما خلصش الكرا').first().waitFor();
  await shot(page, '13-review');
  const approve = await fetch(`${base}/api/discussion/review/contributions/${held}/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json',
               Authorization: `Bearer ${(await page.evaluate(() => JSON.parse(localStorage.getItem('law.session')))).access}` },
    body: JSON.stringify({ act: 'approve' }),
  });
  assert.equal(approve.status, 200);
  assert.equal((await fetch(`${base}/api/discussion/posts/${held}/`)).status, 200);
  await ctx.close();

  // Staff choose the housing topic's moderators from the people it found useful.
  ({ ctx, page } = await open(undefined, 'demo-staff'));
  await page.goto(`${base}/review`);
  await page.getByRole('tab', { name: t('review.tabs.reviewers') }).click();
  await page.getByRole('combobox', { name: t('review.candidatesPlace') }).selectOption('/talk/family');
  await page.getByRole('button', { name: t('review.appointHere') }).first().waitFor();
  await shot(page, '14-moderators', true);
  await ctx.close();

  // A reader again: the topic's page, a person, the rules, the privacy page, French.
  ({ ctx, page } = await open());
  await page.goto(`${base}/topics/family`);
  // The family's page keeps its conversation among the tabs of «القانون كامل».
  await page.getByRole('tab', { name: 'النقاش' }).click();
  await page.getByRole('link', { name: 'ادخل لنقاش هاد الموضوع' }).scrollIntoViewIfNeeded();
  await shot(page, '15-topic-page');
  await page.goto(`${base}/people/demo-hamid`);
  await page.getByText(t('me2.moderates')).locator('..').getByRole('link', { name: 'الأسرة' }).waitFor();
  await shot(page, '16-person');
  await page.goto(`${base}/rules`);
  await page.getByRole('heading', { name: t('rulesPage.checkTitle') }).waitFor();
  await shot(page, '17-rules', true);
  await page.goto(`${base}/privacy`);
  await page.getByRole('heading', { name: t('privacyPage.checkTitle') }).waitFor();
  await shot(page, '18-privacy', true);
  await ctx.close();

  ({ ctx, page } = await open(undefined, null, 'fr'));
  await page.goto(`${base}/talk/family`);
  await page.getByRole('heading', { name: 'Famille', level: 1 }).waitFor();
  await shot(page, '19-topic-fr');
  await ctx.close();

  assert.deepEqual(pageErrors, []);
  console.log('talk e2e: ok');
} finally {
  await browser.close();
}
