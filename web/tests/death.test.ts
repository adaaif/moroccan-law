import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { peopleKey, runs, step, tally } from '../src/features/blog/death/code.ts';

// The twentieth post's meta and figures, as the page reads them (apps/blog/posts/death-penalty).
const require = createRequire(import.meta.url);
const yaml = require('js-yaml');
const dir = new URL('../../back/apps/blog/posts/death-penalty/', import.meta.url);
const meta = yaml.load(readFileSync(new URL('meta.yaml', dir), 'utf8'), { schema: yaml.JSON_SCHEMA });
const figures = JSON.parse(readFileSync(new URL('figures.json', dir), 'utf8'));

test('30 articles of the code punish with death, 28 of them since 1962, and 6 rule on the penalty', () => {
  assert.deepEqual(tally(meta.articles), { death: 30, rule: 6, since1962: 28 });
  assert.deepEqual(figures.checks, []);
  const named = figures.cells.filter((c: { clause?: string }) => c.clause).map((c: { n: string }) => c.n);
  assert.deepEqual(named, meta.articles.map((a: { n: string }) => a.n));
});

test('the code is drawn whole, in runs by its parts, and the arrow keys walk the marked articles', () => {
  assert.equal(figures.cells.length, 732);
  const parts = runs(figures.cells);
  assert.equal(parts.length, meta.groups.length);
  assert.equal(parts.find((r) => r.g === 'state')!.cells[0].n, '163');
  const order = ['16', '41', '163'];
  assert.equal(step(order, '163', 1), '16');
  assert.equal(step(order, '16', -1), '163');
});

test('every reference opens its printed page, and the CNDH counts run 70 to 86', () => {
  for (const [k, v] of Object.entries(figures.texts) as [string, { viewer: string | null }][]) assert.ok(v.viewer, k);
  assert.deepEqual(meta.cndh.years.map((y: { n: number }) => y.n), [70, 74, 78, 83, 83, 86]);
  assert.deepEqual([1, 2, 3, 10, 11, 86, 103].map(peopleKey), ['one', 'two', 'few', 'few', 'many', 'many', 'few']);
});
