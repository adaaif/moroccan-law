import { test } from 'node:test';
import assert from 'node:assert/strict';
import { dayIn, shiftDay } from '../src/shared/services/today.ts';
import { due } from '../src/topics/kit/dates.ts';

// A1 of the road-signposted review: Morocco's day is asked of its time zone, never read from UTC. The first three tests
// stand on past moments, which every release of the time zone data tells alike.
test('while Morocco was an hour ahead of UTC, half past midnight in Casablanca was already the next day', () => {
  assert.equal(dayIn(new Date('2025-10-25T23:30:00Z')), '2025-10-26');
  assert.equal(new Date('2025-10-25T23:30:00Z').toISOString().slice(0, 10), '2025-10-25');
});

test('the insurer\'s five days count from the day in Morocco', () => {
  const day = dayIn(new Date('2025-10-25T23:30:00Z'));
  assert.equal(due(day, { key: '', path: '', label: '', days: 5 }), '2025-10-31');
});

test('during Ramadan Morocco was on UTC, and the day is the same', () => {
  assert.equal(dayIn(new Date('2026-02-25T23:30:00Z')), '2026-02-25');
});

// Decree 2.26.530 (Bulletin 7521, p. 3768): on Sunday 20 September 2026 at two in the morning Morocco went back to
// Greenwich's time, for the whole year. The time zone data says so from its release 2026c; a Node that carries an
// older one still counts Morocco an hour ahead, and its day an hour early. There the test is skipped and says why;
// in CI (CI=true) it runs whatever the data, so a green run never rests on a clock that is an hour off.
const data = (process.versions as Record<string, string | undefined>).tz ?? '';
const old = data < '2026c' && process.env.CI !== 'true'
  ? `this Node's time zone data (${data || 'unknown'}) is older than 2026c: update Node`
  : false;

test('since 20 September 2026 Morocco is on UTC: half past eleven at night is still the same day', { skip: old }, () => {
  assert.equal(dayIn(new Date('2026-09-19T23:30:00Z')), '2026-09-20');     // the last night an hour ahead
  assert.equal(dayIn(new Date('2026-10-25T23:30:00Z')), '2026-10-25');
  assert.equal(dayIn(new Date('2027-07-01T23:30:00Z')), '2027-07-01');     // and no summer hour after it
});

test('days shift on the calendar, across a month and a year', () => {
  assert.equal(shiftDay('2026-03-01', 1), '2026-02-28');
  assert.equal(shiftDay('2027-01-01', 1), '2026-12-31');
  assert.equal(shiftDay('2026-10-26', -7), '2026-11-02');
});
