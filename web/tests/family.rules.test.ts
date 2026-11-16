// The dates and the support amounts (F7, F10 of the family plan) against the texts' own numbers.
import test from 'node:test';
import assert from 'node:assert/strict';
import { due, EVENTS } from '../src/topics/family/dates/rules.ts';
import { periodOn, support, type Child } from '../src/topics/family/support/rules.ts';

const find = (e: string, k: string) => EVENTS.find((x) => x.key === e)!.deadlines.find((d) => d.key === k)!;

test('a birth on 19 Oct 2026: declared by 19 Nov (18 Nov is Independence Day), a year abroad, the grant by 19 Apr 2027', () => {
  assert.equal(due('2026-10-19', find('birth', 'declareBirth')), '2026-11-19');
  assert.equal(due('2026-10-19', find('birth', 'declareBirthAbroad')), '2027-10-19');
  assert.equal(due('2026-10-19', find('birth', 'birthGrant')), '2027-04-19');
});

test('a widow’s waiting period is four months and ten days (art. 132)', () => {
  assert.equal(due('2026-01-10', find('death', 'widowIddah')), '2026-05-20');
});

test('a month without the day ends on its last day', () => {
  assert.equal(due('2026-08-31', find('shiqaq', 'shiqaqJudgment')), '2027-02-28');
});

test('every limit names its article', () => {
  for (const e of EVENTS) for (const d of e.deadlines) assert.match(d.path, /^\/ma\/(loi|decret)\/[\d-]+\/art_\d+$/);
});

const kid = (status: Child['status'], extra: Partial<Child> = {}): Child => ({ status, level: 'none', disabled: false, orphan: false, ...extra });

test('2026: three schooled children are 900 DH, the fourth 36 more (annex of decree 2.23.1067)', () => {
  assert.equal(support([kid('schooled'), kid('schooled'), kid('schooled')], '2026').monthly, 900);
  assert.equal(support([kid('schooled'), kid('schooled'), kid('schooled'), kid('schooled')], '2026').monthly, 936);
});

test('a family is never paid under 500 DH, and one without children gets the flat 500', () => {
  const one = support([kid('notSchooled')], '2026');
  assert.equal(one.monthly, 500);
  assert.ok(one.raised);
  assert.ok(support([], '2026').flat);
});

test('the supplement counts three disabled or fatherless children at most', () => {
  const kids = [1, 2, 3, 4].map(() => kid('schooled', { orphan: true }));
  assert.equal(support(kids, '2026').supplement, 3);
  assert.equal(support(kids, '2026').monthly, 3 * 300 + 36 + 3 * 100);
});

test('the September grant is apart from the monthly amount', () => {
  const s = support([kid('schooled', { level: 'primary' }), kid('schooled', { level: 'upper' })], '2026');
  assert.equal(s.september.total, 500);
  assert.equal(s.monthly, 600);
});

test('the period follows the date', () => {
  assert.equal(periodOn('2024-06-01'), '2023');
  assert.equal(periodOn('2025-03-01'), '2025');
  assert.equal(periodOn('2026-10-20'), '2026');
});

// U12 of the Moroccan-design review: the public holidays of decree 2.77.169 inside the deadlines.
test('a declaration whose last day is a public holiday or a weekend moves to the next working day', async () => {
  const { ending } = await import('../src/topics/kit/dates.ts');
  const { holiday } = await import('../src/topics/kit/holidays.ts');
  assert.equal(holiday('2026-11-18')?.key, 'independence');
  assert.equal(holiday('2025-10-31'), null);                         // the Unity day counts from 2026
  assert.equal(holiday('2026-10-31')?.key, 'unity');
  assert.equal(holiday('2023-01-14'), null);                         // the Amazigh new year from 2024
  assert.deepEqual(holiday('2026-05-27'), { key: 'adha', expected: true });
  // A birth on 19 Oct 2026: 30 days end on Wed 18 Nov, Independence Day; the declaration runs to Thu 19 Nov.
  const birth = ending('2026-10-19', { key: 'b', days: 30, rolls: true, path: '', label: '' });
  assert.equal(birth.date, '2026-11-19');
  assert.deepEqual(birth.moved.map((h) => h.key), ['independence']);
  // An ordinary limit stays on the holiday and says so.
  const plain = ending('2026-10-19', { key: 'p', days: 30, path: '', label: '' });
  assert.equal(plain.date, '2026-11-18');
  assert.equal(plain.on?.key, 'independence');
  // A complete limit past the two days of al-Adha (27–28 May 2026, expected) and the weekend.
  const court = ending('2026-05-11', { key: 'c', days: 15, complete: true, path: '', label: '' });
  assert.equal(court.date, '2026-05-29');
  assert.deepEqual(court.moved.map((h) => h.key), ['adha', 'adha']);
});
