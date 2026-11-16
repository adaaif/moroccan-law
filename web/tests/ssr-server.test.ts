import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { once } from 'node:events';
import { existsSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { request } from 'node:http';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

// The drawing service (scripts/ssr-server.mjs) with a stand-in renderer (fixtures/ssr-entry.mjs): pages are drawn in
// turn, a page whose caller has gone is never drawn, and past a short queue the answer is 503 at once. Nothing here
// waits a set time: the first page holds the process until the test lets it go, and every other request is on the
// wire, in its order, before it does. The service chooses its next page only once it has read all of that, so each
// scenario gives one answer, on a loaded machine too: it runs once, with no retry.
const script = fileURLToPath(new URL('../scripts/ssr-server.mjs', import.meta.url));
const entry = fileURLToPath(new URL('./fixtures/ssr-entry.mjs', import.meta.url));

type Answer = { status: number; drawn: number } | 'gone';
type Asked = { answer: Promise<Answer>; sent: Promise<void>; leave: () => void };

/** Until `file` exists, looked at every few milliseconds. */
const until = (file: string) => new Promise<void>((done) => {
  const look = setInterval(() => { if (existsSync(file)) { clearInterval(look); done(); } }, 5);
});

async function service(queue: number) {
  // A free port, chosen by the system and said on the service's first line.
  const child = spawn(process.execPath, [script], {
    env: { ...process.env, SSR_PORT: '0', SSR_ENTRY: entry, SSR_QUEUE: String(queue) },
    stdio: ['ignore', 'pipe', 'inherit'],
  });
  const [line] = await once(child.stdout, 'data');
  const port = Number(/^ssr on 127\.0\.0\.1:(\d+)$/m.exec(String(line))?.[1]);
  assert.ok(port > 0, `the service's first line names its port: ${String(line)}`);
  const folder = mkdtempSync(join(tmpdir(), 'ssr-test-'));
  const started = join(folder, 'started');
  const release = join(folder, 'release');
  /** A page asked on a connection of its own, as each of Django's workers asks. `sent`: its whole request is written;
   *  `leave`: the caller closes its connection. A held page draws until `go` is called. */
  const draw = (held = false): Asked => {
    let leave = () => {};
    let sent!: Promise<void>;
    const answer = new Promise<Answer>((done) => {
      const asked = request({ host: '127.0.0.1', port, path: '/render?path=/ma/loi/65-99', method: 'POST', agent: false }, (res) => {
        let body = '';
        res.on('data', (c) => { body += c; });
        res.on('end', () => done({ status: res.statusCode ?? 0, drawn: Number(/data-drawn="(\d+)"/.exec(body)?.[1] ?? 0) }));
      });
      asked.on('error', () => done('gone'));
      leave = () => asked.destroy();
      sent = new Promise<void>((written) => {
        asked.end(JSON.stringify([[['textAt', '/ma/loi/65-99', ''], held ? { started, release } : {}]]), () => written());
      });
    });
    return { answer, sent, leave };
  };
  return {
    draw,
    drawing: () => until(started),                       // the held page is being drawn
    go: () => writeFileSync(release, ''),
    stop: () => { child.kill(); rmSync(folder, { recursive: true, force: true }); },
  };
}

test('a page whose caller has gone is never drawn', async () => {
  const { draw, drawing, go, stop } = await service(8);
  try {
    const first = draw(true);                             // holds the process while the others arrive
    await drawing();
    const left = draw();
    await left.sent;
    left.leave();
    const next = draw();
    await next.sent;
    go();
    // The page of the caller that left was not drawn: the next one is the second drawn.
    assert.deepEqual([await first.answer, await left.answer, await next.answer],
                     [{ status: 200, drawn: 1 }, 'gone', { status: 200, drawn: 2 }]);
  } finally {
    stop();
  }
});

test('past a short queue a page is refused at once, not drawn late', async () => {
  const { draw, drawing, go, stop } = await service(2);
  try {
    const first = draw(true);
    await drawing();
    const queued = [draw(), draw()];
    for (const q of queued) await q.sent;                 // in their order, before the one too many
    const refused = draw();
    await refused.sent;
    go();
    assert.deepEqual([await refused.answer, await first.answer, ...(await Promise.all(queued.map((q) => q.answer)))],
                     [{ status: 503, drawn: 0 }, { status: 200, drawn: 1 }, { status: 200, drawn: 2 }, { status: 200, drawn: 3 }]);
  } finally {
    stop();
  }
});
