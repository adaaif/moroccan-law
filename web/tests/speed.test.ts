import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { angle, polar, stack } from '../src/features/blog/speed/dial.ts';

// The twenty-second post's meta and figures, as the page reads them (apps/blog/posts/speed).
const require = createRequire(import.meta.url);
const yaml = require('js-yaml');
const dir = new URL('../../back/apps/blog/posts/speed/', import.meta.url);
const meta = yaml.load(readFileSync(new URL('meta.yaml', dir), 'utf8'), { schema: yaml.JSON_SCHEMA });
const figures = JSON.parse(readFileSync(new URL('figures.json', dir), 'utf8'));

test('the eras run in time, from 35 km/h in 1913 to 120 in 1983 and 2010, each opening its page', () => {
  const years = meta.eras.map((e: { year: number }) => e.year);
  assert.deepEqual(years, [...years].sort((a: number, b: number) => a - b));
  assert.equal(meta.eras[0].kmh, 35);
  assert.equal(meta.eras.find((e: { key: string }) => e.key === 'y1924').kmh, 12);
  assert.equal(Math.max(...meta.eras.map((e: { kmh: number }) => e.kmh)), 120);
  for (const [k, v] of Object.entries(figures.texts) as [string, { viewer: string | null }][]) assert.ok(v.viewer, k);
  assert.equal(figures.texts.y1924.edition, 'translation_fr');
});

test('the ministers\' orders: most fix 60 km/h, between 1956 and 2009', () => {
  const orders = figures.orders as { year: number; kmh: number }[];
  assert.ok(orders.length > 80);
  assert.ok(orders.every((o) => o.year >= 1956 && o.year <= 2009));
  const by = new Map<number, number>();
  for (const o of orders) by.set(o.kmh, (by.get(o.kmh) ?? 0) + 1);
  assert.equal([...by.entries()].sort((a, b) => b[1] - a[1])[0][0], 60);
});

test('the dial: 0 at -120°, 70 at the top, 140 at +120°; orders sharing a year and a speed sit side by side', () => {
  assert.equal(angle(0), -120);
  assert.equal(angle(70), 0);
  assert.equal(angle(200), 120);
  const [x, y] = polar(100, 100, 50, 0);
  assert.ok(Math.abs(x - 100) < 1e-9 && Math.abs(y - 50) < 1e-9);
  assert.deepEqual(stack([{ year: 1970, kmh: 60 }, { year: 1970, kmh: 60 }, { year: 1971, kmh: 60 }]).map((o) => o.k), [0, 1, 0]);
});
