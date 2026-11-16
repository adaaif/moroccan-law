// A law's page drawn by the app's own components, on demand (IX1 of the search-engines review, 9 Nov 2026). The deploy
// prerenders the 91 named texts (scripts/prerender.mjs); every other law's address — about 192,000 texts and their
// articles — reached a crawler as a head over an empty page. Django answers those addresses (apps/corpus/services/heads.py):
// it works out the answers the app asks for (the law's /api/corpus/at…?window=30, an issue's /api/corpus/issues/…: the
// same kept bytes) and posts them here; this draws the page and Django puts it under the page's head, so the app starts
// from the same answers and mounts over the same words (main.tsx): nothing moves, and Google, Bing and the assistants
// read the law.
//
//   node scripts/ssr-server.mjs           listens on 127.0.0.1:8043 (SSR_PORT; 0 takes a free port, said on its first line)
//   POST /render?path=/ma/code/doc/art_65&one=art_65    body: [[query key, answer], …]  →  200 text/html
//
// `one`: an article's page holds that article alone, as the prerender writes it (the app brings its neighbours): thirty
// articles on every article's page made each a near copy of the next. It needs node alone: dist-ssr/entry-server.js
// carries its packages (vite.config.ts, ssr.noExternal; SSR_ENTRY names another file, for the tests). It reads no
// database and asks nothing of anyone; a page that fails to draw answers 500 and Django sends the head alone, as before.
//
// Pages are drawn one at a time, in the order asked: a draw holds the process. At most SSR_QUEUE wait their turn; past
// that the answer is 503 at once, and Django sends the head alone without waiting. A request whose caller has gone
// (Django stops waiting after SSR_TIMEOUT and closes the connection) is never drawn: before, every page asked was drawn,
// so a burst of pages kept the process drawing for callers long gone while new ones waited behind them. The next page
// is chosen once what arrived during a draw has been read (`settled`), whatever the machine's load.
import { createServer } from 'node:http';
import { join, resolve } from 'node:path';

const root = new URL('..', import.meta.url).pathname;
const PORT = Number(process.env.SSR_PORT ?? 8043);
const QUEUE = Number(process.env.SSR_QUEUE ?? 8);   // pages waiting their turn at most (each takes a fraction of a second)
const MOST = 8 << 20;           // a law's window is ~0.1–1 MB; a text whole is never sent here
const { render } = await import(process.env.SSR_ENTRY ? resolve(process.env.SSR_ENTRY) : join(root, 'dist-ssr/entry-server.js'));
// React marks a part it could not draw yet (a piece of the app that loads apart, not yet loaded in this process) and
// draws its placeholder: the first law after a start lacked «بالفرنسية», its follow button and what cites it.
const UNDRAWN = '<!--$!-->';

const address = /^\/(ma|bo)\/[\w/.~+-]+$/;

/** The page drawn whole: again, once the parts it asked for have loaded (three passes at most for a new kind of page,
 *  one once the process has drawn it). React's streaming prerender waits too, but puts what waited after the footer in
 *  a hidden block a script moves: a crawler that runs no script would read the law there. Null when the caller left
 *  between two passes. */
async function drawn(path, seed, gone) {
  for (let pass = 0; ; pass++) {
    const html = render(path, seed);
    if (!html.includes(UNDRAWN) || pass >= 5) return html;
    await new Promise((done) => setTimeout(done, 20));
    if (gone()) return null;
  }
}

function alone(seed, eid) {
  return seed.map(([key, data]) => {
    if (key[0] !== 'textAt' || !Array.isArray(data?.articles)) return [key, data];
    const i = data.articles.findIndex((a) => a.eid === eid);
    if (i < 0) return [key, data];
    const start = (data.range?.[0] ?? 0) + i;
    return [key, { ...data, articles: [data.articles[i]], range: [start, start + 1] }];
  });
}

/** The pages waiting their turn, and whether one is being drawn. */
let waiting = [];
let busy = false;

/** What the event loop has read so far: connections, requests' bytes, callers leaving. A draw holds the process, so
 *  what arrived meanwhile is read only once it ends, one step a turn: Node accepts one waiting connection a turn of its
 *  loop, reads its request the turn after and, when its caller left, the connection's end the turn after that. */
let heard = 0;
const hear = () => { heard += 1; };
const TURNS = 1000;             // a bound, so a stream of arrivals cannot put the next page off for ever

/** Until a whole turn of the event loop has passed with nothing new read: every page that arrived during the draw is
 *  then waiting and every caller that left is known, on a loaded machine as on an idle one. Until 13 Nov 2026 the next
 *  page was chosen after a 5 ms timer, which a busy machine could outlast before it had read everything. A turn is a
 *  pass of the loop that waits for nothing, a few microseconds when there is nothing to read. */
async function settled() {
  for (let seen = -1, turns = 0; seen !== heard && turns < TURNS; turns++) {
    seen = heard;
    await new Promise((done) => setImmediate(done));
  }
}

async function work() {
  if (busy) return;
  busy = true;
  try {
    for (await settled(); waiting.length; await settled()) {
      const job = waiting.shift();
      if (job.gone()) continue;           // its caller stopped waiting: nobody would read it
      await job.draw();
    }
  } finally {
    busy = false;
  }
}

async function answer(req, res, path, one, body, gone) {
  const started = performance.now();
  try {
    let seed = JSON.parse(body.toString('utf8'));
    if (one) seed = alone(seed, one);
    const html = await drawn(path, seed, gone);
    if (html === null || gone()) return;
    res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8',
                         'Server-Timing': `render;dur=${(performance.now() - started).toFixed(1)}` });
    res.end(html);
  } catch (e) {
    console.error(`${path}: ${e instanceof Error ? e.stack : e}`);
    if (!res.headersSent) res.writeHead(500);
    res.end();
  }
}

const server = createServer((req, res) => {
  const url = new URL(req.url ?? '/', 'http://ssr');
  if (req.method === 'GET' && url.pathname === '/health') { res.writeHead(200).end('ok'); return; }
  if (req.method !== 'POST' || url.pathname !== '/render') { res.writeHead(404).end(); return; }
  const path = url.searchParams.get('path') ?? '';
  const one = url.searchParams.get('one') ?? '';
  if (!address.test(path)) { res.writeHead(400).end(); return; }
  // The caller has gone when its connection closed before the answer was written (the socket is destroyed or no longer
  // writable at once; the close event comes later).
  let left = false;
  res.on('close', () => { if (!res.writableFinished) left = true; });
  const gone = () => left || Boolean(res.socket && (res.socket.destroyed || !res.socket.writable));
  const chunks = [];
  let size = 0;
  req.on('data', (c) => {
    hear();
    size += c.length;
    if (size > MOST) { res.writeHead(413).end(); req.destroy(); return; }
    chunks.push(c);
  });
  req.on('end', () => {
    hear();
    if (res.writableEnded || gone()) return;
    waiting = waiting.filter((job) => !job.gone());
    if (waiting.length >= QUEUE) {
      // Busy: the head alone now is better than the words too late.
      res.writeHead(503, { 'Retry-After': '5' }).end();
      return;
    }
    waiting.push({ gone, draw: () => answer(req, res, path, one, Buffer.concat(chunks), gone) });
    void work();
  });
});
server.on('connection', (socket) => {
  hear();
  socket.on('end', hear);       // its caller closed the connection
});
server.listen(PORT, '127.0.0.1', () => console.log(`ssr on 127.0.0.1:${server.address().port}`));
