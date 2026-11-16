import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { at, beforeRamadan, longestRun, notices, row, slotDay, slotOf, summary, type Clock } from '../src/features/blog/clock/time.ts';

// The post's own meta and figures, as the page reads them (apps/blog/posts/clock).
const require = createRequire(import.meta.url);
const yaml = require('js-yaml');
const dir = new URL('../../back/apps/blog/posts/clock/', import.meta.url);
const meta = yaml.load(readFileSync(new URL('meta.yaml', dir), 'utf8'));
const figures = JSON.parse(readFileSync(new URL('figures.json', dir), 'utf8'));
const c: Clock = { legal_from: meta.legal_from instanceof Date ? meta.legal_from.toISOString().slice(0, 10) : meta.legal_from, moves: meta.moves, unknown: meta.unknown };

test('each move flips the clock, except 1940, which sets ahead again after a return no text found', () => {
  for (let i = 1; i < c.moves.length; i += 1) {
    if (c.moves[i].at.startsWith('1940-02-25')) { assert.equal(c.moves[i - 1].to, 60); continue; }
    assert.notEqual(c.moves[i].to, c.moves[i - 1].to, c.moves[i].at);
  }
});

test('the day a text names reads as the text says', () => {
  assert.equal(at(c, '1913-10-01T12:00').state, 'none');
  assert.equal(at(c, '1913-12-01T12:00').state, 'gmt');
  assert.equal(at(c, '1918-06-01T12:00').state, 'ahead');
  assert.equal(at(c, '1939-12-01T12:00').state, 'unknown');
  // The return set for 18 November 1945 was undone the day before: the clock stayed ahead until 30 September 1946.
  assert.equal(at(c, '1945-12-01T12:00').state, 'ahead');
  assert.equal(at(c, '1946-10-01T12:00').state, 'gmt');
  assert.equal(at(c, '1967-06-03T11:59').state, 'gmt');
  assert.equal(at(c, '1967-06-03T12:00').state, 'ahead');
  assert.equal(at(c, '1985-01-01T12:00').state, 'ahead');
  assert.equal(at(c, '2000-01-01T12:00').state, 'gmt');
  assert.equal(at(c, '2020-05-01T12:00').state, 'gmt');
  assert.equal(at(c, '2020-06-01T12:00').state, 'ahead');
  assert.equal(at(c, '2026-09-20T01:59').state, 'ahead');
  assert.equal(at(c, '2026-09-20T02:00').state, 'gmt');
  assert.equal(at(c, '2026-09-20T02:00').since?.text, 'd226530');
});

test('a row keeps a 29 February in every year, empty in a common one', () => {
  assert.equal(slotDay(2023, 59), null);
  assert.equal(slotDay(2024, 59), '2024-02-29');
  assert.equal(slotOf('2026-09-20'), 263);
  assert.equal(slotDay(2026, 263), '2026-09-20');
  const r = row(c, 1989);
  assert.equal(r[slotOf('1989-06-03')], 1);
  assert.equal(r[slotOf('1989-06-04')], 2);
  assert.equal(r[slotOf('1989-06-30')], 2);
  assert.equal(r[slotOf('1989-07-01')], 1);
});

test('the lead prints the texts and the moves counted', () => {
  const s = summary(c, meta.texts.length, '2026-11-06');
  assert.equal(s.texts, 51);
  assert.equal(s.moves, 75);
  assert.match(meta.lead.ar, new RegExp(`الساعة ${s.moves} مرة`));
  assert.match(meta.lead.fr, new RegExp(`${s.moves} fois`));
  assert.match(meta.title.ar, new RegExp(`${s.texts} نصا`));
  // The longest hour ahead: 25 February 1940 to 30 September 1946; the shortest, June 1989; the longest at Greenwich,
  // July 1918 to September 1939 (July 1989 to June 2008 comes second).
  assert.equal(s.longestAhead.from?.at, '1940-02-25T02:00');
  assert.equal(s.shortestAhead.from?.at, '1989-06-04T00:00');
  assert.equal(Math.round(s.shortestAhead.days), 27);
  assert.equal(s.longestGmt.from?.at, '1918-07-15T00:00');
});

test('the Bulletin printed some moves after the clock had moved', () => {
  const n = notices(c, figures.texts);
  const of = (day: string) => n.find((x) => x.move.at.startsWith(day))!;
  assert.equal(of('2026-09-20').days, 83);
  assert.equal(of('2018-06-17').days, 38);
  assert.ok(of('1967-06-03').days < 0, 'the royal decree of 1967 came out in July');
  assert.ok(of('1946-09-30').days < 0);
  assert.ok(n.every((x) => !x.move.rule));
});

test('for nineteen years the clock went back in the week before the first of Ramadan', () => {
  const r = beforeRamadan(c, figures.hijri);
  const years = r.map((x) => x.year);
  assert.deepEqual(longestRun(years), [2008, 2026]);
  assert.ok(r.every((x) => x.before >= 0 && x.before <= 7));
  assert.equal(r.find((x) => x.year === 2026)?.back.at, '2026-02-15T03:00');
});
