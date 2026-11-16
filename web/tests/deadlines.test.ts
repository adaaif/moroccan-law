import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { arabicKey, MAX_DAYS, MIN_DAYS, place } from '../src/features/blog/deadlines/time.ts';

// The twenty-third post's figures, as the page reads them (apps/blog/posts/deadlines).
const dir = new URL('../../back/apps/blog/posts/deadlines/', import.meta.url);
const figures = JSON.parse(readFileSync(new URL('figures.json', dir), 'utf8'));
const meta = readFileSync(new URL('meta.yaml', dir), 'utf8');

test('fifteen days is the law\'s favourite deadline, then thirty days, six months and three months', () => {
  const top = figures.deadlines.slice(0, 4).map((d: { unit: string; n: number }) => `${d.n}${d.unit}`);
  assert.deepEqual(top, ['15d', '30d', '6m', '3m']);
  assert.ok(meta.includes('أكثرها 15 يوما، ثم 30 يوما، ثم ستة أشهر، ثم ثلاثة أشهر'));
  assert.ok(figures.total > 10000);
  assert.equal(figures.deadlines[0].example.path, '/ma/loi/70-03/art_68');
});

test('every example\'s words carry a number of its unit, and the counts fall from the first', () => {
  for (const d of figures.deadlines) assert.ok(d.count >= 5);
  const counts = figures.deadlines.map((d: { count: number }) => d.count);
  assert.deepEqual(counts, [...counts].sort((a, b) => b - a));
  for (const d of figures.deadlines.filter((x: { example?: unknown }) => x.example)) assert.match(d.example.words, /(يوم|أيام|ساع|شهر|أشهر|سن|أسبوع|عام)/);
});

test('the scale runs from an hour (0) to 75 years (1), logarithmic', () => {
  assert.equal(place(MIN_DAYS), 0);
  assert.equal(place(MAX_DAYS), 1);
  assert.ok(Math.abs(place(1) - Math.log(24) / Math.log(MAX_DAYS / MIN_DAYS)) < 1e-9);
  assert.deepEqual([1, 2, 3, 10, 11, 15, 103].map(arabicKey), ['one', 'two', 'few', 'few', 'many', 'many', 'few']);
});
