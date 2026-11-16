import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

// The service worker (public/sw.js), run against a stand-in for the browser's caches: what it answers, and what it
// keeps under which key.
const ORIGIN = 'https://site.test';
const source = readFileSync(new URL('../public/sw.js', import.meta.url), 'utf8');

type Key = string | { url: string };
type Listener = (event: unknown) => void;
const urlOf = (k: Key) => new URL(typeof k === 'string' ? k : k.url, ORIGIN).href;

function worker(answer: (url: string) => Response = () => new Response('<html></html>', { status: 200 })) {
  const stores = new Map<string, Map<string, Response>>();
  const store = (name: string) => {
    if (!stores.has(name)) stores.set(name, new Map());
    const kept = stores.get(name)!;
    return {
      put: async (k: Key, res: Response) => { kept.set(urlOf(k), res); },
      match: async (k: Key) => kept.get(urlOf(k))?.clone(),
      keys: async () => [...kept.keys()].map((url) => ({ url })),
      delete: async (k: Key) => kept.delete(urlOf(k)),
      addAll: async () => {},
    };
  };
  const caches = {
    open: async (name: string) => store(name),
    keys: async () => [...stores.keys()],
    delete: async (name: string) => stores.delete(name),
    match: async (k: Key) => [...stores.values()].map((s) => s.get(urlOf(k))).find(Boolean),
  };
  const listeners: Record<string, Listener> = {};
  const self = {
    addEventListener: (type: string, fn: Listener) => { listeners[type] = fn; },
    location: { origin: ORIGIN },
    skipWaiting: async () => {},
    clients: { claim: async () => {} },
  };
  const fetch = async (req: Key) => answer(urlOf(req));
  new Function('self', 'caches', 'fetch', 'Request', source)(self, caches, fetch, Request);
  return { listeners, stores };
}

async function navigate(sw: ReturnType<typeof worker>, path: string) {
  let answered: Promise<Response> | null = null;
  sw.listeners.fetch({
    request: { url: `${ORIGIN}${path}`, method: 'GET', mode: 'navigate' },
    respondWith: (p: Promise<Response>) => { answered = p; },
  });
  if (answered) await answered;
  await new Promise((done) => setTimeout(done, 5));        // the copy is put after the answer
  return answered !== null;
}

const kept = (sw: ReturnType<typeof worker>) => [...sw.stores.values()].flatMap((s) => [...s.keys()]);

test('the admin, the assistants\' sign-in, the MCP server, the gate and static files are never the worker\'s', async () => {
  const sw = worker();
  for (const path of ['/admin/', '/admin/accounts/user/?q=salma', '/oauth/authorize?client_id=x', '/mcp', '/gate/',
    '/static/admin/css/base.css', '/.well-known/oauth-authorization-server']) {
    assert.equal(await navigate(sw, path), false, path);
  }
  assert.deepEqual(kept(sw), []);
});

test('a page is kept under its path alone, and one-time addresses are not kept', async () => {
  const sw = worker();
  assert.equal(await navigate(sw, '/ma/code/doc?window=3#art_12'), true);
  assert.equal(await navigate(sw, '/letters/stop?t=signed-token'), false);
  assert.equal(await navigate(sw, '/reset'), false);
  assert.deepEqual(kept(sw), [`${ORIGIN}/ma/code/doc`]);
});

test('an answer marked no-store is not kept', async () => {
  const sw = worker(() => new Response('<html></html>', { status: 200, headers: { 'Cache-Control': 'no-cache, no-store' } }));
  assert.equal(await navigate(sw, '/account'), true);
  assert.deepEqual(kept(sw), []);
});

test('a new version drops what the old one kept', async () => {
  const sw = worker();
  sw.stores.set('law-0-pages', new Map([[`${ORIGIN}/admin/`, new Response('x')]]));
  let done: Promise<unknown> = Promise.resolve();
  sw.listeners.activate({ waitUntil: (p: Promise<unknown>) => { done = p; } });
  await done;
  assert.equal(sw.stores.has('law-0-pages'), false);
});
