// The accounts screens end to end, in a real browser.
// Needs both dev servers: back on 8020, web on 5190 (docs/running.md, «The backend» and «The web»).
// SHOTS=<dir> also saves a screenshot of each step.
import assert from 'node:assert/strict';
import { randomBytes } from 'node:crypto';
import { chromium } from 'playwright';

const base = process.env.BASE_URL ?? 'http://localhost:5190';
const shots = process.env.SHOTS;
const shot = async (page, name, fullPage = false) => {
  if (shots) await page.screenshot({ path: `${shots}/${name}.png`, fullPage });
};

const username = `e2e${String(Date.now()).slice(-7)}`;
const email = `${username}@Example.org`;           // capitals, for the case-blind sign-in below
const password = `pw-${randomBytes(12).toString('base64url')}`;   // drawn for each run

const browser = await chromium.launch();
const pageErrors = [];
const watch = (page) => page.on('pageerror', (e) => pageErrors.push(String(e)));

try {
  let ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  let page = await ctx.newPage();
  watch(page);

  // A signed-out visitor is sent to the sign-in page.
  await page.goto(`${base}/account`);
  await page.waitForURL('**/login');
  await shot(page, '1-login-ar');

  // Sign-up: required fields, then the first broken password rule, then success.
  await page.goto(`${base}/register`);
  await page.getByRole('button', { name: 'إنشاء الحساب' }).click();
  await page.getByText('اسم المستخدم مطلوب.').waitFor();
  await page.getByLabel('اسم المستخدم', { exact: true }).fill(username);
  await page.getByLabel('البريد الإلكتروني', { exact: true }).fill(email);
  await page.getByLabel('الاسم الظاهر', { exact: true }).fill('سلمى');
  await page.getByLabel('كلمة السر', { exact: true }).fill('12345678');
  await page.getByRole('button', { name: 'إنشاء الحساب' }).click();
  await page.getByText('لا يمكن أن تكون أرقاما فقط.').waitFor();
  await shot(page, '2-register-weak-ar');
  await page.getByLabel('كلمة السر', { exact: true }).fill(password);
  await page.getByRole('button', { name: 'إنشاء الحساب' }).click();
  await page.waitForURL('**/account');
  await page.getByText(`@${username}`, { exact: true }).waitFor();
  // «أنا»: its tab is the current one; a new account is offered the two things worth doing, and no part says it is empty.
  const tabs = page.locator('.ac-tabs');
  await tabs.locator('a[aria-current="page"]', { hasText: 'أنا' }).waitFor();
  await page.getByRole('link', { name: /^اطرح سؤالك الأول/ }).waitFor();
  await page.getByRole('link', { name: /^تابع قانونا/ }).waitFor();
  await page.waitForLoadState('networkidle');
  for (const empty of ['لا جديد.', 'لم تكتب شيئا بعد.']) assert.equal(await page.getByText(empty).count(), 0, empty);
  // An account that never asked for the data has no «وصولي», on the page or in the header's menu.
  assert.equal(await page.getByRole('link', { name: /^وصولي/ }).count(), 0);
  await page.locator('.ac-trigger').click();
  const menu = page.locator('.ac-menu');
  await menu.getByRole('link', { name: /^الإعدادات/ }).waitFor();
  await page.waitForLoadState('networkidle');
  assert.equal(await menu.getByRole('link', { name: /^وصولي/ }).count(), 0);
  await shot(page, '3-account-ar', true);
  // The menu's «الإعدادات» opens the second page.
  await menu.getByRole('link', { name: /^الإعدادات/ }).click();
  await page.waitForURL('**/account/settings');
  await tabs.locator('a[aria-current="page"]', { hasText: 'الإعدادات' }).waitFor();
  for (const id of ['settings', 'signin', 'apps', 'data', 'leave']) await page.locator(`#${id}`).waitFor();
  await page.getByRole('heading', { name: 'معطياتك الشخصية' }).waitFor();
  await page.getByText('نسخة منها، أو حذف الحساب').waitFor();
  assert.equal(await page.locator('main').getByText('البيانات').count(), 0, 'no «البيانات» on the account');

  // The old addresses lead to the new ones: the settings' parts, the access, the discussion's posts.
  for (const [from, to] of [['/account#apps', '/account/settings#apps'], ['/account#leave', '/account/settings#leave'],
    ['/account#access', '/data/access'], ['/account#discussion', '/account#mine'], ['/account/elsewhere', '/account']]) {
    await page.goto(`${base}${from}`);
    await page.waitForURL((url) => `${url.pathname}${url.hash}` === to);
  }
  await page.goto(`${base}/account#signin`);
  await page.waitForURL('**/account/settings#signin');
  await page.locator('#signin').waitFor();
  await page.waitForTimeout(300);
  const top = (await page.locator('#signin').boundingBox()).y;
  assert.ok(top >= 0 && top < 200, `an old address opens its part (its top at ${top})`);

  // The profile: a new display name and French, which turns the page left to right.
  await page.getByLabel('الاسم الظاهر', { exact: true }).fill('Salma A.');
  await page.getByText('Français', { exact: true }).last().click();
  await page.getByRole('button', { name: 'حفظ' }).click();
  await page.getByText('Enregistré.').waitFor();
  assert.equal(await page.evaluate(() => document.documentElement.dir), 'ltr');
  await shot(page, '4-account-fr', true);

  // Sign out, a wrong password, then the address in capitals signs in.
  await page.getByRole('button', { name: 'Se déconnecter' }).click();
  await page.waitForURL('**/login');
  await page.getByLabel("Nom d'utilisateur ou adresse e-mail", { exact: true }).fill(email.toUpperCase());
  await page.getByLabel('Mot de passe', { exact: true }).fill('wrong-password');
  await page.getByRole('button', { name: 'Se connecter' }).last().click();
  await page.getByText("Nom d'utilisateur ou mot de passe incorrect.").waitFor();
  await page.getByLabel('Mot de passe', { exact: true }).fill(password);
  await page.getByRole('button', { name: 'Se connecter' }).last().click();
  // Back on the page signed out from.
  await page.waitForURL('**/account/settings');
  await page.locator('.ac-tabs a[aria-current="page"]', { hasText: 'Réglages' }).waitFor();

  // A session the server refuses signs the page out once and says so.
  await page.evaluate(() => localStorage.setItem('law.session', JSON.stringify({ access: 'x', refresh: 'x' })));
  await page.reload();
  await page.waitForURL('**/login');
  assert.match(await page.getByRole('status').first().innerText(), /session/);
  await shot(page, '5-session-ended-fr');
  await ctx.close();

  // Signed out, an old address of the access leads to its page, and signing in comes back to it.
  ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  page = await ctx.newPage();
  watch(page);
  await page.goto(`${base}/account#access`);
  await page.waitForURL('**/login');
  await page.getByLabel('اسم المستخدم أو البريد الإلكتروني', { exact: true }).fill(username);
  await page.getByLabel('كلمة السر', { exact: true }).fill(password);
  await page.getByRole('button', { name: 'دخول', exact: true }).last().click();
  await page.waitForURL('**/data/access');
  await ctx.close();

  // On a 360 × 640 phone the first useful row of «أنا» is on the first screen, and nothing is wider than the phone.
  ctx = await browser.newContext({ viewport: { width: 360, height: 640 } });
  page = await ctx.newPage();
  watch(page);
  await page.goto(`${base}/login`);
  await page.getByLabel('اسم المستخدم أو البريد الإلكتروني', { exact: true }).fill(username);
  await page.getByLabel('كلمة السر', { exact: true }).fill(password);
  await page.getByRole('button', { name: 'دخول', exact: true }).last().click();
  await page.waitForURL('**/account');
  const first = page.locator('.ac-body > * > *').first();
  await first.waitFor();
  const row = await first.boundingBox();
  assert.ok(row.y + 44 <= 640, `the first row of «أنا» starts at ${row.y} px`);
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth) <= 360);
  await shot(page, '6-account-phone-ar', true);
  await ctx.close();

  // «Email in use» leads into the existing account, never to a second one.
  ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
  page = await ctx.newPage();
  watch(page);
  await page.goto(`${base}/register`);
  await page.getByLabel('اسم المستخدم', { exact: true }).fill(`${username}b`);
  await page.getByLabel('البريد الإلكتروني', { exact: true }).fill(email.toLowerCase());
  await page.getByLabel('كلمة السر', { exact: true }).fill(password);
  await page.getByRole('button', { name: 'إنشاء الحساب' }).click();
  await page.getByRole('link', { name: 'الدخول بهذا البريد' }).click();
  await page.waitForURL('**/login?login=*');
  assert.equal(await page.getByLabel('اسم المستخدم أو البريد الإلكتروني', { exact: true }).inputValue(),
    email.toLowerCase());
  await shot(page, '7-login-prefilled-phone-ar', true);
  await ctx.close();

  assert.deepEqual(pageErrors, []);
  console.log('accounts e2e: ok');
} finally {
  await browser.close();
}
