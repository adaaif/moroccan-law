import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { days, inYear, pieces } from '../src/features/blog/emergency/calendar.ts';

// The twenty-seventh post's figures, as the page reads them (apps/blog/posts/emergency).
const dir = new URL('../../back/apps/blog/posts/emergency/', import.meta.url);
const figures = JSON.parse(readFileSync(new URL('figures.json', dir), 'utf8'));
const meta = readFileSync(new URL('meta.yaml', dir), 'utf8');

test('33 decrees after the declaration, each carrying the emergency further, the last to 28 February 2023', () => {
  assert.equal(figures.terms.length, 33);
  assert.ok(meta.includes('33 مرسوما'));
  assert.equal(figures.declared_until, '2020-04-20');
  let prev = figures.declared_until;
  for (const t of figures.terms) { assert.ok(t.until > prev, t.number); prev = t.until; }
  assert.equal(figures.terms[32].until, '2023-02-28');
  assert.deepEqual(figures.terms.filter((t: { changes?: boolean }) => t.changes).map((t: { number: string }) => t.number), ['2.21.590', '2.21.643']);
  assert.equal(days('2020-03-24', '2023-02-28'), 1071);
});

test('a term across a new year is cut in two pieces of the calendar', () => {
  assert.deepEqual(pieces({ key: 'x', from: '2020-12-10', to: '2021-01-10' }).map(([y]) => y), [2020, 2021]);
  assert.equal(inYear('2021-01-01'), 0);
  assert.ok(Math.abs(inYear('2020-07-02') - 0.5) < 0.01);
});
