/** The road tools' rules (R11–R13 of the road plan), on written cases: each figure worked out by hand from its
 *  article, the amounts as rates.yaml gives them on 20 Oct 2026. */
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fine, OFFENCES } from '../src/topics/road/rules/fines.ts';
import { atOnce, balanceAfter, comesBack } from '../src/topics/road/rules/points.ts';
import { compensate, type Table } from '../src/topics/road/rules/compensation.ts';

const FINES = { c1_day: 400, c1_15: 500, c1_30: 700, c1_min: 700, c1_max: 1400, c2_day: 300, c2_15: 350, c2_30: 500, c2_min: 500,
  c2_max: 1000, c3_day: 150, c3_15: 200, c3_30: 300, c3_min: 300, c3_max: 600, walk_30: 25, walk_min: 20, walk_max: 50 };
const off = (k: string) => OFFENCES.find((o) => o.key === k)!;

test('a radar notice served on 26 Oct 2026, +25 km/h: 300 until the 27th, 350 until 11 Nov, 500 until 25 Nov (arts 185, 219, 222)', () => {
  const r = fine(off('speed20'), 'radar', '2026-10-26', FINES);
  assert.deepEqual(r.steps.map((s) => [s.amount, s.until]), [[300, '2026-10-27'], [350, '2026-11-11'], [500, '2026-11-25']]);
  assert.equal(r.deposit, 1000);                 // the maximum of art. 185, to contest (art. 231)
  assert.equal(r.points, 2);                     // art. 99 row 28
  assert.equal(r.contestBy, '2026-11-25');
});

test('a red light seen by an officer on 20 Oct 2026: 400 that day, 500 until 4 Nov, 700 until 19 Nov (arts 184, 219, 221)', () => {
  const r = fine(off('redLight'), 'officer', '2026-10-20', FINES);
  assert.deepEqual(r.steps.map((s) => [s.amount, s.until]), [[400, '2026-10-20'], [500, '2026-11-04'], [700, '2026-11-19']]);
  assert.equal(r.twoThirds, 933);                // two thirds of 1,400 (art. 234)
  assert.equal(r.points, 4);
  assert.ok(r.cites.includes('/ma/loi/52-05/art_28'));
});

test('a pedestrian pays 25 dirhams within the 30 days, no reduced price (arts 187, 219)', () => {
  const r = fine(off('walk'), 'officer', '2026-10-20', FINES);
  assert.deepEqual(r.steps.map((s) => s.amount), [25]);
  assert.equal(r.deposit, 50);
  assert.equal(r.points, 0);
});

test('several offences at once: 8 points at most, 10 for délits, 14 with one délit among them (art. 100)', () => {
  const c = (points: number) => ({ points, delit: false });
  const d = (points: number, aggravated = false) => ({ points, delit: true, aggravated });
  assert.deepEqual(atOnce([c(4), c(1), c(1), c(4)]), { total: 8, cap: 8 });
  assert.deepEqual(atOnce([d(6), d(6)]), { total: 10, cap: 10 });
  assert.deepEqual(atOnce([d(6, true), d(6), d(6)]), { total: 16, cap: 16 });
  assert.deepEqual(atOnce([d(6), c(4), c(4), c(4)]), { total: 14, cap: 14 });
  assert.deepEqual(atOnce([c(2)]), { total: 2, cap: null });
});

test('points come back: +4 after a year, 12 after two if under 8, the full 30 after three (art. 35)', () => {
  assert.deepEqual(comesBack(22, 30).map((b) => [b.years, b.balance]), [[1, 26], [3, 30]]);
  assert.deepEqual(comesBack(2, 30).map((b) => [b.years, b.balance]), [[1, 6], [2, 12], [3, 30]]);
  assert.deepEqual(comesBack(10, 20).map((b) => [b.years, b.balance]), [[1, 14], [3, 30]]);
  // Only the years that change something: 28 of 30 is full after one year.
  assert.deepEqual(comesBack(28, 30).map((b) => [b.years, b.balance]), [[1, 30]]);
  assert.deepEqual(comesBack(0, 30), []);
});

test('the balance after some years, and the course\'s +4 once, never above the maximum (arts 33, 35)', () => {
  assert.equal(balanceAfter(2, 30, 0), 2);
  assert.equal(balanceAfter(2, 30, 1), 6);
  assert.equal(balanceAfter(2, 30, 2), 12);
  assert.equal(balanceAfter(2, 30, 2, true), 16);
  assert.equal(balanceAfter(28, 30, 0, true), 30);
  assert.equal(balanceAfter(10, 20, 2, true), 18);
  assert.equal(balanceAfter(10, 20, 3), 30);
  assert.equal(balanceAfter(0, 30, 3), 0);
});

const table = JSON.parse(readFileSync(new URL('../../back/apps/topics/road/compensation.json', import.meta.url), 'utf8')) as Table;

test('the capital by age and earnings: a row read as printed, and between rows by art. 5\'s formula', () => {
  // 30,000 a year at 35, an accident in 2026: the row 30,000 of p. 853 (age 35 is in the 30–41 band).
  const exact = compensate(table, '2026-03-01', 35, 30000, 10);
  assert.equal(exact.rows.length, 1);
  assert.equal(exact.rows[0].page, 853);
  assert.equal(exact.indemnity, Math.round((exact.capital / 100) * 10));
  // 31,500 lies between 30,000 and 33,000: capital1 + (31,500 − 30,000) / (33,000 − 30,000) × (capital2 − capital1).
  const between = compensate(table, '2026-03-01', 35, 31500, 10);
  const [lo, hi] = between.rows;
  assert.equal(between.capital, Math.round(lo.capital + 0.5 * (hi.capital - lo.capital)));
});

test('no proven income: the minimum row of the accident\'s year, 10,270 in 2026 and 11,270 in 2027 (70.24 art. 5)', () => {
  assert.equal(compensate(table, '2026-03-01', 18, 0, 10).minimum, 10270);
  assert.equal(compensate(table, '2026-03-01', 18, 0, 10).capital, 157310);
  assert.equal(compensate(table, '2027-02-01', 18, 0, 10).minimum, 11270);
  // A point is never worth less than a fifth of the minimum (art. 5): 2,054 dirhams in 2026.
  assert.equal(compensate(table, '2026-03-01', 63, 0, 10).pointFloor, 2054);
});

test('a cell the BO misprinted is used as printed and named (66,000 at 41, p. 853)', () => {
  const r = compensate(table, '2026-03-01', 41, 66000, 10);
  assert.equal(r.capital, 369145);
  assert.equal(r.misprint?.steps, 359145);
});

test('a recorded speed against the limit: the margin of art. 195 read as 10 % of the limit, at most 7 (call K1)', async () => {
  const { classify, marginFor } = await import('../src/topics/road/rules/speed.ts');
  assert.equal(marginFor(60), 6);
  assert.equal(marginFor(120), 7);                 // 12 would pass the 7 km/h cap
  assert.equal(classify(60, 60).band, 'within');
  assert.equal(classify(60, 66).band, 'margin');   // 66 − 6 = 60: within the margin
  assert.equal(classify(60, 80).band, 'under20');  // kept 74: +14, no class in arts 184–185 (call K4)
  const c2 = classify(60, 86);                     // kept 80: +20
  assert.deepEqual([c2.band, c2.offence, c2.points], ['c2', 'speed20', 2]);
  assert.equal(classify(60, 95).band, 'c2');       // kept 89: +29, still the 2nd class
  assert.equal(classify(60, 96).band, 'c1');       // kept 90: +30
  const d = classify(120, 177);                    // kept 170: +50
  assert.deepEqual([d.band, d.points], ['delit', 6]);
  assert.equal(classify(60, 86, false).band, 'c2'); // an officer's reading has no device margin: +26
});

test('practice on the phone: a missed card comes back first, a known one waits longer (the Leitner box)', async () => {
  const { order, shuffled } = await import('../src/topics/road/practice.ts');
  const cards = [{ key: 'a' }, { key: 'b' }, { key: 'c' }];
  // a: known twice (box 3, seen at turn 1) waits 4 turns; b missed (box 1); c never seen.
  const boxes = { a: { box: 3, seen: 1 }, b: { box: 1, seen: 1 } };
  assert.deepEqual(order(cards, boxes, 2).map((c) => c.key), ['c', 'b', 'a']);
  assert.deepEqual(order(cards, boxes, 6).map((c) => c.key), ['c', 'b', 'a']);
  assert.equal(order([{ key: 'a' }], { a: { box: 3, seen: 1 } }, 5)[0].key, 'a');
  // A shuffle is the same for the same card and turn, and keeps every choice.
  assert.deepEqual(shuffled([1, 2, 3], 'x1'), shuffled([1, 2, 3], 'x1'));
  assert.deepEqual([...shuffled([1, 2, 3], 'y')].sort(), [1, 2, 3]);
});

test('search names the offence a price question asks about, and none when it is not about a price', async () => {
  const { offenceIn } = await import('../src/topics/road/answer.ts');
  const words: Record<string, string> = { phone: 'التيليفون الهاتف téléphone', belt: 'السمطة الحزام ceinture', redLight: 'الضو الحمر feu rouge' };
  const w = (o: { key: string }) => words[o.key] ?? '';
  assert.equal(offenceIn('شحال المخالفة ديال التيليفون', w)?.key, 'phone');
  assert.equal(offenceIn('combien amende ceinture', w)?.key, 'belt');
  assert.equal(offenceIn('التيليفون فالسياقة', w), null);       // no price asked
  assert.equal(offenceIn('شحال الثمن', w), null);                // no offence named
});
