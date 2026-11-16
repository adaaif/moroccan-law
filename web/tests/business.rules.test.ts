import { test } from 'node:test';
import assert from 'node:assert/strict';
import { EXCLUDED, find } from '../src/topics/business/rules/excluded.ts';
import { forms } from '../src/topics/business/rules/form.ts';
import { presentBy, recoveryFine, road, settleFine } from '../src/topics/business/rules/cheque.ts';
import { due, fine, monthsLate, start } from '../src/topics/business/rules/late.ts';
import { fromClose, fromCreation } from '../src/topics/business/rules/year.ts';

test('decree 2.15.263 lists 41 trades, found by a word of theirs', () => {
  assert.equal(EXCLUDED.length, 41);
  assert.ok(find('الأطباء').includes('الأطباء'));
  assert.ok(find('طبيب').includes('الأطباء'));
  assert.ok(find('bijoutier').includes('تجار التفصيل في الذهب والحلي والمجوهرات'));
  assert.ok(find('auto-école').includes('مستغلو مؤسسات تعليم سياقة السيارات'));
  assert.ok(find('محامي').includes('المحامون'));
  assert.ok(find('ذهب').includes('تجار التفصيل في الذهب والحلي والمجوهرات'));
  assert.deepEqual(find('حلاق'), []);
});

test('the forms the law allows: alone, the ceiling, the trade, five members (114.13 art. 1, 112.12 art. 14)', () => {
  const open = (o: ReturnType<typeof forms>) => o.filter((x) => x.open).map((x) => x.form);
  assert.deepEqual(open(forms('alone', 'service', 150_000, false)), ['auto', 'trader', 'sarl']);
  assert.equal(forms('alone', 'service', 250_000, false)[0].why, 'ceiling');
  assert.deepEqual(open(forms('alone', 'trade', 450_000, false)), ['auto', 'trader', 'sarl']);
  assert.equal(forms('alone', 'trade', 100_000, true)[0].why, 'trade');
  assert.deepEqual(open(forms('few', 'trade', 100_000, false)), ['sarl']);
  assert.deepEqual(open(forms('five', 'trade', 100_000, false)), ['sarl', 'coop']);
});

test('a cheque is presented within 20 days in Morocco, 60 from abroad (art. 268)', () => {
  assert.equal(presentBy('2026-10-01', 'morocco'), '2026-10-21');
  assert.equal(presentBy('2026-10-01', 'abroad'), '2026-11-30');
});

test('the cheque road: injunction in two days, three months free, a year against the drawer (arts 313, 314, 295)', () => {
  const r = Object.fromEntries(road('2026-10-01', 'morocco', '2026-10-05').map((s) => [s.key, s.date]));
  assert.equal(r.injunction, '2026-10-07');
  assert.equal(r.free, '2027-01-05');
  assert.equal(r.drawer, '2027-10-21');
  assert.equal(r.bank, '2028-10-21');
  assert.equal(r.recover, '2028-10-21');
});

test('the fine to issue cheques again: 0.5, 1, 1.5 %, between 500 and 50,000, none within three months (art. 314)', () => {
  assert.equal(recoveryFine(20_000, 1, false), 500);
  assert.equal(recoveryFine(200_000, 1, false), 1_000);
  assert.equal(recoveryFine(200_000, 3, false), 3_000);
  assert.equal(recoveryFine(10_000_000, 3, false), 50_000);
  assert.equal(recoveryFine(200_000, 2, true), 0);
  assert.equal(settleFine(20_000), 400);
});

test('payment terms: 60 days, 120 at most, from the end of the delivery month when invoiced late (art. 78-2)', () => {
  assert.equal(due('2026-03-10', null, null), '2026-05-09');
  assert.equal(due('2026-03-10', null, 200), '2026-07-08');
  assert.equal(start('2026-04-15', '2026-03-20'), '2026-03-31');
  assert.equal(start('2026-03-25', '2026-03-20'), '2026-03-25');
});

test('the fine: the key rate the first month, 0.85 % each further month or part (art. 78-3)', () => {
  assert.equal(monthsLate('2026-05-09', '2026-05-09'), 0);
  assert.equal(monthsLate('2026-05-09', '2026-05-20'), 1);
  assert.equal(monthsLate('2026-05-09', '2026-06-09'), 1);
  assert.equal(monthsLate('2026-05-09', '2026-06-10'), 2);
  assert.deepEqual(fine(100_000, 3, 2.25), { first: 2_250, rest: 1_700, total: 3_950 });
});

test('the company year: 30 days, three months, five years; three months and six after the close', () => {
  const c = Object.fromEntries(fromCreation('2026-01-15', '2026-02-10').map((s) => [s.key, s.date]));
  assert.deepEqual([c.declare, c.register, c.capital], ['2026-02-14', '2026-04-15', '2031-02-10']);
  const y = Object.fromEntries(fromClose('2025-12-31').map((s) => [s.key, s.date]));
  assert.deepEqual([y.taxReturn, y.assembly, y.papers], ['2026-03-31', '2026-06-30', '2026-06-15']);
});
