import { test } from 'node:test';
import assert from 'node:assert/strict';
import { endpointOf, frameAt, hostOf, kindOf } from '../src/shared/analytics/paths.ts';

// The analytics review (15 Nov 2026): what a measure reads of an address, a referrer, an API path and a stack.

test('each address is the kind of page the registry names for it', () => {
  const kinds: [string, string][] = [
    ['/', 'home'],
    ['/ma/loi/65-99', 'law'], ['/ma/code/doc', 'law'], ['/ma/loi/65-99/annex', 'law'], ['/constitution', 'law'],
    ['/constitution/2011', 'law'], ['/texts/123', 'law'],
    ['/ma/loi/65-99/art_53', 'article'], ['/ma/dahir/1-11-91/art_1/', 'article'],
    ['/bo/general_ar/7278', 'issue'], ['/bo/general_ar/7278/quality', 'issue'], ['/pages/12/3', 'issue'],
    ['/library', 'library'], ['/codes', 'library'], ['/bo', 'library'], ['/new', 'library'], ['/places', 'library'],
    ['/places/casablanca', 'library'], ['/words', 'library'], ['/words/nafaqa', 'library'],
    ['/budget', 'budget'], ['/budget/2027', 'budget'],
    ['/search', 'search'],
    ['/topics', 'topic'], ['/topics/family', 'topic'], ['/topics/family/pages/papers', 'topic'],
    ['/topics/family/checklists/marriage', 'topic'], ['/topics/family/reform', 'topic'], ['/topics/family/reform/age', 'topic'],
    ['/topics/tax/changes', 'topic'], ['/situations', 'topic'], ['/situations/fired', 'topic'],
    ['/topics/work/journeys/fired', 'journey'],
    ['/topics/tax/tools/salary', 'tool'], ['/topics/family/tools/inheritance/zawja-ibn-bint', 'tool'],
    ['/blog', 'blog'], ['/blog/whatsapp', 'post'],
    ['/discussion/ma/loi/65-99/art_53', 'talk'], ['/talk', 'talk'], ['/talk/family/12', 'talk'], ['/questions', 'talk'],
    ['/people/someone', 'talk'], ['/explain/ma/loi/65-99/art_53', 'talk'],
    ['/me', 'account'], ['/me/following', 'account'], ['/saved', 'account'], ['/account', 'account'], ['/account/settings', 'account'], ['/login', 'account'],
    ['/register', 'account'], ['/forgot', 'account'], ['/reset', 'account'], ['/connect', 'account'],
    ['/auth/google', 'account'], ['/letters/stop', 'account'], ['/review', 'account'], ['/topics/road/review', 'account'],
    ['/about', 'page'], ['/data', 'page'], ['/rules', 'page'], ['/privacy', 'page'], ['/corrections', 'page'],
    ['/check', 'page'], ['/ai', 'page'],
    ['/embed/ma/loi/65-99/art_53', 'embed'],
    ['/.env', 'other'], ['/wp-login.php', 'other'], ['/bo/general_ar', 'other'], ['/topics/family/nothing/here', 'other'],
    ['/embed', 'other'], ['/ma', 'other'],
  ];
  for (const [path, kind] of kinds) assert.equal(kindOf(path), kind, path);
});

test('an API path is cut to its endpoint: its first two segments, never what was asked', () => {
  assert.equal(endpointOf('/corpus/at/ma/loi/65-99?window=30'), '/corpus/at');
  assert.equal(endpointOf('/api/corpus/at/ma/loi/65-99/art_53/'), '/corpus/at');
  assert.equal(endpointOf('/search/?q=%D8%B7%D9%84%D8%A7%D9%82'), '/search');
  assert.equal(endpointOf('/auth/token/refresh/'), '/auth/token');
  assert.equal(endpointOf('/discussion/people/Someone/'), '/discussion/people');
  assert.equal(endpointOf('/Topics/Family/'), '/topics/family');
  assert.equal(endpointOf('/words/%D9%86%D9%81%D9%82%D8%A9/'), undefined);
  assert.equal(endpointOf('/'), undefined);
  assert.equal(endpointOf(`/${'a'.repeat(70)}/`), undefined);
});

test('a referrer gives its host alone, lowercased; a phone app its package', () => {
  assert.equal(hostOf('https://WWW.Google.co.ma/search?q=x'), 'www.google.co.ma');
  assert.equal(hostOf('android-app://com.whatsapp/'), 'com.whatsapp');
  assert.equal(hostOf(''), '');
  assert.equal(hostOf('not a url'), '');
});

test('an error is placed by the first frame in one of the site\'s built files, without its message', () => {
  const origin = 'https://3adala.com';
  const chrome = [
    // Chrome writes the message as the stack's first line: a place in it is never read.
    'TypeError: failed at https://3adala.com/assets/message-Xx.js:1:1',
    '    at https://cdn.example.org/lib.js:10:20',
    '    at render (https://3adala.com/assets/TextPage-Ab12Cd3.js:3:4567)',
    '    at https://3adala.com/assets/index-B8bJsMU.js:12:345',
  ].join('\n');
  assert.equal(frameAt(chrome, origin), 'assets/TextPage-Ab12Cd3.js:3:4567');
  assert.equal(frameAt('@https://3adala.com/assets/index-B8bJsMU.js:12:345', origin), 'assets/index-B8bJsMU.js:12:345',
    'an error event\'s own file and place');
  const firefox = 'render@https://3adala.com/assets/TextPage-Ab12Cd3.js?v=2:3:4567\n@https://3adala.com/assets/index.js:1:2';
  assert.equal(frameAt(firefox, origin), 'assets/TextPage-Ab12Cd3.js:3:4567');
  assert.equal(frameAt('at https://127.0.0.1:4173/assets/engine-Xy.js:1:99', 'http://127.0.0.1:4173'), undefined);
  assert.equal(frameAt('at http://127.0.0.1:4173/assets/engine-Xy.js:1:99', 'http://127.0.0.1:4173'), 'assets/engine-Xy.js:1:99');
  assert.equal(frameAt('at https://3adala.com/:12:3', origin), undefined, 'the page itself is no built file');
  assert.equal(frameAt('at https://other.example/assets/x.js:1:2', origin), undefined);
  assert.equal(frameAt(undefined, origin), undefined);
  assert.equal(frameAt(`at https://3adala.com/assets/${'x'.repeat(80)}.js:1:2`, origin), undefined, 'too long for the rule');
});
