import { test } from 'node:test';
import assert from 'node:assert/strict';
import { gone, lastDay, PAPERS } from '../src/topics/land/rules/clock.ts';
import { addMonths, road, workingDays } from '../src/topics/land/rules/permit.ts';

// The land's clock (the land review, M11): each paper's last day as the kit counts it.
test('an opposition closes two months after the notice, to the same date', () => {
  assert.equal(lastDay('oppose', '2026-09-02').date, '2026-11-02');
});

test('pre-emption: thirty days from the notice, a year without one', () => {
  assert.equal(lastDay('preempt', '2026-10-01').date, '2026-10-31');
  assert.equal(lastDay('preempt-year', '2026-03-15').date, '2027-03-15');
});

test('the expropriation inquiry is a complete period: neither first nor last day, a day off moves on', () => {
  // 2 months from Sat 1 Aug 2026 is 1 Oct; complete adds the last day (2 Oct, a Friday), no move.
  assert.equal(lastDay('inquiry', '2026-08-01').date, '2026-10-02');
  // 2 months from 5 Sep 2026 is 5 Nov; +1 is 6 Nov, Green March day (a holiday) → Saturday, Sunday → Monday 9 Nov.
  const moved = lastDay('inquiry', '2026-09-05');
  assert.equal(moved.date, '2026-11-09');
  assert.ok(moved.moved.length >= 1);
});

test('fraud on a title: four years from the entry; a share: thirty days', () => {
  assert.equal(lastDay('fraud', '2024-02-29').date, '2028-02-29');
  assert.equal(lastDay('share', '2026-12-10').date, '2027-01-09');
});

test('every paper has its limit, its article and its journey', () => {
  for (const p of PAPERS) {
    const { limit } = lastDay(p, '2026-01-10');
    assert.match(limit.deadline.path, /^\/ma\//);
    assert.match(limit.journey, /^journeys\//);
  }
});

test('the bar: share of the limit gone', () => {
  assert.equal(gone('2026-09-02', '2026-11-02', '2026-09-02'), 0);
  assert.equal(gone('2026-09-02', '2026-11-02', '2026-12-01'), 1);
});

// The permit's road (M12).
test('working days skip weekends and holidays', () => {
  // Thu 30 Jul 2026 + 3 working days: Fri 31 Jul, (Sat, Sun), Mon 3 Aug, Tue 4 Aug.
  assert.equal(workingDays('2026-07-30', 3), '2026-08-04');
  // Wed 12 Aug + 3: Thu 13, (Fri 14 Oued Ed-Dahab, Sat, Sun), Mon 17, Tue 18.
  assert.equal(workingDays('2026-08-12', 3), '2026-08-18');
});

test('the tacit permit at two months, the lapse a year after', () => {
  const r = road('2026-08-03');
  assert.equal(r.find((s) => s.key === 'tacit')!.date, '2026-10-03');
  assert.equal(r.find((s) => s.key === 'lapse')!.date, '2027-10-03');
  // An express permit given earlier starts its year from that day.
  assert.equal(road('2026-08-03', '2026-09-01').find((s) => s.key === 'lapse')!.date, '2027-09-01');
  assert.equal(addMonths('2026-12-31', 2), '2027-02-28');
});
