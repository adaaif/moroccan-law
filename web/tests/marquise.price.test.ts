import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { compare, dirhams, hm, month, priceOn, segments, wageOn, type Price } from '../src/features/blog/marquise/price.ts';

// The post's own meta and figures, as the page reads them (apps/blog/posts/marquise).
const require = createRequire(import.meta.url);
const yaml = require('js-yaml');
const dir = new URL('../../back/apps/blog/posts/marquise/', import.meta.url);
const meta = yaml.load(readFileSync(new URL('meta.yaml', dir), 'utf8'), { schema: yaml.JSON_SCHEMA });
const figures = JSON.parse(readFileSync(new URL('figures.json', dir), 'utf8'));
const prices: Price[] = meta.prices;
const gap = meta.gap;

test('the orders come in time and the soft pack never got cheaper', () => {
  for (let i = 1; i < prices.length; i += 1) {
    assert.ok(prices[i].date > prices[i - 1].date, prices[i].date);
    assert.ok(dirhams(prices[i]) > dirhams(prices[i - 1]), prices[i].date);
  }
  // Where the orders print three columns, the company's share and Palestine's make the public price.
  for (const p of prices.filter((x) => x.palestine)) assert.equal(Math.round((p.company! + p.palestine!) * 100), Math.round(p.price * 100), p.date);
});

test('1960 and 2026: the same 1 h 44 of work at the minimum wage, for a price 22 times higher', () => {
  const wage = figures.wage;
  const y1960 = priceOn(prices, '1960-08-01')!, y2026 = priceOn(prices, '2026-04-01')!;
  assert.equal(dirhams(y1960), 1.4);
  assert.equal(y2026.price, 31);
  assert.deepEqual(hm(dirhams(y1960) / wageOn(wage, '1960-08-01')!), { h: 1, m: 44 });
  assert.deepEqual(hm(31 / wageOn(wage, '2026-04-01')!), { h: 1, m: 44 });
  assert.equal(Math.floor(31 / 1.4), 22);
  assert.match(meta.lead.ar, /22 مرة/);
  assert.match(meta.lead.ar, /ساعة و44 دقيقة/);
  assert.match(meta.lead.ar, new RegExp(`في ${prices.length} قرارا`));
  assert.match(meta.lead.fr, new RegExp(`dans ${prices.length} arrêtés`));
});

test('between the orders the hours stay between 1 h 15 (1991) and 2 h 21 (1980)', () => {
  const s = segments(prices, figures.wage, '2026-11-06', gap).filter((x) => x.hours !== null && x.from >= '1960-07-22');
  const hours = s.map((x) => x.hours!);
  assert.deepEqual(hm(Math.min(...hours)), { h: 1, m: 15 });
  assert.deepEqual(hm(Math.max(...hours)), { h: 2, m: 21 });
  // No price where the Bulletin printed none.
  assert.equal(priceOn(prices, '1970-01-01', gap), null);
  assert.ok(segments(prices, figures.wage, '2026-11-06', gap).some((x) => x.from === gap.from && x.gap && x.dh === 1.7));
});

test('a drawn guess is set against the order in force on 1 July, and a pack a day is a month at the minimum wage', () => {
  const g = Array(67).fill(null);
  g[1990 - 1960] = 5;
  g[1970 - 1960] = 2;
  assert.deepEqual(compare(g, 1960, prices, gap), [{ year: 1990, guess: 5, truth: 7.5 }]);
  const m = month(1, 31, 17.92);
  assert.equal(Math.round(m.cost), 944);
  assert.equal(Math.round(m.hours), 53);
});
