/** The housing tools' rules (H10–H13 of the housing plan), on written cases: each figure worked out by hand from its
 *  article, the rates as rates.yaml gives them on 20 Oct 2026. */
import test from 'node:test';
import assert from 'node:assert/strict';
import { depositCheck, rentCheck } from '../src/topics/housing/rules/rent.ts';
import { noticeCheck, type NoticeInput } from '../src/topics/housing/rules/eviction.ts';
import { capAt, delayPenalty, offplan } from '../src/topics/housing/rules/offplan.ts';
import { aid, type AidInput } from '../src/topics/housing/rules/aid.ts';

const REVISION = { home: 8, professional: 10, commercial: 10, years: 3, small_rent: 400, small_cap: 50, claim_months: 3, appeal_days: 30 };
const DEPOSIT = { max_months: 2, return_months: 1 };
const HOME = { notice_months: 2, owned_months: 18, indemnity_months: 12, false_reason_months: 12, return_months: 2 };
const SHOP = { shop_short_days: 15, shop_long_months: 3, shop_years: 2, shop_lapse_months: 6, shop_rebuild_years_rent: 3 };
const OFFPLAN = { reservation: 5, preliminary: 5, preliminary_alone: 10, start: 10, works: 60, keys: 20, penalty_month: 1,
  penalty_year: 10, rescission: 20, extension_months: 6, register_above: 50, withdraw_months: 1, refund_days: 7 };
const AID = { low_price: 300000, low_aid: 100000, high_price: 700000, high_aid: 70000, years: 5, deed_days: 60, release_days: 30 };

test('a home\'s rent: three years, then 8% at most (67.12 arts 32–34)', () => {
  const r = rentCheck({ kind: 'home', rent: 2500, proposed: 2800, since: '2023-09-01', on: '2026-10-20' }, REVISION);
  assert.equal(r.earliest, '2026-09-01');
  assert.equal(r.max, 2700);                     // 2,500 × 1.08
  assert.equal(r.increase, 12);
  assert.equal(r.verdict, 'tooHigh');
  assert.equal(rentCheck({ kind: 'home', rent: 2500, proposed: 2700, since: '2023-09-01', on: '2026-10-20' }, REVISION).verdict, 'within');
  assert.equal(rentCheck({ kind: 'home', rent: 2500, proposed: 2600, since: '2024-01-01', on: '2026-10-20' }, REVISION).verdict, 'tooEarly');
  // No current rent, no rise to measure (PX37 of the where-it-trips review: 3,000 DH on nothing read «within», 0 %).
  assert.equal(rentCheck({ kind: 'home', rent: 0, proposed: 3000, since: '2020-01-01', on: '2026-10-20' }, REVISION).verdict, 'none');
});

test('professional premises and shops: 10%; a rent of 400 DH or less, up to 50% by a court (67.12 art 35, 07.03 art 5)', () => {
  assert.equal(rentCheck({ kind: 'professional', rent: 3000, proposed: 0, since: '2020-01-01', on: '2026-10-20' }, REVISION).max, 3300);
  const small = rentCheck({ kind: 'commercial', rent: 400, proposed: 0, since: '2020-01-01', on: '2026-10-20' }, REVISION);
  assert.ok(small.small);
  assert.equal(small.courtMax, 600);
  assert.ok(small.cites.includes('/ma/loi/7-03/art_5'));
});

test('the deposit: two months at most, back within a month of the return (67.12 art 20)', () => {
  const d = depositCheck(2500, 7500, '2026-10-31', DEPOSIT);
  assert.equal(d.max, 5000);
  assert.ok(d.over);
  assert.equal(d.returnBy, '2026-11-30');        // a month without the 31st ends on its last day
});

const notice: NoticeInput = { premises: 'home', reason: 'live', dated: '2026-09-01', received: '2026-09-03', months: 2, days: 0,
  reasonStated: true, wholePremises: true, ownedSince: '2024-01-15', offeredSimilar: false, rent: 2500, tenantSince: '' };

test('a home\'s notice to live in it: two months from receipt, 18 months owned, a year of rent if validated (arts 45–51)', () => {
  const r = noticeCheck(notice, { home: HOME, shop: SHOP });
  assert.ok(r.valid);
  assert.equal(r.leaveBy, '2026-11-03');
  assert.equal(r.sums.find((s) => s.key === 'yearOfRent')!.amount, 30000);
  const young = noticeCheck({ ...notice, ownedSince: '2025-06-01' }, { home: HOME, shop: SHOP });
  assert.equal(young.checks.find((c) => c.key === 'owned')!.met, false);
  assert.ok(noticeCheck({ ...notice, ownedSince: '2025-06-01', offeredSimilar: true }, { home: HOME, shop: SHOP }).valid);
  // A tenant who does not know since when the landlord owns the house: neither met nor missed, and not a defect (HM15).
  const unknown = noticeCheck({ ...notice, ownedSince: '' }, { home: HOME, shop: SHOP });
  assert.equal(unknown.checks.find((c) => c.key === 'owned')!.met, null);
  assert.ok(unknown.valid);
  const short = noticeCheck({ ...notice, months: 1 }, { home: HOME, shop: SHOP });
  assert.equal(short.checks.find((c) => c.key === 'twoMonths')!.met, false);
  assert.equal(noticeCheck({ ...notice, reason: 'other' }, { home: HOME, shop: SHOP }).valid, false);
});

test('unpaid rent: art 51 is quoted as written and left to the court (an editorial call of 20 Oct 2026)', () => {
  const r = noticeCheck({ ...notice, reason: 'arrears' }, { home: HOME, shop: SHOP });
  const year = r.sums.find((s) => s.key === 'yearOfRent')!;
  assert.equal(year.amount, 30000);
  assert.ok(year.court);
  assert.ok(!r.sums.some((s) => s.key === 'falseReason'));
});

test('a shop: fifteen days for unpaid rent, three months otherwise, three years\' rent to rebuild (49.16 arts 9, 26)', () => {
  const shop: NoticeInput = { ...notice, premises: 'shop', reason: 'rebuild', months: 3, tenantSince: '2019-05-01', rent: 4000 };
  const r = noticeCheck(shop, { home: HOME, shop: SHOP });
  assert.ok(r.valid);
  assert.equal(r.leaveBy, '2026-12-03');
  assert.equal(r.lapsesOn, '2027-06-03');
  assert.equal(r.sums.find((s) => s.key === 'threeYears')!.amount, 144000);
  assert.ok(r.checks.find((c) => c.key === 'renewal')!.met);
  const arrears = noticeCheck({ ...shop, reason: 'arrears', months: 0, days: 15 }, { home: HOME, shop: SHOP });
  assert.ok(arrears.checks.find((c) => c.key === 'fifteenDays')!.met);
});

test('off plan: the most paid at each stage (DOC 618-6)', () => {
  assert.deepEqual(['reservation', 'preliminary', 'start', 'works', 'keys'].map((s) => capAt(s as never, true, OFFPLAN)), [5, 10, 20, 80, 100]);
  assert.equal(capAt('preliminary', false, OFFPLAN), 10);
  const r = offplan({ price: 800000, reserved: false, stage: 'start', paid: 200000, delivery: '2026-01-31', extended: false,
    notice: '2026-03-10', on: '2026-10-20' }, OFFPLAN);
  assert.equal(r.capAmount, 160000);
  assert.ok(r.over);
  assert.ok(r.late);
  assert.equal(r.rescission, 40000);             // 20% of what was paid (618-14)
});

test('off plan: 1% a month from a month after the notice, at most 10% a year (618-12)', () => {
  assert.deepEqual(delayPenalty(500000, '2026-03-10', '2026-10-20', OFFPLAN), { months: 6, amount: 30000 });
  // 30 months: two whole years at 10% each, then 6 months at 1%: 26% of 500,000.
  assert.deepEqual(delayPenalty(500000, '2024-03-10', '2026-10-20', OFFPLAN), { months: 30, amount: 130000 });
});

const buyer: AidInput = { moroccan: true, before: false, owns: 'no', price: 280000, permit: '2024-05-01', rooms: 2, firstSale: true,
  deed: '2026-11-15', on: '2026-10-20' };

test('the aid: 100,000 to 300,000 DH, 70,000 to 700,000, five years after (decree 2.23.350 art 2, LF 50.22 art 8)', () => {
  const r = aid(buyer, AID);
  assert.ok(r.eligible);
  assert.equal(r.amount, 100000);
  assert.equal(r.until, '2031-11-15');
  assert.equal(aid({ ...buyer, price: 650000 }, AID).amount, 70000);
  assert.equal(aid({ ...buyer, price: 750000 }, AID).eligible, false);
  assert.equal(aid({ ...buyer, permit: '2022-12-31' }, AID).eligible, false);
  assert.equal(aid({ ...buyer, rooms: 1 }, AID).conditions.find((c) => c.key === 'rooms')!.met, false);
  assert.ok(aid({ ...buyer, owns: 'indivision' }, AID).eligible);           // since the 2026 finance law
  assert.equal(aid({ ...buyer, owns: 'yes' }, AID).eligible, false);
});
