// The account's letters end to end, in a real browser (3 Nov 2026, as sign-up opened with Resend): a misspelt address
// at sign-up, the code from the letter, a new password, «نسيت كلمة السر» and its link, a dead link, a misspelt address
// at sign-in, a new address.
// Needs both dev servers, Django writing its letters to files:
//   EMAIL_BACKEND=django.core.mail.backends.filebased.EmailBackend EMAIL_FILE_PATH=<dir> python manage.py runserver
//   LETTERS=<dir> npm run e2e:letters      (BASE_URL, default http://localhost:5190; SHOTS=<dir> saves screenshots)
// The addresses sit on gmail.com and hotmail.com because their misspellings are what is tested; run it only with the
// file backend. Their local part holds underscores, which no Gmail address can.
import assert from 'node:assert/strict';
import { randomBytes } from 'node:crypto';
import { readdirSync, readFileSync, statSync } from 'node:fs';
import path from 'node:path';
import { chromium } from 'playwright';

const base = process.env.BASE_URL ?? 'http://localhost:5190';
const letters = process.env.LETTERS;
assert.ok(letters, 'LETTERS=<the folder EMAIL_FILE_PATH names>');
const shots = process.env.SHOTS;
const shot = async (page, name, fullPage = false) => {
  if (shots) await page.screenshot({ path: `${shots}/${name}.png`, fullPage });
};

const stamp = String(Date.now()).slice(-7);
const username = `e2e_letters_${stamp}`;
// Drawn for each run.
const password = `pw-${randomBytes(12).toString('base64url')}`;
const second = `pw-${randomBytes(12).toString('base64url')}`;

/** A letter's plain-text words (Django's file backend writes MIME, the parts in base64). */
function words(mime) {
  const part = mime.match(/Content-Type: text\/plain; charset="utf-8"\nContent-Transfer-Encoding: (\S+)\n\n([\s\S]*?)\n--=/);
  return part[1] === 'base64' ? Buffer.from(part[2].replace(/\s/g, ''), 'base64').toString('utf8') : part[2];
}

/** The words of the newest letter to `to` written after `since` (one file a connection, letters split on its rule). */
async function letterTo(to, since) {
  for (let i = 0; i < 50; i += 1) {
    const found = readdirSync(letters)
      .map((f) => path.join(letters, f))
      .filter((f) => statSync(f).mtimeMs >= since)
      .sort((a, b) => statSync(a).mtimeMs - statSync(b).mtimeMs)
      .flatMap((f) => readFileSync(f, 'utf8').split(/\n-{79}\n/))
      .filter((mime) => mime.includes(`\nTo: ${to}\n`));
    if (found.length) return words(found.at(-1));
    await new Promise((r) => setTimeout(r, 200));
  }
  throw new Error(`no letter to ${to}`);
}
const codeIn = (letter) => letter.match(/\n\n(\d{6})\n\n/)[1];
const linkIn = (letter) => letter.match(/(https?:\/\/\S+\/reset#u=[^\s&]+&t=[^\s<"]+)/)[1];

const browser = await chromium.launch();
const pageErrors = [];
const watch = (page) => page.on('pageerror', (e) => pageErrors.push(String(e)));

try {
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await ctx.newPage();
  watch(page);

  // Sign-up with a misspelt provider: its fix is offered, one tap takes it.
  let since = Date.now();
  await page.goto(`${base}/register`);
  await page.getByLabel('اسم المستخدم', { exact: true }).fill(username);
  await page.getByLabel('البريد الإلكتروني', { exact: true }).fill(`${username}@gamil.com`);
  await page.getByLabel('كلمة السر', { exact: true }).fill(password);
  await page.getByRole('button', { name: 'إنشاء الحساب' }).click();
  await page.getByText('هل تقصد').waitFor();
  await shot(page, '01-register-typo-ar');
  await page.getByRole('button', { name: 'نعم، صحّحه' }).click();
  await page.waitForURL('**/account');

  // The code is already in the inbox: its box is open at once.
  const code = codeIn(await letterTo(`${username}@gmail.com`, since));
  await page.getByLabel('الرمز', { exact: true }).fill(code);
  await shot(page, '02-account-code-ar');
  await page.getByRole('button', { name: 'تأكيد', exact: true }).click();
  await page.locator('#prove').waitFor({ state: 'detached' });
  await page.locator('.ac-head').getByText('البريد مؤكَّد').waitFor();
  // How one signs in is on the second page, «الإعدادات».
  await page.locator('.ac-tabs').getByRole('link', { name: 'الإعدادات' }).click();
  await page.waitForURL('**/account/settings');
  await page.locator('#signin').getByText('(مؤكد)').waitFor();

  // A new password: a wrong current one is said, then it changes and this device stays in.
  await page.locator('#signin summary', { hasText: 'تبديل كلمة السر' }).click();
  const pw = page.locator('#signin details').nth(1);
  await pw.getByLabel('كلمة السر الحالية', { exact: true }).fill('not-my-password');
  await pw.getByLabel('كلمة السر الجديدة', { exact: true }).fill(second);
  await pw.getByRole('button', { name: 'تبديل كلمة السر' }).click();
  await pw.getByText('كلمة السر غير صحيحة.').waitFor();
  await pw.getByLabel('كلمة السر الحالية', { exact: true }).fill(password);
  await pw.getByRole('button', { name: 'تبديل كلمة السر' }).click();
  await pw.getByText('تبدّلت كلمة سرك.').waitFor();
  await shot(page, '03-account-signin-ar', true);
  await page.reload();
  await page.locator('#signin').waitFor();   // still signed in with the fresh pair

  // Signed out, the password forgotten: a link by the username, opened, a weak password refused, then a new one.
  await page.getByRole('button', { name: 'الخروج من هذا الجهاز' }).click();
  await page.waitForURL('**/login');
  await page.getByLabel('اسم المستخدم أو البريد الإلكتروني', { exact: true }).fill(username);
  await page.getByRole('link', { name: 'نسيت كلمة السر؟' }).click();
  await page.waitForURL('**/forgot?login=*');
  since = Date.now();
  await page.getByRole('button', { name: 'أرسل الرابط' }).click();
  await page.getByText('أرسلنا الرابط إلى بريد هذا الحساب').waitFor();
  // Asked by username, the answer names no address: not even its masked domain.
  assert.doesNotMatch(await page.getByRole('status').innerText(), /@/);
  await shot(page, '04-forgot-sent-ar');
  const link = linkIn(await letterTo(`${username}@gmail.com`, since));
  assert.ok(link.startsWith(base), link);

  await page.goto(link);
  await page.getByText(username).waitFor();
  assert.equal(new URL(page.url()).hash, '', 'the token leaves the address bar');
  await page.getByLabel('كلمة السر الجديدة', { exact: true }).fill('12345678');
  await page.getByRole('button', { name: 'حفظ كلمة السر والدخول' }).click();
  await page.getByText('لا يمكن أن تكون أرقاما فقط.').waitFor();
  await shot(page, '05-reset-weak-ar');
  await page.getByLabel('كلمة السر الجديدة', { exact: true }).fill(password);
  await page.getByRole('button', { name: 'حفظ كلمة السر والدخول' }).click();
  await page.getByText('تبدّلت كلمة سرك ودخلت إلى حسابك.').waitFor();
  await page.getByRole('link', { name: 'إلى حسابك' }).click();
  await page.waitForURL('**/account');

  // The same link again: dead, with the way to a new one.
  await page.goto(link);
  await page.getByText('هذا الرابط لم يعد يصلح').waitFor();
  await shot(page, '06-reset-dead-ar');

  // A new address: a misspelt one is offered its fix; the old address is told, the new one gets a code. The letters
  // already sent link to /account#signin, which leads to that part of «الإعدادات».
  await page.goto(`${base}/account#signin`);
  await page.waitForURL('**/account/settings#signin');
  await page.locator('#signin summary', { hasText: 'تبديل البريد' }).click();
  const em = page.locator('#signin details').first();
  since = Date.now();
  await em.getByLabel('البريد الجديد', { exact: true }).fill(`${username}@hotmial.com`);
  await em.getByLabel('كلمة السر الحالية', { exact: true }).fill(password);
  await em.getByRole('button', { name: 'تبديل البريد' }).click();
  await em.getByText('هل تقصد').waitFor();
  await em.getByRole('button', { name: 'نعم، صحّحه' }).click();
  await page.getByText('تبدّل بريدك.').waitFor();
  // The new address waits for its code: the way to it is on «أنا».
  await page.locator('#signin').getByRole('link', { name: 'تأكيد البريد' }).click();
  await page.waitForURL('**/account#prove');
  await page.locator('#prove').waitFor();
  const told = await letterTo(`${username}@gmail.com`, since);
  assert.match(told, new RegExp(`${username}@hotmail\\.com`));
  codeIn(await letterTo(`${username}@hotmail.com`, since));
  await shot(page, '07-account-new-address-ar', true);
  await page.locator('.ac-tabs').getByRole('link', { name: 'الإعدادات' }).click();
  await page.getByRole('button', { name: 'الخروج من هذا الجهاز' }).click();
  await page.waitForURL('**/login');

  // At sign-in, a misspelt address is offered its fix too.
  await page.getByLabel('اسم المستخدم أو البريد الإلكتروني', { exact: true }).fill(`${username}@hotmial.com`);
  await page.getByLabel('كلمة السر', { exact: true }).fill(password);
  await page.getByRole('button', { name: 'دخول' }).last().click();
  await page.getByRole('button', { name: `استعمل ${username}@hotmail.com` }).click();
  await shot(page, '08-login-typo-ar');
  await page.getByRole('button', { name: 'دخول' }).last().click();
  // Back on the page signed out from.
  await page.waitForURL('**/account/settings');
  await ctx.close();

  // On a phone, in French: the forgotten password by an address no account holds, then the dead link.
  const phone = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const p = await phone.newPage();
  watch(p);
  await p.goto(`${base}/login`);
  await p.evaluate(() => localStorage.setItem('law.lang', 'fr'));
  await p.goto(`${base}/forgot`);
  await p.getByRole('button', { name: 'Envoyer le lien' }).waitFor();
  await p.getByLabel("Nom d'utilisateur ou adresse e-mail", { exact: true }).fill('personne@example.org');
  await p.getByRole('button', { name: 'Envoyer le lien' }).click();
  await p.getByText('Aucun compte avec cette adresse').waitFor();
  await shot(p, '09-forgot-none-phone-fr');
  await p.goto(`${base}/reset#u=MQ&t=abc-def`);
  await p.getByText('Ce lien ne fonctionne plus').waitFor();
  await shot(p, '10-reset-dead-phone-fr');
  await phone.close();

  assert.deepEqual(pageErrors, []);
  console.log('letters e2e: ok');
} finally {
  await browser.close();
}
