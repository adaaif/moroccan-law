/** The work tools' rules (T8–T11 of the work plan), on written cases: each figure worked out by hand from its article
 *  and decree, the rates as rates.yaml gives them on 20 Oct 2026. */
import test from 'node:test';
import assert from 'node:assert/strict';
import { endOfContract, months, noticeOf, severanceHours, stairs, startFor, type EndInput } from '../src/topics/work/rules/end.ts';
import { leaveDays, minimumMonthly, overtimePay, payslip, seniorityRate, workerShares } from '../src/topics/work/rules/pay.ts';
import { allowance, pension } from '../src/topics/work/rules/cnss.ts';
import { due } from '../src/topics/kit/dates.ts';
import { EVENTS } from '../src/topics/work/rules/dates.ts';

const NOTICE = { cadre_under1_months: 1, cadre_1to5_months: 2, cadre_over5_months: 3, worker_under1_days: 8, worker_1to5_months: 1, worker_over5_months: 2 };
const RATES = { notice: NOTICE, smigHour: 17.92, smagDay: 97.44 };
const CNSS = { worker_long: 3.96, worker_short: 0.33, worker_ipe: 0.19, worker_amo: 2.26, ceiling: 6000 };
const PENSION = { min_days: 1320, full_days: 3240, base_rate: 50, step_days: 216, step_rate: 1, max_rate: 70, ceiling: 6000,
  floor_1320: 600, floor_1705: 700, floor_2089: 800, floor_2473: 900, floor_2857: 1000 };
const IPE = { days_36_months: 780, days_12_months: 260, rate: 70, months: 6 };
const base: EndInput = { start: '2019-03-15', end: '2026-03-14', category: 'employee', farm: false, monthly: 4000,
  noticeGiven: false, leaveDays: 10, delegate: false, ending: 'dismissed' };
const byKey = (i: EndInput) => Object.fromEntries(endOfContract(i, RATES).map((l) => [l.key, l]));

test('the plan\'s example: seven years, 4,000 DH, dismissed without notice or fault (arts 41, 51–53, 251)', () => {
  assert.equal(months(base.start, base.end), 84);
  const l = byKey(base);
  assert.equal(l.notice.amount, 8000);                    // two months: over five years (decree 2.04.469)
  assert.equal(l.severance.detail.hours, 768);            // 5 × 96 + 2 × 144
  assert.equal(l.severance.amount, 16083.77);              // 768 × 4,000 ÷ 191
  assert.equal(l.leave.amount, 1538.46);                   // 10 × 4,000 ÷ 26
  assert.equal(l.damages.amount, 42000);                   // 7 × 1.5 × 4,000, if a court finds it abusive
  assert.ok(l.damages.conditional && Object.values(l).every((x) => x.applies));
});

test('severance by band, by the month: 16 years are 2,400 hours; a delegate\'s doubled (arts 53, 58)', () => {
  assert.equal(severanceHours(16 * 12), 5 * 96 + 5 * 144 + 5 * 192 + 240);
  assert.equal(severanceHours(18), 96 + 48);
  assert.equal(byKey({ ...base, delegate: true }).severance.detail.hours, 1536);
});

test('the wage it counts on is never under the minimum of the day (art. 56)', () => {
  const l = byKey({ ...base, monthly: 2500 });
  assert.equal(l.severance.detail.hourly, 17.92);
  assert.equal(l.severance.detail.floored, 1);
  assert.equal(byKey({ ...base, farm: true, monthly: 2000 }).severance.detail.hourly, 12.18);   // 97.44 ÷ 8
});

test('what does not apply says why: under six months, serious fault, resignation (arts 52, 61, 34)', () => {
  const young = byKey({ ...base, start: '2026-01-01', end: '2026-05-31' });
  assert.equal(young.severance.applies, false);
  assert.equal(young.severance.why, 'underSix');
  assert.equal(young.notice.detail.days, 8);
  assert.equal(young.notice.amount, 1230.77);              // 8 days × 4,000 ÷ 26
  const fault = byKey({ ...base, ending: 'seriousFault' });
  assert.deepEqual([fault.notice.applies, fault.severance.applies, fault.damages.applies, fault.leave.applies], [false, false, false, true]);
  assert.equal(byKey({ ...base, ending: 'resigned' }).notice.why, 'resignedOwes');
});

test('notice by seniority and category, and damages capped at 36 months (decree 2.04.469, art. 41)', () => {
  assert.deepEqual(noticeOf('cadre', 6, NOTICE), { months: 1 });
  assert.deepEqual(noticeOf('cadre', 60, NOTICE), { months: 2 });
  assert.deepEqual(noticeOf('worker', 61, NOTICE), { months: 2 });
  assert.equal(byKey({ ...base, start: '1990-01-01', end: '2026-01-01' }).damages.amount, 36 * 4000);
});

test('pay: the minimum by sector, seniority, overtime, leave, the payslip\'s shares', () => {
  assert.equal(minimumMonthly('nonfarm', 17.92, 97.44), 3422.72);   // the CNSS's own monthly figure
  assert.equal(minimumMonthly('farm', 17.92, 97.44), 2533.44);
  assert.equal(minimumMonthly('home', 17.92, 97.44), 2053.63);      // 60% (law 19.12, art. 19)
  assert.deepEqual([1, 2, 4, 5, 12, 20, 25, 40].map(seniorityRate), [0, 5, 5, 10, 15, 20, 25, 25]);
  assert.equal(overtimePay(20, 4, false, false), 100);               // +25%
  assert.equal(overtimePay(20, 4, true, true), 160);                 // night on the rest day: +100%
  assert.deepEqual([3, 6, 12, 60, 300].map((m) => leaveDays(m, false)), [0, 9, 18, 19.5, 25.5]);
  assert.equal(leaveDays(12, true), 24);
  assert.deepEqual(workerShares(8000, CNSS), { long: 237.6, short: 19.8, ipe: 11.4, amo: 180.8, total: 449.6 });
});

test('the CNSS pension: the decree\'s formula, its floors, 70% at most; refund under 1,320 days', () => {
  assert.equal(pension(1000, 4000, PENSION).eligible, false);
  assert.deepEqual(pension(2000, 4000, PENSION), { eligible: true, rate: 30.86, formula: 1234.4, floor: 700, amount: 1234.4, base: 4000 });
  assert.equal(pension(1500, 1500, PENSION).amount, 600);           // 23.14% of 1,500 is under the floor
  assert.equal(pension(5000, 8000, PENSION).rate, 58);              // 50 + ⌊1,760 ÷ 216⌋, on the 6,000 ceiling
  assert.equal(pension(5000, 8000, PENSION).amount, 3480);
  assert.equal(pension(20000, 6000, PENSION).rate, 70);
});

test('the job-loss allowance: the days missing named, 70% capped at the minimum', () => {
  const a = allowance(800, 270, true, true, 5000, 3422.72, IPE);
  assert.deepEqual([a.open, a.amount, a.months], [true, 3422.72, 6]);
  const b = allowance(700, 200, true, true, 3000, 3422.72, IPE);
  assert.deepEqual([b.open, b.missing36, b.missing12, b.amount], [false, 80, 60, 2100]);
  assert.equal(allowance(900, 300, false, true, 3000, 3422.72, IPE).open, false);
});

test('dates: the Code\'s limits from the next day; a court\'s complete, past a weekend (law 58.25, art. 602)', () => {
  const find = (e: string, k: string) => EVENTS.find((x) => x.key === e)!.deadlines.find((d) => d.key === k)!;
  assert.equal(due('2026-10-19', find('dismissal', 'sue')), '2027-01-17');
  assert.equal(due('2026-10-19', find('accident', 'tellEmployer')), '2026-10-21');
  assert.equal(due('2026-10-19', find('judgment', 'appeal')), '2026-11-19');       // a Thursday
  assert.equal(due('2026-10-14', find('judgment', 'appeal')), '2026-11-16');       // 14 Nov is a Saturday: Monday
});

/** The ministry's simulator (miepeec.gov.ma/simulation/?lang=ar), as its page publishes its formulas (read 20 Oct 2026):
 *  hourly = monthly ÷ 191; severance 96 × years, then (96×5) + 144 × (years − 5), …; damages 1.5 × monthly × years,
 *  36 months at most; leave days × monthly ÷ 26; notice months × monthly, or days × monthly ÷ 26. */
function ministry(monthly: number, years: number, leaveDays: number, notice: { months?: number; days?: number }) {
  const sh = monthly / 191;
  const hours = years <= 5 ? 96 * years : years <= 10 ? 96 * 5 + 144 * (years - 5)
    : years <= 15 ? 96 * 5 + 144 * 5 + 192 * (years - 10) : 96 * 5 + 144 * 5 + 192 * 5 + 240 * (years - 15);
  return { severance: hours * sh, damages: Math.min(1.5 * monthly * years, 36 * monthly), leave: (leaveDays * monthly) / 26,
    notice: notice.months ? notice.months * monthly : ((notice.days ?? 0) * monthly) / 26 };
}

test('every sum agrees with the ministry\'s published formulas, whole years from 1 to 30, three wages', () => {
  for (const monthly of [3422.72, 6000, 15000]) {
    for (let years = 1; years <= 30; years++) {
      const start = `${2026 - years}-01-01`;
      const i: EndInput = { ...base, start, end: '2025-12-31', monthly, leaveDays: 9, category: years % 3 ? 'employee' : 'cadre' };
      const l = byKey(i);
      const m = ministry(monthly, years, 9, noticeOf(i.category, years * 12, NOTICE));
      for (const k of ['severance', 'damages', 'leave', 'notice'] as const) {
        assert.ok(Math.abs(l[k].amount - m[k]) < 0.02, `${k}, ${years} years, ${monthly} DH: ${l[k].amount} vs ${m[k]}`);
      }
    }
  }
});

test('a service in months starts where months() counts it back (E13 of the work-counted review)', () => {
  for (const [end, n] of [['2026-10-26', 88], ['2026-03-31', 1], ['2026-02-28', 12], ['2024-02-29', 49], ['2026-12-31', 0], ['2026-01-15', 300]] as const) {
    assert.equal(months(startFor(end, n), end), n, `${end} ${n}`);
  }
});

test('art. 53 drawn as stairs adds up to severanceHours (E13)', () => {
  for (const n of [0, 6, 11, 12, 60, 61, 88, 120, 121, 180, 181, 245]) {
    const sum = stairs(n).reduce((a, s) => a + s.hours, 0);
    assert.ok(Math.abs(sum - severanceHours(n)) < 0.05, `${n}: ${sum} vs ${severanceHours(n)}`);
  }
  assert.deepEqual(stairs(88).map((s) => [s.band, s.months]), [[96, 12], [96, 12], [96, 12], [96, 12], [96, 12], [144, 12], [144, 12], [144, 4]]);
});

test('the payslip the law writes: the review\'s example (E14 of the work-counted review)', () => {
  const cnss = { worker_long: 3.96, worker_short: 0.33, worker_ipe: 0.19, worker_amo: 2.26, ceiling: 6000 };
  const p = payslip({ sector: 'nonfarm', hoursWeek: 44, base: 3800, years: 6, overtime: 6, kind: 'day' }, { smigHour: 17.92, smagDay: 97.44, homeShare: 60, cnss });
  assert.equal(p.seniority, 380);
  assert.equal(p.overtime, 149.21);
  assert.equal(p.gross, 4329.21);
  assert.equal(p.cnss, 193.95);
  assert.equal(p.amo, 97.84);
  assert.equal(p.net, 4037.42);
  assert.equal(p.minimum, 3422.72);
  assert.equal(p.cnssRate, 4.48);
  // Above the ceiling only AMO grows; at home no overtime.
  const high = payslip({ sector: 'nonfarm', hoursWeek: 44, base: 9000, years: 0, overtime: 0, kind: 'day' }, { smigHour: 17.92, smagDay: 97.44, homeShare: 60, cnss });
  assert.equal(high.cnss, 268.8);
  const home = payslip({ sector: 'home', hoursWeek: 48, base: 2100, years: 3, overtime: 5, kind: 'night' }, { smigHour: 17.92, smagDay: 97.44, homeShare: 60, cnss });
  assert.equal(home.overtime, 0);
  assert.equal(home.minimum, 2053.63);
});
