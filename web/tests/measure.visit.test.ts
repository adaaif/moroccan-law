import { test } from 'node:test';
import assert from 'node:assert/strict';
import { backOf, freshOf } from '../src/shared/analytics/visit.ts';

// Readers who come back (the analytics review, 15 Nov 2026): one date on the phone, the Moroccan day it last opened the
// site. 16 November 2026 is a Monday.

test('a phone that kept no day comes for the first time: its first day, week and month', () => {
  assert.equal(backOf(null, '2026-11-18'), 'first');
  assert.equal(freshOf(null, '2026-11-18'), 'dwm');
  assert.equal(backOf('nonsense', '2026-11-18'), 'first');
});

test('the same day again is no first of anything', () => {
  assert.equal(backOf('2026-11-18', '2026-11-18'), 'today');
  assert.equal(freshOf('2026-11-18', '2026-11-18'), 'none');
});

test('how long since, in the bands the registry names', () => {
  assert.equal(backOf('2026-11-17', '2026-11-18'), 'day');
  assert.equal(backOf('2026-11-16', '2026-11-18'), 'week');
  assert.equal(backOf('2026-11-11', '2026-11-18'), 'week');
  assert.equal(backOf('2026-11-10', '2026-11-18'), 'month');
  assert.equal(backOf('2026-10-19', '2026-11-18'), 'month');
  assert.equal(backOf('2026-10-18', '2026-11-18'), 'more');
  assert.equal(backOf('2025-11-18', '2026-11-18'), 'more');
});

test('a day after today (the phone\'s clock moved back) is not read as a return', () => {
  assert.equal(backOf('2026-11-19', '2026-11-18'), 'unknown');
  assert.equal(freshOf('2026-11-19', '2026-11-18'), 'none');
});

test('the week starts on Monday', () => {
  // Sunday the 15th, then Monday the 16th: a new week.
  assert.equal(freshOf('2026-11-15', '2026-11-16'), 'dw');
  // Monday the 16th, then Sunday the 22nd: the same week.
  assert.equal(freshOf('2026-11-16', '2026-11-22'), 'd');
  // Sunday the 22nd, then Monday the 23rd.
  assert.equal(freshOf('2026-11-22', '2026-11-23'), 'dw');
});

test('the month starts on its first', () => {
  // Saturday 31 October, then Sunday 1 November: a new month in the same week (Monday 26 October).
  assert.equal(freshOf('2026-10-31', '2026-11-01'), 'dm');
  // Sunday 29 November, then Tuesday 1 December: a new week and a new month.
  assert.equal(freshOf('2026-11-29', '2026-12-01'), 'dwm');
  // Across a year.
  assert.equal(freshOf('2026-12-31', '2027-01-01'), 'dm');
  assert.equal(backOf('2026-12-31', '2027-01-01'), 'day');
  // A leap day.
  assert.equal(backOf('2028-02-28', '2028-03-01'), 'week');
  assert.equal(freshOf('2028-02-29', '2028-03-01'), 'dm');
});
