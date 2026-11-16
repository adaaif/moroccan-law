import { test } from 'node:test';
import assert from 'node:assert/strict';
import { card, dutyDay, lastValid, stamp } from '../src/topics/papers/rules/card.ts';
import { lastDay } from '../src/topics/papers/rules/clock.ts';
import { phase, stops } from '../src/topics/papers/rules/counter.ts';
import { check } from '../src/topics/papers/rules/names.ts';
import { byLaw, byRequest, onCard3 } from '../src/topics/papers/rules/rehab.ts';

test('the card is due at 16 full years (04.20 art. 2)', () => {
  assert.equal(dutyDay('2010-03-05'), '2026-03-05');
  assert.equal(card('2010-03-05', '2026-03-04', null).state, 'none-young');
  assert.equal(card('2010-03-05', '2026-03-05', null).state, 'none-due');
});

test('ten years past 12; before, seven at most and never past the day before 12 (2.20.521 art. 1)', () => {
  assert.equal(lastValid('1990-06-01', '2026-10-27'), '2036-10-27');
  assert.equal(lastValid('2020-06-01', '2026-10-27'), '2032-05-31');   // the day before the twelfth birthday comes first
  assert.equal(lastValid('2024-06-01', '2026-10-27'), '2033-10-27');   // seven years come first
});

test('the stamp: 75 DH, 50 under 12 (tax code art. 252)', () => {
  assert.equal(stamp('1990-06-01', '2026-10-27'), 75);
  assert.equal(stamp('2016-06-01', '2026-10-27'), 50);
});

test('an event of art. 13 or a passed date obliges a renewal; a child at 12 too (04.20 art. 13)', () => {
  assert.deepEqual(card('1990-06-01', '2026-10-27', '2030-01-01', ['moved']), { state: 'renew', last: '2030-01-01', why: ['moved'], fee: 75 });
  assert.deepEqual((card('1990-06-01', '2026-10-27', '2026-01-01') as { why: string[] }).why, ['expired']);
  assert.equal(card('1990-06-01', '2026-10-27', '2030-01-01').state, 'valid');
});

test('a birth: 30 days from the next day, its last day off moved to a working day (2.22.04 art. 40)', () => {
  // 1 Oct 2026 + 30 = 31 Oct 2026, a Saturday: moved to Monday 2 Nov.
  assert.equal(lastDay('birth', '2026-10-01').date, '2026-11-02');
  // 10 Jan 2027 is a Sunday and the 11th the Independence Manifesto's holiday: Tuesday the 12th.
  assert.equal(lastDay('birth-abroad', '2026-01-10').date, '2027-01-12');
  assert.equal(lastDay('error', '2026-10-01').date, '2026-10-16');          // the authority's 15 days stay as they fall
});

test('55.19: 60 days, complete; 30 to appeal; 15 to answer it (arts 16, 21, 31)', () => {
  const s = stops('2026-09-01', 'general', 0, null);
  assert.deepEqual(s.map((x) => [x.key, x.date]), [['deposit', '2026-09-01'], ['answer', '2026-11-01'], ['appeal', '2026-12-02'], ['reply', '2026-12-18']]);
  assert.equal(phase(s, '2026-10-27'), 'waiting');
  assert.equal(phase(s, '2026-11-10'), 'appeal');
  assert.equal(phase(s, '2027-01-01'), 'late');
  const r = stops('2026-09-01', 'general', 0, '2026-09-20');
  assert.equal(r.find((x) => x.key === 'appeal')!.date, '2026-10-21');
  assert.equal(stops('2026-09-01', 'investment', 0, null)[1].date, '2026-10-02');
});

test('a first name: two names at most, no title, no number (36.21 art. 34)', () => {
  assert.ok(check('آدم').every((c) => c.ok));
  assert.ok(check('محمد أمين').every((c) => c.ok));
  assert.equal(check('محمد أمين ياسين').find((c) => c.key === 'two')!.ok, false);
  assert.equal(check('مولاي إدريس').find((c) => c.key === 'title')!.found, 'مولاي');
  assert.equal(check('Lalla Salma').find((c) => c.key === 'title')!.ok, false);
  assert.equal(check('يوسف الثاني').find((c) => c.key === 'number')!.ok, false);
});

test('rehabilitation by law: 6 months, 2, 4, 5, 10 years; a year for a suspended sentence (22.01 arts 688, 689)', () => {
  assert.equal(byLaw('fine', '2026-01-31').date, '2026-07-31');
  assert.equal(byLaw('short', '2026-01-31').date, '2028-01-31');
  assert.equal(byLaw('two', '2026-01-31').date, '2030-01-31');
  assert.equal(byLaw('long', '2026-01-31').date, '2031-01-31');
  assert.equal(byLaw('felony', '2026-01-31').date, '2036-01-31');
  assert.equal(byLaw('suspended', '2026-01-31').date, '2027-01-31');
  assert.equal(byRequest('felony', '2026-01-31'), '2030-01-31');
  assert.equal(byRequest('fine', '2026-01-31'), '2026-01-31');
  assert.equal(onCard3('fine'), false);
  assert.equal(onCard3('suspended'), false);
  assert.equal(onCard3('short'), true);
});
