// The site's service worker (row 14 of the reader-experience review; HM27 of the hard-moment review, 7 Nov 2026): what a reader
// has read stays readable without a connection and on a weak one.
// - Pages: the network, but past PATIENCE the copy last seen (a topic's cached page first painted at 12.6 s on a weak
//   signal: the network was asked first with no timer); offline the copy, else «محفوظاتي», else the shell.
// - The law's answers a reader opened (a text's windows, a topic, its journeys, pages and tools' rates): kept as they
//   come, MAX_ANSWERS of them, and answered the same way; an article inside a window kept is answered from that window
//   (offline, art. 56 failed though it came with art. 53). Only public answers, only the ones that came whole (200).
// - The built files (hashed, never changed) from the cache first; the shell's own, and its fonts, at install (after a
//   first visit the cache held 5–24 of the 54–71 files a page used).
// «محفوظاتي» stays the page's own, in IndexedDB.
// - Never the worker's: the admin, the assistants' sign-in, the MCP server, the gate, Django's static files and the
//   well-known documents go to the network as if there were no worker, and nothing of them is kept (an admin's pages
//   stayed on the device and were answered offline with no session). Pages holding a one-time thing in their address
//   (a reset link, Google's answer, an assistant's request, a letters token) go to the network alone too.
// - A page is kept under its path alone, never its query or fragment; nothing that says no-store is kept.
// VERSION moves when what was kept must go: every cache whose name does not begin with it is dropped when this worker
// takes over (an earlier one's pages could hold admin pages and tokens; law-1 also drops the caches kept under the
// project's first name).
const VERSION = 'law-1';
const SHELL = `${VERSION}-shell`;
const ASSETS = `${VERSION}-assets`;
const ANSWERS = `${VERSION}-answers`;
const PAGES = `${VERSION}-pages`;
const MAX_ASSETS = 160;
const MAX_ANSWERS = 80;
const PATIENCE = 2500;
const NEVER = /^\/(?:admin|oauth|gate|static|\.well-known|mcp)(?:\/|$)/;
const ONCE = /^\/(?:reset|auth\/google|connect|letters\/stop)\/?$/;

self.addEventListener('install', (event) => {
  event.waitUntil((async () => {
    const shell = await caches.open(SHELL);
    await shell.addAll(['/', '/saved']).catch(() => {});
    // The shell's scripts, stylesheet and fonts, as index.html names them.
    try {
      const html = await (await fetch('/index.html', { cache: 'no-cache' })).text();
      const files = [...html.matchAll(/(?:src|href)="(\/(?:assets|fonts)\/[^"]+)"/g)].map((m) => m[1]);
      await (await caches.open(ASSETS)).addAll([...new Set(files)]);
    } catch { /* the next visit fills it */ }
    await self.skipWaiting();
  })());
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => !k.startsWith(VERSION)).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  );
});

async function trim(cache, most) {
  const keys = await cache.keys();
  for (const k of keys.slice(0, Math.max(0, keys.length - most))) await cache.delete(k);
}

/** Whole, and not marked no-store. */
const keepable = (res) => res.ok && !/no-store/i.test(res.headers.get('Cache-Control') || '');

/** The network, kept under `key` when whole; past PATIENCE (or failing) what was kept, if anything; else the network's
 *  own end. */
async function patient(req, cacheName, most, fallback, key = req) {
  const cache = await caches.open(cacheName);
  const network = fetch(req).then((res) => {
    if (keepable(res)) void cache.put(key, res.clone()).then(() => trim(cache, most));
    return res;
  });
  const late = new Promise((done) => setTimeout(() => done(null), PATIENCE));
  const first = await Promise.race([network.catch(() => null), late]);
  if (first) return first;
  const kept = (await cache.match(key)) || (fallback ? await fallback(cache) : null);
  if (kept) return kept;
  return network;
}

// A text's answer: /api/corpus/at/<text>/<article>/; another window of the same text that holds the article answers it.
const AT = /^\/api\/corpus\/at(\/.+?)(?:\/(art_[^/]+))?\/?$/;

async function withinWindow(cache, url) {
  const m = AT.exec(url.pathname);
  if (!m || !m[2]) return null;
  const [, text, eid] = m;
  for (const key of await cache.keys()) {
    const k = new URL(key.url);
    const other = AT.exec(k.pathname);
    // The same text on the same day (?on=): another day's version is another text.
    if (!other || other[1] !== text || (k.searchParams.get('on') ?? '') !== (url.searchParams.get('on') ?? '')) continue;
    const res = await cache.match(key);
    try {
      const d = await res.clone().json();
      if (d.articles?.some((a) => a.eid === eid)) return res;
    } catch { /* not a text's answer */ }
  }
  return null;
}

const KEPT = (p) => p.startsWith('/api/corpus/at/') || /^\/api\/topics\/(?:[\w-]+\/(?:[a-z]+\/[\w-]+\/)?)?$/.test(p);

self.addEventListener('fetch', (event) => {
  const req = event.request;
  const url = new URL(req.url);
  if (req.method !== 'GET' || url.origin !== self.location.origin || NEVER.test(url.pathname)) return;

  if (url.pathname.startsWith('/api/')) {
    if (KEPT(url.pathname)) event.respondWith(patient(req, ANSWERS, MAX_ANSWERS, (cache) => withinWindow(cache, url)));
    return;
  }

  if (req.mode === 'navigate') {
    if (ONCE.test(url.pathname)) return;
    // Offline: this page as last seen, else the app's shell, which routes to the page (/saved reads the device).
    event.respondWith(patient(req, PAGES, 40, () => caches.match('/saved').then((s) => s || caches.match('/')),
                              new Request(url.origin + url.pathname)));
    return;
  }

  if (url.pathname.startsWith('/assets/') || url.pathname.startsWith('/fonts/')) {
    event.respondWith(
      caches.open(ASSETS).then((cache) => cache.match(req).then((hit) => hit || fetch(req).then((res) => {
        if (res.ok) void cache.put(req, res.clone()).then(() => trim(cache, MAX_ASSETS));
        return res;
      }))),
    );
  }
});
