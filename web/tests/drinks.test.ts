import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { groups, hoursOf } from '../src/features/blog/drinks/fines.ts';

// The seventeenth post's meta and figures, as the page reads them (apps/blog/posts/article-28).
const require = createRequire(import.meta.url);
const yaml = require('js-yaml');
const dir = new URL('../../back/apps/blog/posts/article-28/', import.meta.url);
const meta = yaml.load(readFileSync(new URL('meta.yaml', dir), 'utf8'), { schema: yaml.JSON_SCHEMA });
const figures = JSON.parse(readFileSync(new URL('figures.json', dir), 'utf8'));

test('article 28 says what the lead says: 1 to 6 months, 300 to 1.500 dirhams, «الى المغاربة المسلمين»', () => {
  const [first, second] = meta.art28.ar;
  assert.match(first, /الى المغاربة المسلمين\.$/);
  assert.match(second, /بين شهر واحد وستة أشهر/);
  assert.match(second, /بين 300 و 1\.500 درهم/);
  assert.match(meta.lead.ar, /من 47 فصلا/);
  assert.equal(meta.order.articles, 47);
  for (const m of meta.art28.marks) {
    assert.ok(meta.art28.ar[m.p].includes(m.ar), m.key);
    assert.ok(meta.art28.fr[m.p].includes(m.fr), m.key);
  }
});

test('the eighteen fines fall into seven ranges, article 28 alone at 300 to 1.500, ten articles at 500 to 2.500', () => {
  assert.equal(meta.fines.length, 18);
  const g = groups(meta.fines);
  assert.equal(g.length, 7);
  assert.deepEqual(g[0], { lo: 500, hi: 2500, arts: [1, 5, 17, 19, 22, 23, 25, 27, 33, 34], prison: [1, 6] });
  assert.deepEqual(g.find((x) => x.arts.includes(28)), { lo: 300, hi: 1500, arts: [28], prison: [1, 6] });
});

test('300 dirhams were 371 hours of minimum-wage work in 1967 and 17 in 2026', () => {
  assert.equal(hoursOf(300, figures.wage, meta.order.published), 371);
  assert.equal(hoursOf(300, figures.wage, meta.counted_on), 17);
});

test('every text the post names opens its printed page', () => {
  for (const [k, v] of Object.entries(figures.texts)) assert.ok((v as { viewer: string | null }).viewer, k);
  assert.ok(figures.articles['28'] && figures.articles['44']);
});
