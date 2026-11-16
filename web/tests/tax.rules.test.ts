import { test } from 'node:test';
import assert from 'node:assert/strict';
import { allowanceCost, familyOff, pensionTax, rentTax, salaryTax, scaleTax } from '../src/topics/tax/rules/income.ts';
import { autoEntrepreneur, buyDuties, carTax, housingTax, landTax, lateCost, sellTax } from '../src/topics/tax/rules/things.ts';

// The rows of apps/topics/tax/rates.yaml (2026) and the work topic's CNSS row, as the tools read them.
const scale = { s1: 40000, s2: 60000, s3: 80000, s4: 100000, s5: 180000, r1: 10, r2: 20, r3: 30, r4: 34, r5: 37 };
const family2026 = { per: 600, max: 3600 };
const family2025 = { per: 500, max: 3000 };
const expenses = { low_rate: 35, threshold: 78000, high_rate: 25, cap: 35000 };
const cnss = { worker_long: 3.96, worker_short: 0.33, worker_ipe: 0.19, worker_amo: 2.26, ceiling: 6000 };
const pension2026 = { basic_exempt: 1, basic_reduction: 0, low_rate: 70, threshold: 168000, high_rate: 40, foreign_reduction: 80 };
const pension2025 = { ...pension2026, basic_exempt: 0, basic_reduction: 50 };

test('the scale taxes each slice at its own rate; the first 40,000 are exempt (art. 73-I)', () => {
  assert.equal(scaleTax(40000, scale).tax, 0);
  assert.equal(scaleTax(60000, scale).tax, 2000);
  // 2,000 + 4,000 + 6,000 + 27,200 + 37% of 20,000.
  assert.equal(scaleTax(200000, scale).tax, 46600);
  assert.equal(scaleTax(200000, scale).marginal, 37);
});

test('a raise never lowers the net: one dirham over a threshold pays the higher rate on that dirham only', () => {
  const a = salaryTax(9000, 0, { scale, family: family2026, expenses, cnss });
  const b = salaryTax(9001, 0, { scale, family: family2026, expenses, cnss });
  assert.ok(b.monthly.net > a.monthly.net);
});

test('10,000 a month, two dependents, 2026: expenses 25%, contributions, the scale, 1,200 off', () => {
  const s = salaryTax(10000, 2, { scale, family: family2026, expenses, cnss });
  assert.equal(s.expenses, 30000);
  assert.equal(s.cnss, 3225.6);
  assert.equal(s.amo, 2712);
  assert.equal(s.taxable, 84062.4);
  assert.equal(s.scale, 7218.72);
  assert.equal(s.family, 1200);
  assert.equal(s.tax, 6018.72);
  assert.equal(s.monthly.net, 9003.64);
});

test('the family deduction: 600 each, 3,600 at most in 2026; 500 and 3,000 in 2025; never more than the tax', () => {
  assert.equal(familyOff(7, family2026), 3600);
  assert.equal(familyOff(3, family2025), 1500);
  assert.equal(salaryTax(4000, 6, { scale, family: family2026, expenses, cnss }).tax, 0);
});

test('expenses: 35% up to 78,000 a year, 25% above and at most 35,000 (art. 59-I-A)', () => {
  assert.equal(salaryTax(6000, 0, { scale, family: family2026, expenses, cnss }).expenses, 25200);
  assert.equal(salaryTax(20000, 0, { scale, family: family2026, expenses, cnss }).expenses, 35000);
});

test('a basic scheme pension is exempt from 2026, half its tax off in 2025; a complementary one is abated', () => {
  assert.equal(pensionTax(120000, 'basic', 0, { scale, family: family2026, pension: pension2026 }).tax, 0);
  const y2025 = pensionTax(120000, 'basic', 0, { scale, family: family2025, pension: pension2025 });
  // 30% of 120,000 is taxable: 36,000, under the exempt slice.
  assert.equal(y2025.taxable, 36000);
  const other = pensionTax(240000, 'other', 0, { scale, family: family2026, pension: pension2026 });
  // Abatement 70% of 168,000 + 40% of 72,000 = 146,400; taxable 93,600.
  assert.equal(other.taxable, 93600);
  assert.equal(other.tax, 2000 + 4000 + 4080);
});

test('rent: 40% off, a company tenant withholds 10% under 120,000 and 15% above, the option 20%', () => {
  const r = rentTax(60000, { scale, rent: { abatement: 40, withhold_low: 10, withhold_high: 15, withhold_threshold: 120000, final: 20 } });
  assert.equal(r.net, 36000);
  assert.equal(r.withheld, 6000);
  assert.equal(r.final, 12000);
  assert.equal(rentTax(120000, { scale, rent: { abatement: 40, withhold_low: 10, withhold_high: 15, withhold_threshold: 120000, final: 20 } }).withheldRate, 15);
});

const local = { h1: 5000, h2: 20000, h3: 40000, r1: 10, r2: 20, r3: 30, abatement: 75, services_urban: 10.5, services_other: 6.5,
  land_full_min: 15, land_full_max: 30, land_mid_min: 5, land_mid_max: 15, land_low_min: 0.5, land_low_max: 2, land_floor: 200 };

test('the housing tax: 75% off a main home, then the scale; the services tax on the rental value', () => {
  const main = housingTax(24000, true, true, local);
  assert.equal(main.base, 6000);
  assert.equal(main.housing, 100);
  assert.equal(main.services, 2520);
  assert.equal(housingTax(24000, false, true, local).housing, 1500 + 800);
});

test('urban land: whole square metres between the zone\'s bounds; nothing under 200 dirhams', () => {
  const l = landTax(300.2, 'full', local);
  assert.equal(l.m2, 301);
  assert.equal(l.min, 4515);
  assert.equal(l.max, 9030);
  assert.equal(landTax(50, 'low', local).none, true);
});

const car = { petrol_lt8: 350, petrol_8_10: 650, petrol_11_14: 3000, petrol_15: 8000, diesel_lt8: 700, diesel_8_10: 1500, diesel_11_14: 6000, diesel_15: 20000 };
test('the vignette by horsepower and fuel; a diesel pick-up at the petrol tariff; a twelfth a month left', () => {
  assert.equal(carTax(6, 'diesel', false, null, car).year, 700);
  assert.equal(carTax(9, 'petrol', false, null, car).year, 650);
  assert.equal(carTax(12, 'diesel', true, null, car).year, 3000);
  assert.equal(carTax(6, 'diesel', false, 10, car).due, 175);
  assert.equal(carTax(6, 'electric', false, null, car).due, 0);
});

const property = { rate: 20, minimum: 3, costs: 15, home_years: 5, home_cap: 4000000, small: 140000, social_years: 4 };
test('a sale: 20% of the profit, at least 3% of the price; the main home after five years, 3% above 4 million', () => {
  const s = sellTax({ price: 1000000, bought: 600000, costs: null, works: 0, sellCosts: 0, years: 3, main: false, yearSales: 0 }, property);
  assert.equal(s.costs, 90000);
  assert.equal(s.profit, 310000);
  assert.equal(s.tax, 62000);
  const loss = sellTax({ price: 800000, bought: 800000, costs: null, works: 0, sellCosts: 0, years: 3, main: false, yearSales: 0 }, property);
  assert.equal(loss.case, 'minimum');
  assert.equal(loss.tax, 24000);
  assert.equal(sellTax({ price: 5000000, bought: 1000000, costs: null, works: 0, sellCosts: 0, years: 6, main: true, yearSales: 0 }, property).tax, 30000);
  assert.equal(sellTax({ price: 120000, bought: 50000, costs: null, works: 0, sellCosts: 0, years: 1, main: false, yearSales: 0 }, property).tax, 0);
});

test('registration duties: 4% built, 5% land, 1.5% a gift in the family', () => {
  const r = { built: 4, land: 5, social: 3, family_gift: 1.5, days: 30 };
  assert.equal(buyDuties(900000, 'built', r).duties, 36000);
  assert.equal(buyDuties(500000, 'land', r).duties, 25000);
  assert.equal(buyDuties(400000, 'family_gift', r).duties, 6000);
});

const own = { trade: 0.5, trade_cap: 500000, service: 1, service_cap: 200000, client: 80000, client_rate: 30,
  d1: 499, d2: 1000, d3: 2500, d4: 5000, d5: 10000, d6: 25000, d7: 50000, c1: 1200, c2: 1560, c3: 2280, c4: 2880, c5: 4200, c6: 6000, c7: 9000, c8: 14400 };
test('the auto-entrepreneur: 1% of services, the complementary duty by the tax, 30% on one client above 80,000', () => {
  const a = autoEntrepreneur(150000, 'service', 100000, own);
  assert.equal(a.tax, 1500);
  assert.equal(a.complementary, 2280);
  assert.equal(a.withheld, 6000);
  assert.equal(autoEntrepreneur(600000, 'trade', 0, own).over, true);
});

const late = { penalty: 10, penalty_30: 5, first_month: 5, per_month: 0.5, local_free: 1000, registration_min: 100 };
test('paying late: 5% within 30 days, else 10%; 5% the first month and 0.5% each month begun after', () => {
  const soon = lateCost(10000, '2026-03-01', '2026-03-20', 'state', late);
  assert.equal(soon.penalty, 500);
  assert.equal(soon.increase, 500);
  const later = lateCost(10000, '2026-03-01', '2026-06-15', 'state', late);
  assert.equal(later.months, 4);
  assert.equal(later.penalty, 1000);
  assert.equal(later.increase, 650);
  assert.equal(lateCost(900, '2026-03-01', '2026-09-01', 'local', late).total, 0);
});

// The 2027 bill's rows (apps/topics/tax/rates.yaml `bill-scale`, `bill-expenses`): a bill's, never law
// (the finance-bill review, P6). The claims page's figures rest on these tests.
const bill2027 = { s1: 60000, s2: 80000, s3: 100000, s4: 180000, s5: 180000, r1: 10, r2: 20, r3: 34, r4: 37, r5: 37 };
const bill2031 = { s1: 60000, s2: 150000, s3: 500000, s4: 500000, s5: 500000, r1: 10, r2: 20, r3: 30, r4: 30, r5: 30 };
const bill45 = { low_rate: 45, threshold: 0, high_rate: 45, cap: 35000 };
const now = { scale, family: family2026, expenses, cnss };
const in2027 = { scale: bill2027, family: family2026, expenses: bill45, cnss };
const in2031 = { scale: bill2031, family: family2026, expenses: bill45, cnss };

test('a bill scale with fewer slices draws none empty (247-XXXXVII for 2027)', () => {
  assert.deepEqual(scaleTax(200000, bill2027).slices.map((s) => s.rate), [0, 10, 20, 34, 37]);
});

test('the bill gains exactly 500 a month above 100,000 taxable a year in 2027 (the speech: «about 500»)', () => {
  for (const gross of [12000, 15000, 25000]) {
    const gain = salaryTax(gross, 0, now).monthly.tax - salaryTax(gross, 0, in2027).monthly.tax;
    assert.equal(Math.round(gain * 100) / 100, 500);
  }
  // Less below it: 442.71 at 10,000 gross.
  assert.equal(Math.round((salaryTax(10000, 0, now).monthly.tax - salaryTax(10000, 0, in2027).monthly.tax) * 100) / 100, 442.71);
});

test('no tax in 2027 up to 8,374 gross a month without dependents, not 10,000 net (the speech)', () => {
  assert.equal(salaryTax(8374, 0, in2027).monthly.tax, 0);
  assert.ok(salaryTax(8375, 0, in2027).monthly.tax > 0);
  assert.ok(salaryTax(11000, 0, in2027).monthly.tax > 0);
});

test('2031: read as gross salaries with no dependents, 11,829 and 18,737 would gain 677 and 2,038 (not the speech\'s reading)', () => {
  const gain = (g: number) => Math.round(salaryTax(g, 0, now).monthly.tax - salaryTax(g, 0, in2031).monthly.tax);
  assert.equal(gain(11829), 677);
  assert.equal(gain(18737), 2038);
});

test('2027: two dependents free to 9,397 gross; a net of almost 10,000 only with five (the claims page)', () => {
  const top = (k: number) => { let lo = 0, hi = 100000; while (hi - lo > 1) { const m = Math.floor((lo + hi) / 2); if (salaryTax(m, k, in2027).monthly.tax > 0) hi = m; else lo = m; } return lo; };
  assert.equal(top(2), 9397);
  assert.equal(salaryTax(top(5), 5, in2027).monthly.net, 9999.76);
  assert.equal(salaryTax(8374, 0, now).monthly.tax, 331.16);    // the whole of today's tax is the gain there
});

test('the speech\'s 1,186 and 3,079 are today\'s net salaries of 14,000 and 25,000 gross with three dependents (the claims page)', () => {
  for (const [gross, net, gain] of [[14000, 11829, 1186], [25000, 18737, 3079]]) {
    assert.equal(Math.round(salaryTax(gross, 3, now).monthly.net), net);
    assert.equal(Math.round(salaryTax(gross, 3, now).monthly.tax - salaryTax(gross, 3, in2031).monthly.tax), gain);
  }
});

test('the minister in committee (30 Oct): 10,506 gross pays 250 a month in 2027, and nets 10,000 with five dependents (the claims page)', () => {
  const alone = salaryTax(10506, 0, in2027);
  assert.equal(Math.round(alone.taxable * 100) / 100, 84997.17);
  assert.equal(alone.tax, 2999.43);
  assert.equal(alone.monthly.tax, 249.95);
  assert.ok(salaryTax(10506, 4, in2027).monthly.tax > 0);
  assert.equal(salaryTax(10506, 5, in2027).monthly.tax, 0);
  assert.equal(salaryTax(10506, 5, in2027).monthly.net, 9999.76);
  assert.equal(salaryTax(10506, 0, now).monthly.tax, 711.98);     // today's tax on the same salary
});

test('2027, three dependents (the speech\'s assumption): no tax to 9,909 gross, 9,416 net (the claims page)', () => {
  let lo = 0, hi = 100000; while (hi - lo > 1) { const m = Math.floor((lo + hi) / 2); if (salaryTax(m, 3, in2027).monthly.tax > 0) hi = m; else lo = m; }
  assert.equal(lo, 9909);
  assert.equal(Math.round(salaryTax(lo, 3, in2027).monthly.net), 9416);
});

test('2031: a month\'s allowance taxed as salary; at 10,000 gross, 1,000 more falls in the 10% slice (60,000 to 150,000): 100 a month', () => {
  assert.equal(allowanceCost(10000, 0, 0, in2031), 0);
  // 45% of 120,000 is past the 35,000 cap already, so the whole allowance is taxed: 12,000 a year at 10%.
  assert.equal(allowanceCost(10000, 1000, 0, in2031), 100);
  // Under the tax-free band nothing is due, allowance or not: 3,000 gross with 500 stays under 60,000 taxable.
  assert.equal(allowanceCost(3000, 500, 0, in2031), 0);
  // Never more than the allowance at the top rate.
  for (const [g, a] of [[6000, 800], [20000, 3000], [60000, 5000]]) assert.ok(allowanceCost(g, a, 2, in2031) <= a * 0.3 + 0.01);
});
