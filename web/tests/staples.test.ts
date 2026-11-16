import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { segments, wageOn } from '../src/features/blog/marquise/price.ts';

// The fifteenth post's meta and figures, as the page reads them (apps/blog/posts/bread-gasoil).
const require = createRequire(import.meta.url);
const yaml = require('js-yaml');
const dir = new URL('../../back/apps/blog/posts/bread-gasoil/', import.meta.url);
const meta = yaml.load(readFileSync(new URL('meta.yaml', dir), 'utf8'), { schema: yaml.JSON_SCHEMA });
const figures = JSON.parse(readFileSync(new URL('figures.json', dir), 'utf8'));
const days = (a: string, b: string) => Math.round((Date.parse(`${b}T00:00:00Z`) - Date.parse(`${a}T00:00:00Z`)) / 86_400_000);
const minutes = (dh: number, on: string) => Math.round((dh / wageOn(figures.wage, on)!) * 60);

test('every staple rose in May 1981 and the June orders took back between 45 and 69 per cent of the rise', () => {
  const back = meta.basket.map((b: { values: number[] }) => Math.round(((b.values[1] - b.values[2]) / (b.values[1] - b.values[0])) * 100));
  for (const b of meta.basket) assert.ok(b.values[1] > b.values[0] && b.values[2] < b.values[1] && b.values[2] > b.values[0], b.key);
  assert.deepEqual([Math.min(...back), Math.max(...back)], [45, 69]);
  assert.equal(back[0], 50, 'the loaf: exactly half');
  // The loaf at 0,90 from the May order's first day (29 May, its third article) to the June order's (7 June): 9 days;
  // September 1980 to May 1981, 266.
  assert.equal(days(meta.issues[1].from, meta.issues[2].from), 9);
  assert.equal(days(meta.issues[0].from, meta.issues[1].from), 266);
});

test('gasoil: 23 prices, 25 minutes of work a litre in 1975, 64 in 1981, 42 at the last printed price', () => {
  assert.equal(meta.gasoil.length, 23);
  assert.match(meta.lead.ar, /كتبت 23 ثمنا/);
  assert.match(meta.lead.fr, /23 prix/);
  const from = meta.gasoil.map((g: { from: string }) => g.from);
  assert.deepEqual(from, [...from].sort());
  assert.equal(minutes(meta.gasoil[0].price / 100, meta.gasoil[0].from), 25);
  const top = Math.max(...meta.gasoil.map((g: { price: number; from: string }) => minutes(g.price / 100, g.from)));
  assert.equal(top, 64);
  assert.equal(minutes(meta.last.price / 100, meta.last.from), 42);
});

test('three orders came out more than two months after they applied, 180.80 the latest (148 days)', () => {
  const late = meta.gasoil.filter((g: { printed?: boolean; from: string; date: string }) => !g.printed && days(g.from, g.date) > 60);
  assert.deepEqual(late.map((g: { number: string }) => g.number), ['180.80', '481.81', '246.07']);
  assert.equal(Math.max(...late.map((g: { from: string; date: string }) => days(g.from, g.date))), 148);
});

test('the litre has no price where the ministry published it, and the steps stop at the last printed day', () => {
  const ministry = meta.away[0];
  const gas = meta.gasoil.map((g: { from: string; price: number; name: string }) => ({ date: g.from, price: g.price / 100, unit: 'dirham', name: g.name }));
  const s = segments(gas, figures.wage, meta.last.from, { from: ministry.from, to: ministry.to });
  assert.ok(s.some((x) => x.from === ministry.from && x.gap));
  assert.ok(s.every((x) => x.to <= meta.last.from));
});
