// The browser's ma_law (WASM) against the shared vectors in crates/vectors: the citation reader and the
// keyboard repair must answer here exactly as they do in Rust and in Python.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { initSync, fold, layoutCandidates, parseCitations, parseQuery } from '../src/shared/wasm/ma_law/ma_law.js';

const here = new URL('.', import.meta.url);
initSync({ module: readFileSync(new URL('../src/shared/wasm/ma_law/ma_law_bg.wasm', here)) });
const vectors = (name) => JSON.parse(readFileSync(new URL(`../../crates/vectors/${name}.json`, here), 'utf8'));

let n = 0;
for (const v of vectors('fold')) {
  assert.equal(fold(v.in), v.out, v.in);
  n++;
}
for (const v of vectors('layout')) {
  assert.deepEqual(JSON.parse(layoutCandidates(v.in)).map(([, t]) => t), v.out, v.in);
  n++;
}
for (const v of vectors('cite')) {
  const got = JSON.parse(v.query ? parseQuery(v.in) : parseCitations(v.in));
  // The vectors name the fields they pin (issue_suffix only where an issue is «bis»).
  assert.deepEqual(got.map((c, i) => Object.fromEntries(Object.keys(v.want[i] ?? {}).map((k) => [k, c[k]]))), v.want, v.in);
  // UTF-16 offsets slice the same words JavaScript sees.
  for (const c of got) assert.equal(v.in.slice(c.start16, c.end16), c.raw, v.in);
  n++;
}
console.log(`ma_law (wasm): ${n} vectors pass`);
