// What a device kept under the project's first name is carried to today's names (shared/services/savedMove.ts and
// oldKeys.ts): the saved articles and families, in a real browser's IndexedDB. Needs no server: the
// page is answered here. Usage: node e2e/saved-move.e2e.mjs
import { chromium } from 'playwright';
import ts from 'typescript';
import { readFileSync } from 'node:fs';

// The two modules as the browser gets them: their types taken off, their exports hung on the window.
const plain = (file) => ts.transpileModule(readFileSync(new URL(`../src/shared/services/${file}`, import.meta.url), 'utf8'),
  { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } }).outputText.replace(/^export /gm, '');
const html = `<!doctype html><meta charset="utf-8"><script>(() => { ${plain('savedMove.ts')}\n${plain('oldKeys.ts')}\nwindow.Move = { moveSaved, moveOldKeys }; })();</script>`;
const ORIGIN = 'https://site.test';

const inPage = async (page, fn) => page.evaluate(fn);
const helpers = () => {
  const settled = (req) => new Promise((res, rej) => { req.onsuccess = () => res(req.result); req.onerror = () => rej(req.error); });
  window.openAs = (name) => new Promise((res, rej) => {
    const req = indexedDB.open(name, 2);
    req.onupgradeneeded = () => {
      req.result.createObjectStore('saved', { keyPath: 'path' });
      req.result.createObjectStore('families', { keyPath: 'code' });
    };
    req.onsuccess = () => res(req.result); req.onerror = () => rej(req.error);
  });
  window.put = async (name, store, row) => { const db = await window.openAs(name); await settled(db.transaction(store, 'readwrite').objectStore(store).put(row)); db.close(); };
  window.all = async (name, store) => { const db = await window.openAs(name); const rows = await settled(db.transaction(store).objectStore(store).getAll()); db.close(); return rows; };
  window.names = async () => (await indexedDB.databases()).map((d) => d.name).sort();
};

const browser = await chromium.launch();
const problems = [];
const check = (ok, what) => { if (!ok) problems.push(what); };

async function fresh() {
  const context = await browser.newContext();
  const page = await context.newPage();
  await page.route(`${ORIGIN}/**`, (route) => route.fulfill({ contentType: 'text/html', body: html }));
  await page.goto(`${ORIGIN}/`);
  await inPage(page, helpers);
  return page;
}

// 1. A device that kept two articles and a family before the rename, and one article (the same address) since.
{
  const page = await fresh();
  const got = await inPage(page, async () => {
    await window.put('matn', 'saved', { path: '/ma/loi/70-03/art_49', label: 'old 49', savedAt: '2026-10-01' });
    await window.put('matn', 'saved', { path: '/ma/loi/70-03/art_84', label: 'old 84', savedAt: '2026-10-02' });
    await window.put('matn', 'families', { code: 'abc', name: 'ours', savedAt: '2026-11-14' });
    await window.put('law', 'saved', { path: '/ma/loi/70-03/art_84', label: 'new 84', savedAt: '2026-11-15' });
    await window.Move.moveSaved(() => window.openAs('law'));
    await new Promise((r) => setTimeout(r, 300));
    const first = { saved: await window.all('law', 'saved'), families: await window.all('law', 'families'), names: await window.names(), done: localStorage.getItem('law.saved.moved') };
    await window.Move.moveSaved(() => { throw new Error('asked twice'); });   // the second time it does nothing
    return first;
  });
  check(got.saved.length === 2, `articles: ${JSON.stringify(got.saved)}`);
  check(got.saved.find((r) => r.path.endsWith('art_49'))?.label === 'old 49', 'the old article was not carried');
  check(got.saved.find((r) => r.path.endsWith('art_84'))?.label === 'new 84', 'the newer copy did not win');
  check(got.families.length === 1 && got.families[0].code === 'abc', 'the family was not carried');
  check(!got.names.includes('matn'), `the old database is still there: ${got.names}`);
  check(got.done === '1', 'not marked as done');
  await page.context().close();
}

// 2. A device that never had the old database: nothing appears, nothing is left behind.
{
  const page = await fresh();
  const got = await inPage(page, async () => {
    await window.Move.moveSaved(() => window.openAs('law'));
    await new Promise((r) => setTimeout(r, 300));
    return { saved: await window.all('law', 'saved'), names: await window.names(), done: localStorage.getItem('law.saved.moved') };
  });
  check(got.saved.length === 0 && !got.names.includes('matn') && got.done === '1', `a new device: ${JSON.stringify(got)}`);
  await page.context().close();
}

// 3. The keys in localStorage (shared/services/oldKeys.ts, called first thing in main.tsx).
{
  const page = await fresh();
  const got = await inPage(page, () => {
    localStorage.setItem('matn.follows', '["/ma/loi/70-03"]');
    localStorage.setItem('matn.road.practice.signs', '{"seen":3}');
    localStorage.setItem('matn.road.numbers', 'old');
    localStorage.setItem('law.road.numbers', 'new');
    localStorage.setItem('law.session', 'kept');
    window.Move.moveOldKeys();
    return Object.fromEntries(Object.keys(localStorage).sort().map((k) => [k, localStorage.getItem(k)]));
  });
  const want = { 'law.follows': '["/ma/loi/70-03"]', 'law.road.numbers': 'new', 'law.road.practice.signs': '{"seen":3}', 'law.session': 'kept' };
  check(JSON.stringify(got) === JSON.stringify(want), `keys: ${JSON.stringify(got)}`);
  await page.context().close();
}

await browser.close();
console.log(problems.length ? `PROBLEMS:\n${problems.join('\n')}` : 'saved-move: no problem found');
process.exit(problems.length ? 1 : 0);
