import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { runs, texts } from '../src/features/blog/mokri/runs.ts';

// The twenty-fifth post's figures, as the page reads them (apps/blog/posts/mokri).
const dir = new URL('../../back/apps/blog/posts/mokri/', import.meta.url);
const figures = JSON.parse(readFileSync(new URL('figures.json', dir), 'utf8'));
const meta = readFileSync(new URL('meta.yaml', dir), 'utf8');

test('11,679 texts carry the name, every year from 1917 to 1955, and the title says so', () => {
  assert.equal(figures.total, 11679);
  assert.ok(meta.includes('11.679 نصا'));
  const by = new Map(figures.years.map((y: { year: number }) => [y.year, y]));
  for (let y = 1917; y <= 1955; y += 1) assert.ok(texts(by.get(y) as never) > 0, String(y));
  assert.equal(figures.first.date.slice(0, 4), '1913');
  assert.equal(figures.last.date.slice(0, 4), '1956');
});

test('the Residents General follow each other in their order, Lyautey first', () => {
  const r = runs(figures.years.filter((y: { year: number }) => y.year <= 1955)).map(([k]) => k);
  assert.equal(r[0], 'lyautey');
  assert.deepEqual(r.slice(0, 6), ['lyautey', 'steeg', 'saint', 'ponsot', 'nogues', 'puaux']);
  assert.equal(new Set(r).size, r.length, 'each Resident General is one run');
});
