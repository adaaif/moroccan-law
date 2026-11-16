// A stand-in for dist-ssr/entry-server.js in tests/ssr-server.test.ts: it numbers the pages it draws. A seed may hold
// the process while it draws, as a long law does, until the test lets it go: `{ started, release }` are two files; the
// first is written when the drawing starts, and the drawing ends once the second exists (or after a minute).
import { existsSync, writeFileSync } from 'node:fs';

let drawn = 0;

export function render(path, seed) {
  drawn += 1;
  const { started, release } = seed?.[0]?.[1] ?? {};
  if (started && release) {
    writeFileSync(started, '');
    const most = Date.now() + 60_000;
    while (!existsSync(release) && Date.now() < most) { /* drawing */ }
  }
  return `<main data-drawn="${drawn}">${path}</main>`;
}
