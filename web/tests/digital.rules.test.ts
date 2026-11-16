import { test } from 'node:test';
import assert from 'node:assert/strict';
import { OFFENCES, SITUATIONS, lapses, spell } from '../src/topics/digital/rules/offence.ts';
import { road } from '../src/topics/digital/rules/info.ts';
import { term } from '../src/topics/digital/rules/copyright.ts';
import { articles, correctBy } from '../src/topics/digital/rules/letter.ts';

test('the penalties as the texts print them (penal code 538, 540, 447-1, 447-3, 607-3, 503-1-1; press code 85)', () => {
  assert.deepEqual(OFFENCES.extortion.prison, [12, 60]);
  assert.deepEqual(OFFENCES.scam.fine, [500, 5_000]);
  assert.deepEqual(OFFENCES.intimate.prison, [6, 36]);
  assert.deepEqual(OFFENCES.intimate.aggravated?.prison, [12, 60]);
  assert.deepEqual(OFFENCES.hacked.prison, [1, 3]);
  assert.equal(OFFENCES.harassment.aggravated?.doubled, true);
  assert.deepEqual(OFFENCES.defamation.fine, [10_000, 100_000]);
  assert.equal(OFFENCES.defamation.prison, undefined);
  assert.equal(SITUATIONS.length, 10);
});

test('a press offence lapses in six months, a délit in four years (88.13 art. 101, 22.01 art. 5)', () => {
  assert.equal(lapses(OFFENCES.insult, '2026-05-31'), '2026-11-30');
  assert.equal(lapses(OFFENCES.extortion, '2026-03-01'), '2030-03-01');
  assert.deepEqual(spell(36), [3, 'years']);
  assert.deepEqual(spell(6), [6, 'months']);
});

test('the information request: 20 working days, holidays and weekends out (31.13 arts 16, 19, 20, 21)', () => {
  // Received Monday 2 November 2026: 6 Nov (Green March) and 18 Nov (Independence Day) do not count.
  const r = Object.fromEntries(road('2026-11-02', false, false).map((s) => [s.key, s.date]));
  assert.equal(r.answer, '2026-12-02');
  assert.equal(Object.fromEntries(road('2026-11-02', true, false).map((s) => [s.key, s.date])).answer, '2026-11-05');
  assert.ok(r.head > r.answer && r.court > r.commissionAnswer);
});

test('copyright: life and seventy years; seventy years from the end of the year of publication (2.00 arts 25, 27, 28)', () => {
  assert.deepEqual(term('author', '1956-07-14'), { until: '2026-07-14', free: '2026-07-15', path: '/ma/loi/2-00/art_25' });
  assert.equal(term('anonymous', '1960').until, '2030-12-31');
  assert.equal(term('collective', '1960').free, '2031-01-01');
});

test('a data correction: ten full days from receipt (09.08 art. 8)', () => {
  // Received Thursday 1 October 2026: 2–11 Oct counted, the 12th not, a Monday: it stays.
  assert.equal(correctBy('2026-10-01'), '2026-10-12');
  assert.deepEqual(articles(['erase', 'access', 'rectify']), ['/ma/loi/9-08/art_7', '/ma/loi/9-08/art_8']);
});
