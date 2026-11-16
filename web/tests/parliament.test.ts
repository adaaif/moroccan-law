import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { arabicKey, daysToRead, span, withoutParliament } from '../src/features/blog/parliament/time.ts';

// The twenty-first post's meta and figures, as the page reads them (apps/blog/posts/parliament).
const require = createRequire(import.meta.url);
const yaml = require('js-yaml');
const dir = new URL('../../back/apps/blog/posts/parliament/', import.meta.url);
const meta = yaml.load(readFileSync(new URL('meta.yaml', dir), 'utf8'), { schema: yaml.JSON_SCHEMA });
const figures = JSON.parse(readFileSync(new URL('figures.json', dir), 'utf8'));

test('the title\'s ratio is the counted one: 14 decrees and 52 orders for each voted law', () => {
  assert.deepEqual(figures.ratio, { decrees: 14, orders: 52, share: 84 });
  assert.ok(meta.title.ar.includes(`${figures.ratio.decrees} مرسوما`) && meta.title.ar.includes(`${figures.ratio.orders} قرارا`));
  assert.ok(meta.title.fr.includes(`${figures.ratio.decrees} décrets`) && meta.title.fr.includes(`${figures.ratio.orders} arrêtés`));
});

test('the King made the laws in 1965–1970 and 1972–1977, and since 2000 the thinnest year is 2012, the fullest 2016', () => {
  const lone = withoutParliament(figures.years);
  for (const y of [1965, 1966, 1967, 1968, 1969, 1973, 1974, 1975, 1976, 1977]) assert.ok(lone.includes(y), String(y));
  assert.ok(!lone.includes(1971) && !lone.includes(2016));
  const since = figures.years.filter((y: { year: number }) => y.year >= 2000 && y.year < meta.span[1]);
  const voted = since.map((y: { voted: number }) => y.voted);
  assert.equal(since[voted.indexOf(Math.min(...voted))].year, 2012);
  assert.equal(since[voted.indexOf(Math.max(...voted))].year, 2016);
});

test('reading time: the laws in about 500 hours, said in years, months and days', () => {
  const laws = figures.reading[0].words;
  assert.ok(Math.abs(laws / meta.reading.wpm / 60 - 500) < 10);
  assert.equal(daysToRead(laws, 200, 30), 1001);
  assert.deepEqual(span(1001), { y: 2, m: 9, d: 0 });
  assert.deepEqual(span(62), { y: 0, m: 2, d: 0 });
  assert.deepEqual(span(4380), { y: 12, m: 0, d: 0 });
  assert.deepEqual([1, 2, 9, 11, 100, 103].map(arabicKey), ['one', 'two', 'few', 'many', 'many', 'few']);
});
