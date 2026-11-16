import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { byAge, holds, lifeAge, lifeX, next, retireAge } from '../src/features/blog/ages/life.ts';

// The sixteenth post's meta and figures, as the page reads them (apps/blog/posts/ages).
const require = createRequire(import.meta.url);
const yaml = require('js-yaml');
const dir = new URL('../../back/apps/blog/posts/ages/', import.meta.url);
const meta = yaml.load(readFileSync(new URL('meta.yaml', dir), 'utf8'), { schema: yaml.JSON_SCHEMA });
const figures = JSON.parse(readFileSync(new URL('figures.json', dir), 'utf8'));
const ages = meta.ages;
const real = ages.filter((a: { echo?: boolean }) => !a.echo);

test('35 ages in 14 texts, 28 before 26 and one between 26 and 54, as the lead says', () => {
  assert.equal(real.length, 35);
  assert.equal(new Set(real.map((a: { law: string }) => a.law)).size, 14);
  assert.equal(real.filter((a: { age: number }) => a.age < 26).length, 28);
  assert.deepEqual(real.filter((a: { age: number }) => a.age >= 26 && a.age <= 54).map((a: { age: number }) => a.age), [40]);
  assert.match(meta.lead.ar, /قرأنا 35 منها في 14 نصا/);
  assert.match(meta.lead.ar, /28 منها قبل السادسة والعشرين/);
  assert.match(meta.lead.fr, /35 dans 14 textes/);
  assert.equal(meta.moves.length, 7);
});

test('every age and every step opens its printed page, and every law it names is named', () => {
  for (const a of ages) assert.ok(figures.texts[`a-${a.key}`]?.viewer, a.key);
  for (const m of meta.moves) m.steps.forEach((_: unknown, i: number) => assert.ok(figures.texts[`m-${m.key}-${i}`]?.viewer, `${m.key}-${i}`));
  for (const a of ages) assert.ok(meta.laws[a.law], a.law);
  for (const m of meta.moves) for (const s of m.steps) assert.ok(meta.laws[s.law], s.law);
});

test('at 17, eleven rules hold and the next age is 18, where seven things start or end', () => {
  const now = holds(ages, 17).map((a: { key: string }) => a.key);
  assert.deepEqual(now.sort(), ['choose', 'criminal12', 'delegates', 'discern', 'emancipate', 'idcard', 'light', 'mines', 'moped', 'prints', 'work']);
  const n = next(ages, 17)!;
  assert.equal(n.age, 18);
  assert.equal(n.items.length, 7);
  assert.equal(next(ages, 65), null);
  assert.ok(byAge(ages).every((g, i, all) => i === 0 || all[i - 1].age < g.age));
});

test('the line of a life gives youth most of its width and comes back to the same age', () => {
  assert.equal(lifeX(0), 0);
  assert.ok(Math.abs(lifeX(26) - 0.7) < 1e-9 && Math.abs(lifeX(66) - 1) < 1e-9);
  for (const age of [0, 4, 7, 10, 12, 14, 15, 16, 18, 19, 20, 21, 25, 40, 55, 60, 63, 65]) assert.equal(lifeAge(lifeX(age)), age, String(age));
});

test('the civil servant born in 1959 retires at 61 and a half, before 1957 at 60, from 1962 at 63', () => {
  const steps = meta.retire.steps;
  assert.equal(retireAge(steps, 1959), 61.5);
  assert.equal(retireAge(steps, 1950), 60);
  assert.equal(retireAge(steps, 1990), 63);
});
