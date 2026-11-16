// The phone budget (row 17 of the reader-experience review): what a first visit downloads before the page is read, gzip
// sizes from dist/ after `npm run build`. Over budget fails. The budgets leave a little room above today's sizes;
// a change that needs more says why in its commit.
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { gzipSync } from 'node:zlib';
import path from 'node:path';

const DIST = path.resolve(import.meta.dirname, '../dist');
const html = readFileSync(path.join(DIST, 'index.html'), 'utf8');
const gz = (file) => gzipSync(readFileSync(path.join(DIST, file))).length;
const kb = (n) => `${(n / 1024).toFixed(1)} KB`;

const entry = [...html.matchAll(/<script[^>]+src="\/([^"]+\.js)"/g)].map((m) => m[1]);
const preloadJs = [...html.matchAll(/<link rel="modulepreload"[^>]+href="\/([^"]+\.js)"/g)].map((m) => m[1]);
const css = [...html.matchAll(/<link rel="stylesheet"[^>]+href="\/([^"]+\.css)"/g)].map((m) => m[1]);
const fonts = [...html.matchAll(/<link rel="preload" href="\/([^"]+\.woff2)"/g)].map((m) => m[1]);

const rows = [
  // React, the router, the query cache and i18next are most of it; the home and a text's page come with it (the
  // pages people land on); French's words and every other page load apart. 141 since the discussion (19 Oct 2026):
  // its entry points (the margin's count, one route import, three footer links) are 0.4 KB; its pages and words
  // load apart. 141.5 since the work topic (20 Oct 2026): a text whose French is a consolidation (Adala's labour code,
  // to 2011) says so on its page, and an article changed since says its French is older than its Arabic (0.3 KB).
  // 142 since the constitution's pages (25 Oct 2026, a review): the text page names the constitution's own
  // opening and map, and the app its /constitution route, both loaded apart (0.2 KB). 145 since
  // the Moroccan-design review (U20, 25 Oct 2026): one sheet the phone's back closes, the doors, the reference peek and the
  // motion; the home's lower sections were already apart, so the room could not come from them.
  // 144.8 since 27 Oct 2026: JS chunks carry seven hash characters (vite.config.ts), and the entry names 121 of them.
  // 145.2 since 1 Nov 2026 (a percent's sign always on the right): every Arabic string keeps a percent's sign
  // on the right of its number, a post-processor in the translation layer (0.1 KB); the home's end had already left.
  // 145.3 since 2 Nov 2026 (the open data closed): no code at first load changed, but main stood 4 bytes under and the
  // entry's list of chunk names compressed 15 bytes worse with the library's, about's and /data's new hashes.
  // 145.4 since 4 Nov 2026 (3adala.com): no code at first load changed and the captions got shorter, but the lazy
  // chunks' new hashes made the entry's list of their names compress 18 bytes worse: 145.3008 of 145.3.
  // 145.5 since 6 Nov 2026 (the blog in the header and as a tab of the phone's bottom bar):
  // «بالأرقام» in the header and the bottom bar, its icon and its word in both languages, 6 bytes over 145.4.
  // 145.6 since 9 Nov 2026, for two changes: the search-engines review (IX1, IX8: a Bulletin issue Django draws
  // waits for its page's code before the app mounts over it, a law's title says its subject) and the wordmark «قانون
  // المغرب» in the header, in place of the arch and the name: 11 bytes over 145.5 (its drawing is a file of its own).
  // 145.8 since 9 Nov 2026 (a reader who types an article's famous number, such as 222, finds its law): a law's page says the public's name of
  // an article people know by its number, and the search box offers it while typing (its card and words load apart with
  // the search page): 93 bytes over 145.6.
  // 145.9 since 12 Nov 2026 (the open-source audit, OP26): a refused refresh ends the session only when the server
  // refuses the token itself (17 bytes in the first load's api.ts), and the lazy chunks' new hashes made the entry's
  // list of their names compress a few bytes worse: 3 bytes over 145.8.
  // 146.2 since 15 Nov 2026 (the analytics review): what the site counts is noted where it happens, so the first load
  // carries the measures' waiting line (shared/analytics/note.ts, beside api.ts, which notes an endpoint that failed),
  // the idle import of their engine (main.tsx: the engine and web-vitals load apart) and the routes' boundary handing the
  // error it caught to the window: 311 bytes (149,286 to 149,597). The engine's chunk is named after the build, and the
  // entry's list of chunk names moves the total by some tens of bytes from one build to the next: 146.1 left 9 bytes.
  // 146.3 since 16 Nov 2026 (/open-source): the first load carries its route and the footer's word that leads to it, in
  // both languages (about 90 bytes; the page, its words and its styles load apart), and the entry's list of chunk names
  // moved it 8 bytes over 146.2.
  ['JavaScript at first load', [...entry, ...preloadJs].reduce((n, f) => n + gz(f), 0), 146.3 * 1024],
  ['Stylesheet', css.reduce((n, f) => n + gz(f), 0), 15 * 1024],
  ['Fonts an Arabic page needs', fonts.reduce((n, f) => n + statSync(path.join(DIST, f)).size, 0), 75 * 1024],
];
// The pages people land on, drawn at the deploy (HM2 of the hard-moment review): what a first visit downloads
// before its first words, the page itself, gzipped as nginx sends it. Checked when a prerender has written them.
const landing = (dir) => readdirSync(dir, { withFileTypes: true }).flatMap((e) => e.isDirectory()
  ? landing(path.join(dir, e.name)) : e.name === 'index.html.gz' ? [path.join(dir, e.name)] : []);
try {
  const home = statSync(path.join(DIST, 'home.html.gz')).size;
  const pages = [path.join(DIST, 'topics'), path.join(DIST, 'blog')].flatMap(landing);
  const largest = Math.max(...pages.map((f) => statSync(f).size));
  // The largest are whole pages, not a first screen: the road's compensation table, the blog's maps (69 KB, 7 Nov 2026).
  rows.push(['The home, drawn (gzip)', home, 50 * 1024], [`Largest of ${pages.length} landing pages`, largest, 72 * 1024]);
} catch { /* no prerender in this build */ }
const fr = readdirSync(path.join(DIST, 'assets')).filter((f) => /^fr-.*\.js$/.test(f));
let over = 0;
for (const [what, size, budget] of rows) {
  const ok = size <= budget;
  if (!ok) over++;
  console.log(`${ok ? 'ok  ' : 'OVER'} ${what.padEnd(28)} ${kb(size).padStart(9)} of ${kb(budget)}`);
}
console.log(`     French words load apart:     ${fr.length ? fr.map((f) => kb(gz(`assets/${f}`))).join(', ') : 'NOT SPLIT'}`);
if (!fr.length) over++;

// No text under 14 px (1f9ec52, 18 Oct 2026; restored by P2 of the polish review after 1dfc089 had lowered the bottom
// bar to 12.5 px): a class that sets a smaller size fails here, in any file of src/.
const SRC = path.resolve(import.meta.dirname, '../src');
const small = /\btext-xs\b|\btext-\[(?:[0-9]|1[0-3])(?:\.\d+)?px\]|\btext-\[0?\.(?:[0-7]\d*|8[0-6]\d*)rem\]/;
const walk = (dir) => readdirSync(dir, { withFileTypes: true }).flatMap((e) =>
  e.isDirectory() ? walk(path.join(dir, e.name)) : /\.(tsx?|css)$/.test(e.name) ? [path.join(dir, e.name)] : []);
const tiny = walk(SRC).flatMap((file) => readFileSync(file, 'utf8').split('\n')
  .map((line, i) => (small.test(line) ? `${path.relative(SRC, file)}:${i + 1}` : null)).filter(Boolean));
console.log(`${tiny.length ? 'OVER' : 'ok  '} Text under 14 px              ${tiny.length ? tiny.slice(0, 8).join(', ') : 'none'}`);
if (tiny.length) over++;
process.exit(over ? 1 : 0);
