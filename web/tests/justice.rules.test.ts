import { test } from 'node:test';
import assert from 'node:assert/strict';
import { cells, lastDay, rule, startsFrom } from '../src/topics/justice/rules/deadline.ts';
import { clock, longest, plusHours } from '../src/topics/justice/rules/custody.ts';
import { court } from '../src/topics/justice/rules/court.ts';
import { alternatives } from '../src/topics/justice/rules/alternative.ts';
import { holiday } from '../src/topics/kit/holidays.ts';

test('a civil appeal: 30 complete days from the notification, the end moved off a weekend (58.25 arts 204, 602)', () => {
  // Notified on Thursday 1 October 2026: days 2 Oct … 31 Oct counted, 1 Nov (a Sunday) not counted → Monday 2 Nov.
  const l = lastDay('appeal', '2026-10-01');
  assert.equal(l.counted, '2026-10-31');
  assert.equal(l.date, '2026-11-02');
  // Notified Monday 5 October: counted to 4 Nov, the uncounted last day Thursday 5 Nov — not a holiday, it stays.
  assert.equal(lastDay('appeal', '2026-10-05').date, '2026-11-05');
});

test('the Green March moves a 15-day limit (58.25 art. 602, decree 2.77.169)', () => {
  // Notified 21 October: counted to 5 Nov, the last day 6 Nov is the Green March → Monday 9 Nov.
  const l = lastDay('opposition', '2026-10-21');
  assert.equal(l.date, '2026-11-09');
  assert.ok(l.moved.some((h) => h.key === 'greenMarch'));
});

test('criminal limits are 10 days, from the pronouncement for one present, else from the notification (22.01 arts 400, 750)', () => {
  assert.equal(rule('crim-appeal').days, 10);
  assert.equal(startsFrom(rule('crim-appeal'), true), 'pronounced');
  assert.equal(startsFrom(rule('crim-appeal'), false), 'notice');
  assert.equal(lastDay('crim-appeal', '2026-10-13').date, '2026-10-26');   // 24 Oct counted, 25 a Sunday → 26
});

test('a complaint lapses 4 years after a délit, 15 after a crime, 1 after a contravention (22.01 art. 5)', () => {
  assert.equal(lastDay('delit', '2023-03-15').date, '2027-03-15');
  assert.equal(lastDay('crime', '2020-02-29').date, '2035-02-28');
  assert.equal(lastDay('contravention', '2026-01-10').date, '2027-01-10');
});

test('the month grid hatches the start and the uncounted days, and stamps the last', () => {
  const l = lastDay('appeal', '2026-10-01');
  const g = cells('2026-10-01', l, (d) => Boolean(holiday(d)) || [0, 6].includes(new Date(`${d}T12:00:00Z`).getUTCDay()));
  assert.equal(g.length % 7, 0);
  assert.equal(g.find((c) => c.day === '2026-10-01')!.mark, 'start');
  assert.equal(g.find((c) => c.day === '2026-10-31')!.mark, 'counted');
  assert.equal(g.find((c) => c.day === '2026-11-01')!.mark, 'off');
  assert.equal(g.find((c) => c.day === '2026-11-02')!.mark, 'last');
});

test('custody: 48 hours, 24 more once; 96 and 96 for state security; 96, 96 and 96 for terrorism (22.01 art. 66-2)', () => {
  const c = Object.fromEntries(clock('2026-10-27T22:30', 'ordinary').map((s) => [s.key, s.at]));
  assert.equal(c.lawyer, '2026-10-27T23:30');
  assert.equal(c.end, '2026-10-29T22:30');
  assert.equal(c.ext1, '2026-10-30T22:30');
  assert.equal(longest('ordinary'), 72);
  assert.equal(longest('state'), 192);
  assert.equal(longest('terror'), 288);
  assert.equal(plusHours('2026-12-31T23:00', 2), '2027-01-01T01:00');
});

test('which court: proximity under 5,000, no appeal up to 10,000, no cassation up to 30,000 nor on rents (58.25 arts 30, 331, 375)', () => {
  assert.equal(court('debt', 4_999).court, 'proximity');
  assert.equal(court('debt', 5_000).court, 'first');
  assert.equal(court('debt', 10_000).recourse.kind, 'annul');
  assert.equal(court('debt', 10_001).recourse.kind, 'appeal');
  assert.equal(court('debt', 30_000).cassation.open, false);
  assert.equal(court('debt', 30_001).cassation.open, true);
  assert.equal(court('rent', 500_000).cassation.open, false);
  assert.equal(court('family', 0).court, 'family');
  assert.equal(court('work', 50_000).lawyer, 'aid');
  assert.equal(court('admin', 0).free, 'admin-appeal');
  assert.equal(court('crime', 0).court, 'prosecutor');
});

test('alternatives: three hours a day between 40 and 3,600; 100 to 2,000 DH a day; none past five years, in repeat or for art. 35-3', () => {
  const a = alternatives(90, false, false, 30, true);
  assert.equal(a.open, true);
  assert.equal(a.work.hours, 270);
  assert.deepEqual([a.dayFine.min, a.dayFine.max], [9_000, 180_000]);
  assert.equal(alternatives(10, false, false, 30, false).work.capped, 'min');
  assert.equal(alternatives(10, false, false, 30, false).work.hours, 40);
  assert.equal(alternatives(1500, false, false, 30, false).work.hours, 3600);
  assert.equal(alternatives(1500, false, false, 30, false).dayFine.open, false);
  assert.equal(alternatives(5 * 365 + 1, false, false, 30, true).why, 'term');
  assert.equal(alternatives(60, true, false, 30, true).why, 'repeat');
  assert.equal(alternatives(60, false, true, 30, true).why, 'excluded');
  assert.equal(alternatives(60, false, false, 14, true).work.open, false);
});

test('custody: a minor in an ordinary case gets no extension (22.01 art. 460, HM6 of the hard-moment review)', () => {
  const stops = clock('2026-11-06T23:00', 'ordinary', true);
  assert.deepEqual(stops.map((x) => x.key), ['arrest', 'lawyer', 'end']);
  assert.equal(stops[2].at, '2026-11-08T23:00');
  assert.equal(stops[2].path, '/ma/loi/22-01/art_460');
  // State security and terrorism are crimes of art. 108: their extensions stand for a minor too.
  assert.equal(clock('2026-11-06T23:00', 'terror', true).length, 5);
});
