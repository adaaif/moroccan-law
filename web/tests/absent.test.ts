import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { lastDecade, passed, peak, share, textsKey } from '../src/features/blog/absent/screens.ts';

// The nineteenth post's meta and figures, as the page reads them (apps/blog/posts/whatsapp).
const require = createRequire(import.meta.url);
const yaml = require('js-yaml');
const dir = new URL('../../back/apps/blog/posts/whatsapp/', import.meta.url);
const meta = yaml.load(readFileSync(new URL('meta.yaml', dir), 'utf8'), { schema: yaml.JSON_SCHEMA });
const figures = JSON.parse(readFileSync(new URL('figures.json', dir), 'utf8'));
const counted = (k: string) => figures.machines.find((m: { key: string }) => m.key === k) ?? figures.generics.find((m: { key: string }) => m.key === k);

test('no text of law names a network, and nothing is left for a person to read', () => {
  assert.equal(figures.apps.length, meta.apps.length);
  for (const a of figures.apps) assert.equal(a.texts, 0, a.key);
  assert.deepEqual(figures.checks, []);
});

test('each network\'s first page in the Bulletin is the one the meta names, and the Facebook of 2015 comes first', () => {
  for (const a of meta.apps) {
    const f = figures.apps.find((x: { key: string }) => x.key === a.key);
    assert.equal(f.first.date, a.first.date, a.key);
    assert.equal(f.first.page, a.first.page, a.key);
  }
  const first = [...meta.apps].sort((x, y) => x.first.date.localeCompare(y.first.date))[0];
  assert.equal(first.first.date, '2015-03-19');
});

test('the machines are still written: the telegram in 2025, the fax in 2026; the telex last in 2015, the typewriter in 2009', () => {
  assert.equal(counted('telegram').newest.date.slice(0, 4), '2025');
  assert.equal(counted('fax').newest.date.slice(0, 4), '2026');
  assert.equal(counted('telex').newest.date.slice(0, 4), '2015');
  assert.equal(counted('typewriter').newest.date.slice(0, 4), '2009');
  assert.ok(counted('telegram').standing > 1000);
  assert.equal(lastDecade(figures.decades, counted('typewriter').decades), 2000);
  assert.deepEqual(peak(figures.decades, counted('telegram').decades), { decade: 1980, n: counted('telegram').decades[7] });
});

test('WhatsApp passed the fax at the Mediator in 2023, and the shares read as each language writes them', () => {
  const years = meta.mediator.years.map((d: { year: number; fax: number; whatsapp?: number }) => ({ year: d.year, a: d.fax, b: d.whatsapp }));
  assert.equal(passed(years), 2023);
  assert.equal(passed([{ year: 2019, a: 3 }]), null);
  assert.equal(share('61.70', 'ar'), '⁦61,7٪⁩');
  assert.equal(share('18.40', 'fr'), '18,4 %');
});

test('«نص» agrees with its number as Arabic writes it', () => {
  assert.deepEqual([0, 1, 2, 3, 10, 11, 100, 103, 110, 111, 1199].map(textsKey),
    ['zero', 'one', 'two', 'few', 'few', 'many', 'many', 'few', 'few', 'many', 'many']);
});

test('the organic law writes its formula six times, and every quote opens its printed page', () => {
  assert.equal(figures.formula, 6);
  for (const [k, v] of Object.entries(figures.texts) as [string, { viewer: string | null }][]) assert.ok(v.viewer, k);
});
