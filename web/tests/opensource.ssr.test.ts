import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createElement } from 'react';
import { renderToString } from 'react-dom/server';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { StaticRouter } from 'react-router-dom/server.js';

// /open-source drawn on the server, in Node, with no browser: the deploy draws its head from it (scripts/prerender.mjs),
// so it must render without window, localStorage or matchMedia, and ask no word while drawing. The page's modules are
// read through Vite (its alias, its JSX, its JSON and CSS imports); React, the router and the query cache are the
// test's own, shared with them.
const root = fileURLToPath(new URL('..', import.meta.url));

test('the page renders on the server, its figures «…» until they come, then set in its sentences', async () => {
  assert.equal(typeof (globalThis as { window?: unknown }).window, 'undefined');
  const { createServer } = await import('vite');
  const react = (await import('@vitejs/plugin-react-swc')).default;
  const cacheDir = mkdtempSync(join(tmpdir(), 'open-ssr-'));
  const server = await createServer({
    configFile: false, root, cacheDir, logLevel: 'silent', appType: 'custom', plugins: [react()],
    resolve: { alias: { '@': join(root, 'src') } },
    server: { middlewareMode: true, hmr: false, watch: null },
    optimizeDeps: { noDiscovery: true, include: [] },
  });
  try {
    const page = (await server.ssrLoadModule('/src/features/opensource/OpenSourcePage.tsx')).default;
    const { applyLanguage } = await server.ssrLoadModule('/src/shared/locales/i18n.ts');
    const { drawn } = await server.ssrLoadModule('/src/shared/services/title.ts');

    // Anything that reads the device while drawing is caught, even inside a try.
    const read: string[] = [];
    const trap = (name: string) => Object.defineProperty(globalThis, name, {
      configurable: true, get() { read.push(name); throw new ReferenceError(`${name} read while drawing`); },
    });
    const draw = (seed: [unknown[], unknown][] = []) => {
      const client = new QueryClient({ defaultOptions: { queries: { staleTime: Infinity, retry: false } } });
      for (const [key, data] of seed) client.setQueryData(key, data);
      trap('localStorage');
      trap('matchMedia');
      try {
        return renderToString(createElement(QueryClientProvider, { client },
          createElement(StaticRouter, { location: '/open-source' }, createElement(page))));
      } finally {
        delete (globalThis as Record<string, unknown>).localStorage;
        delete (globalThis as Record<string, unknown>).matchMedia;
      }
    };

    const empty = draw();
    assert.deepEqual(read, [], 'nothing is read from the device');
    assert.match(empty, /<h1[^>]*>قانون المغرب، كلمة كلمة<\/h1>/);
    assert.equal(drawn.title, 'قانون المغرب، كلمة كلمة — قانون', 'the page names itself for the head');
    assert.match(empty, /id="word"/);
    assert.match(empty, /aria-busy="true"/, 'the sheet waits for its word: none is asked while drawing');
    assert.match(empty, /<b class="os-n">…<\/b> عددا/, 'a figure not yet come is «…»');
    assert.match(empty, /قريبا/, 'no repository yet: the code is «soon»');
    assert.doesNotMatch(empty, /blob\/main/, 'and no address of a repository is written');
    assert.doesNotMatch(empty, /mailto:/);

    const full = draw([
      [['about'], { texts: 192710, articles: 1838000, issues: 7829, pages: 412000, corrections: 4761, contact: 'contact@example.org',
                    source: 'https://example.org/law' }],
      [['quality', 'words'], { words: 30401, ready: 1200, settled: 12000, answers: 36500, today: 12 }],
    ]);
    assert.deepEqual(read, []);
    assert.match(full, /<b class="os-n">7\.829<\/b> عددا/);
    assert.match(full, /<b class="os-n">30\.401<\/b> كلمة/);
    assert.match(full, /39٪/, 'the share, its sign on the right');
    // The task as a field: a square for every hundred words (30,401 → 305), filled for the 12,000 settled.
    assert.equal((full.match(/<i(?: data-on="")?><\/i>/g) ?? []).length, 305);
    assert.equal((full.match(/<i data-on=""><\/i>/g) ?? []).length, 120);
    // The project by its addresses: the repository's, written out, and the agreement said to be a draft.
    assert.match(full, /href="https:\/\/example\.org\/law\/blob\/main\/CONTRIBUTING\.md"/);
    assert.match(full, /href="https:\/\/example\.org\/law\/issues\/new\/choose"/);
    assert.match(full, /example\.org(?:<!-- -->)?\/(?:<!-- -->)?<wbr\/?>(?:<!-- -->)?law/, 'an address is written without its scheme, and breaks after a slash');
    assert.match(full, /مسودة/);
    assert.match(full, /href="https:\/\/example\.org\/law"/);
    assert.match(full, /href="mailto:contact@example\.org"/);
    assert.match(full, /href="\/ma\/loi\/65-99\/art_563"/);

    await applyLanguage('fr');
    const fr = draw();
    assert.deepEqual(read, []);
    assert.match(fr, /<h1[^>]*>Le droit marocain, un mot à la fois<\/h1>/);
    assert.match(fr, /Les mots à trancher sont en arabe/);
    assert.match(fr, /lang="ar" dir="rtl"/, 'the law\'s words stay Arabic, right to left');
    await applyLanguage('ar');
  } finally {
    await server.close();
    rmSync(cacheDir, { recursive: true, force: true });
  }
});
