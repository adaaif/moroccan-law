import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { percent, perYear, sums, total } from '../src/features/blog/expropriation/sums.ts';

// The twenty-fourth post's figures, as the page reads them (apps/blog/posts/expropriation).
const dir = new URL('../../back/apps/blog/posts/expropriation/', import.meta.url);
const figures = JSON.parse(readFileSync(new URL('figures.json', dir), 'utf8'));
const meta = readFileSync(new URL('meta.yaml', dir), 'utf8');

test('912 declarations since 2020, nearly half for water, against a third in the 2010s', () => {
  const now = sums(figures.years, 2020, 2026), before = sums(figures.years, 2010, 2019);
  const all = Object.values(now).reduce((a: number, b) => a + (b as number), 0) as number;
  const prev = Object.values(before).reduce((a: number, b) => a + (b as number), 0) as number;
  assert.equal(all, 912);
  assert.ok(meta.includes('912 مرسوما منذ 2020'));
  assert.equal(percent(now.water, all), 47);
  assert.equal(percent(before.water, prev), 36);
  assert.ok(all / 6.9 > prev / 10, 'a faster pace than the 2010s');
});

test('every example and the law open their page; a year\'s total sums its purposes', () => {
  for (const [k, v] of Object.entries(figures.texts) as [string, { viewer: string | null }][]) assert.ok(v.viewer, k);
  assert.equal(total({ year: 2024, water: 99, road: 30 }), 129);
  assert.equal(perYear(912, 7), 130);
});
