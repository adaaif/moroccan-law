import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

// The account's two addresses (src/features/accounts/moved.ts): an old link to a section leads to where it is now, and
// the words of the two pages and of «وصولي» are said in both languages.
const { movedTo, tabOf, SETTINGS_PARTS } = await import('../src/features/accounts/moved.ts');

const json = (path: string) => JSON.parse(readFileSync(new URL(path, import.meta.url), 'utf8'));
const talk = { ar: json('../src/features/discussion/locales/ar.json'), fr: json('../src/features/discussion/locales/fr.json') };
const pages = { ar: json('../src/shared/locales/pages.ar.json'), fr: json('../src/shared/locales/pages.fr.json') };

test('the settings\' sections, the access and the old name of one\'s posts lead to their new address', () => {
  for (const part of ['settings', 'signin', 'apps', 'data', 'leave']) {
    assert.equal(movedTo('/account', `#${part}`), `/account/settings#${part}`, part);
  }
  // The letters already sent about a request link here.
  assert.equal(movedTo('/account', '#access'), '/data/access');
  assert.equal(movedTo('/account/', '#access'), '/data/access');
  assert.equal(movedTo('/account', '#discussion'), '/account#mine');
  assert.deepEqual(SETTINGS_PARTS, ['settings', 'signin', 'apps', 'data', 'leave']);
});

test('the person\'s own sections stay on /account, and the two pages are right as they are', () => {
  for (const part of ['', '#prove', '#pause', '#notices', '#mine', '#following', '#reports']) {
    assert.equal(movedTo('/account', part), null, part);
  }
  assert.equal(movedTo('/account/settings', ''), null);
  assert.equal(movedTo('/account/settings/', '#apps'), null);
  // An address under /account the site does not know goes to «أنا».
  assert.equal(movedTo('/account/access', ''), '/account');
  assert.equal(movedTo('/account/settings/more', ''), '/account');
});

test('an address says which page it shows', () => {
  assert.equal(tabOf('/account'), 'me');
  assert.equal(tabOf('/account/'), 'me');
  assert.equal(tabOf('/account/settings'), 'settings');
  assert.equal(tabOf('/account/settings/'), 'settings');
});

test('the two pages and «وصولي» are named in both languages, and the personal data is not «البيانات»', () => {
  for (const lang of ['ar', 'fr'] as const) {
    const me2 = talk[lang].me2;
    for (const key of ['tabMe', 'pagesLabel', 'settings', 'settingsTitle', 'stepsTitle', 'stepAsk', 'stepAskLead', 'stepFollow',
      'stepFollowLead', 'access']) {
      assert.ok(me2[key], `${lang} me2.${key}`);
    }
    for (const state of ['waiting', 'more', 'declined', 'again', 'live', 'ended']) {
      assert.ok(me2.accessStates[state], `${lang} me2.accessStates.${state}`);
    }
    // A date is said where the state has one.
    for (const state of ['waiting', 'declined', 'live']) assert.match(me2.accessStates[state], /\{\{date\}\}/, `${lang} ${state}`);
    assert.ok(talk[lang].account.dataTitle && talk[lang].account.dataLead, `${lang} account.dataTitle`);
    assert.ok(pages[lang].account.me && pages[lang].account.settings, `${lang} pages:account`);
  }
  assert.equal(talk.ar.me2.tabMe, 'أنا');
  assert.equal(talk.ar.me2.settings, 'الإعدادات');
  assert.equal(talk.ar.me2.access, 'وصولي');
  assert.equal(talk.ar.account.dataTitle, 'معطياتك الشخصية');
  assert.equal(talk.ar.account.dataLead, 'نسخة منها، أو حذف الحساب');
  assert.equal(talk.fr.account.dataTitle, 'Vos données personnelles');
  const words = JSON.stringify([talk.ar.me2, talk.ar.account, pages.ar.account]);
  assert.ok(!words.includes('البيانات'), 'no «البيانات» in the account\'s words');
});
