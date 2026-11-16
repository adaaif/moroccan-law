import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { changed, days, span } from '../src/features/blog/strike/wait.ts';

// The eighteenth post's meta and figures, as the page reads them (apps/blog/posts/strike).
const require = createRequire(import.meta.url);
const yaml = require('js-yaml');
const dir = new URL('../../back/apps/blog/posts/strike/', import.meta.url);
const meta = yaml.load(readFileSync(new URL('meta.yaml', dir), 'utf8'), { schema: yaml.JSON_SCHEMA });
const figures = JSON.parse(readFileSync(new URL('figures.json', dir), 'utf8'));
const at = (k: string) => meta.path.find((p: { key: string }) => p.key === k).date;

test('62 years from the first «حق الإضراب مضمون» in the Bulletin to the law, and 8 years and 2 months in the House', () => {
  assert.equal(span(meta.constitutions[0].date, meta.law.published).years, 62);
  assert.deepEqual(span(at('filed'), at('house1')), { years: 8, months: 2, days: 18 });
  assert.equal(days(at('filed'), at('house1')), 3001);
  assert.equal(days(at('filed'), meta.election.date), 1, 'filed the day before the election');
  assert.equal(at('printed'), meta.law.published);
});

test('the first clause is the same in all six; the second changed in 1970 and in 2011', () => {
  const words = meta.constitutions.map((c: { words: string }) => c.words);
  for (const w of words) assert.match(w, /^حق ال[اإ]ضراب مضمون\./);
  const marks = words.map((w: string, i: number) => changed(i ? words[i - 1] : null, w).filter((x) => x.changed).map((x) => x.word));
  assert.deepEqual(marks[0], []);
  assert.deepEqual(marks[1], ['التي', 'يمكن', 'معها', 'ممارسة']);
  assert.deepEqual([marks[2], marks[3], marks[4]], [[], [], []]);
  assert.deepEqual(marks[5], ['ويحدد', 'شروط', 'وكيفيات', 'ممارسته.']);
});

test('22 organic laws since 2011, 18 printed before the election of 7 October 2016 and four after', () => {
  assert.equal(meta.organic.length, 22);
  const late = meta.organic.filter((o: { date: string }) => o.date > meta.election.date).map((o: { number: string }) => o.number);
  assert.deepEqual(late, ['26.16', '04.16', '97.15', '35.24']);
  for (const [k, v] of Object.entries(figures.texts)) assert.ok((v as { viewer: string | null }).viewer, k);
});
