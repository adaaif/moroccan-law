/** The consumer tools' rules (T1–T7 of the consumer plan), on written cases: each date worked out by hand from its
 *  article of law 31.08, every period a full one (art. 203: the starting day does not count), the sugar prices as the
 *  orders print them. */
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { canReturn, windowDays } from '../src/topics/consumer/rules/withdrawal.ts';
import { guarantee } from '../src/topics/consumer/rules/guarantee.ts';
import { dateRequired, lateDated, lateDistance } from '../src/topics/consumer/rules/delivery.ts';
import { ceilings, inDefault, withdrawBy } from '../src/topics/consumer/rules/credit.ts';
import { SUGAR, sugarOn } from '../src/topics/consumer/rules/sugar.ts';
import { DOORS, SECTORS } from '../src/topics/consumer/rules/where.ts';
import { KINDS } from '../src/topics/consumer/rules/clauses.ts';
import { LETTERS, filled } from '../src/topics/consumer/rules/letters.ts';
import { receipt, nextLast } from '../src/topics/consumer/rules/receipt.ts';

test('online, received on Saturday 24 Oct 2026 with a written confirmation: the last day is 31 Oct (arts 36, 203)', () => {
  const r = canReturn({ channel: 'online', day: '2026-10-24', confirmed: true });
  assert.equal(r.kind, 'window');
  if (r.kind !== 'window') return;
  assert.equal(r.days, 7);
  assert.equal(r.last, '2026-10-31');
  assert.equal(r.refundDays, 15);                        // art. 37
  assert.deepEqual(windowDays('2026-10-24', 7), ['2026-10-25', '2026-10-26', '2026-10-27', '2026-10-28', '2026-10-29', '2026-10-30', '2026-10-31']);
});

test('online without a written confirmation: thirty days, to 23 Nov 2026 (art. 36, second item)', () => {
  const r = canReturn({ channel: 'online', day: '2026-10-24', confirmed: false });
  assert.ok(r.kind === 'window' && r.days === 30 && r.last === '2026-11-23');
});

test('made to measure, perishable or opened: no withdrawal online (art. 38)', () => {
  const r = canReturn({ channel: 'online', day: '2026-10-24', excluded: true });
  assert.equal(r.kind, 'excluded');
  assert.ok(r.cites.includes('/ma/loi/31-08/art_38'));
});

test('a door sale ordered on 20 Oct 2026: seven days from the order, to 27 Oct (art. 49)', () => {
  const r = canReturn({ channel: 'door', day: '2026-10-20' });
  assert.ok(r.kind === 'window' && r.from === 'order' && r.last === '2026-10-27');
});

test('a credit offer accepted on 28 Feb 2026: to 7 Mar (art. 85)', () => {
  const r = canReturn({ channel: 'credit', day: '2026-02-28' });
  assert.ok(r.kind === 'window' && r.last === '2026-03-07');
  assert.equal(withdrawBy('2026-02-28'), '2026-03-07');
});

test('in a shop: no withdrawal, the guarantee to a year after delivery (arts 36, 65)', () => {
  const r = canReturn({ channel: 'shop', day: '2026-10-24' });
  assert.ok(r.kind === 'shop' && r.guaranteeLast === '2027-10-24');
});

test('a phone delivered 15 Jan 2026, a 24-month card, 21 days in repair: legal to 15 Jan 2027, the card to 5 Feb 2028 (arts 65, 73)', () => {
  const g = guarantee({ delivered: '2026-01-15', shopMonths: 24, repairDays: 21 });
  assert.equal(g.legalLast, '2027-01-15');
  assert.equal(g.shopBase, '2028-01-15');
  assert.equal(g.shopLast, '2028-02-05');
  assert.ok(g.cites.includes('/ma/loi/31-08/art_73'));
});

test('a flat delivered 31 Aug 2026: two years, to 31 Aug 2028; no card, no shop line (art. 65)', () => {
  const g = guarantee({ delivered: '2026-08-31', immovable: true });
  assert.equal(g.legalLast, '2028-08-31');
  assert.equal(g.shopLast, null);
});

test('a sofa promised for 1 Nov 2026: ending possible from 9 Nov to 13 Nov; a notice received 10 Nov is refunded by 17 Nov, interest from 18 Nov (arts 13, 14)', () => {
  const l = lateDated('2026-11-01', '2026-11-10');
  assert.equal(l.from, '2026-11-09');
  assert.equal(l.until, '2026-11-13');
  assert.equal(l.refundBy, '2026-11-17');
  assert.equal(l.interestFrom, '2026-11-18');
  assert.ok(dateRequired(3500) && !dateRequired(3000));      // decree 2.12.503 art. 28: above 3,000 dirhams
});

test('an online order confirmed 1 Oct 2026: executed by 31 Oct; paid on 1 Oct and unavailable, refunded by 16 Oct (arts 39, 40)', () => {
  const d = lateDistance('2026-10-01', '2026-10-01');
  assert.equal(d.executeBy, '2026-10-31');
  assert.equal(d.refundBy, '2026-10-16');
});

test('a consumer credit with 20,000 DH left and 3,000 DH unpaid: interest within 800, indemnity within 120, early repayment free (arts 103–105)', () => {
  const c = ceilings('consumer', 20000, 3000);
  assert.equal(c.lateInterest, 800);
  assert.equal(c.indemnity, 120);
  assert.equal(c.early, 0);
  assert.equal(ceilings('consumer', 20000, 3000, 2500).indemnity, 50);     // deferred: 2 %
  assert.ok(inDefault(3, false) && !inDefault(2, false) && !inDefault(3, true));   // art. 109
});

test('a home loan with 400,000 DH left: early repayment and late interest each within 8,000 (arts 132, 133)', () => {
  const c = ceilings('home', 400000);
  assert.equal(c.early, 8000);
  assert.equal(c.lateInterest, 8000);
  assert.equal(c.indemnity, null);
});

test('sugar on 24 Oct 2026, granulated 1 kg: 4.3363 ex factory, margins 0.1019 and 0.1548, together 4.593 (orders 2889.25, 3243.23)', () => {
  const s = sugarOn(SUGAR, '2026-10-24', 'g1')!;
  assert.equal(s.factory, 4.3363);
  assert.equal(s.wholesale, 0.1019);
  assert.equal(s.retail, 0.1548);
  assert.equal(s.total, 4.593);
  assert.equal(s.from, '2026-01-01');
  const loaf2023 = sugarOn(SUGAR, '2023-06-01', 'loaf')!;
  assert.equal(loaf2023.factory, 5.008);
  assert.equal(loaf2023.total, null);                    // before 2024, the site holds no restated margins
});

test('the copy of the sugar rows ships what rates.yaml says (its newest row, value by value)', () => {
  const yaml = readFileSync(new URL('../../back/apps/topics/consumer/rates.yaml', import.meta.url), 'utf8');
  const newest = SUGAR[SUGAR.length - 1];
  for (const [k, v] of Object.entries(newest.values)) assert.ok(new RegExp(`${k}: ${String(v).replace('.', '\\.')}0*[,}]`).test(yaml), `${k}: ${v}`);
});

test('every sector starts with the supplier and ends with a court or a regulator; the seventeen kinds; the letters quote articles', () => {
  for (const s of SECTORS) {
    assert.ok(DOORS[s].length >= 3, s);
    assert.ok(!DOORS[s][0].url, `${s}: the supplier first, no service before it`);
  }
  assert.equal(KINDS.length, 17);
  for (const l of LETTERS) assert.ok(l.cites.length && l.fields.includes('name'), l.key);
  assert.equal(filled({ name: ' Salma ' }, ['name', 'supplier']).supplier, '……………');
});

test('the receipt of a purchase: its lines and dates come from the other rules (the consumer-receipt review)', () => {
  // Online goods received on 20 October, confirmed in writing, 4,200 DH: 7 days to withdraw, refund in 15, a year of
  // guarantee, the written date (above 3,000 DH), the invoice, the price, the court.
  const online = receipt({ channel: 'online', day: '2026-10-20', price: 4200, confirmed: true });
  assert.deepEqual(online.map((l) => l.key), ['withdraw', 'refund', 'guarantee', 'noReturnStamp', 'invoice', 'price', 'writtenDate', 'court']);
  assert.equal(online[0].last, canReturn({ channel: 'online', day: '2026-10-20', confirmed: true }).kind === 'window' ? '2026-10-27' : '');
  assert.equal(online.find((l) => l.key === 'guarantee')?.last, guarantee({ delivered: '2026-10-20' }).legalLast);
  // Without the written confirmation, thirty days.
  assert.equal(receipt({ channel: 'online', day: '2026-10-20', price: 100, confirmed: false })[0].days, 30);
  // In a shop: no withdrawal, the guarantee, the shop's own when it gives one; no written date at 900 DH.
  const shop = receipt({ channel: 'shop', day: '2026-10-20', price: 900, shopMonths: 24 });
  assert.deepEqual(shop.map((l) => l.key), ['noWithdraw', 'guarantee', 'shopGuarantee', 'noReturnStamp', 'invoice', 'price', 'court']);
  // A credit: the linked sale ends with it, early repayment free, the 4 % cap; a service online has no guarantee.
  assert.ok(receipt({ channel: 'credit', day: '2026-10-20', price: 20000 }).some((l) => l.key === 'defaultCap'));
  assert.ok(!receipt({ channel: 'online', service: true, day: '2026-10-20', price: 300 }).some((l) => l.key === 'guarantee'));
  // The soonest day ahead.
  assert.equal(nextLast(online, '2026-10-21')?.key, 'withdraw');
  assert.equal(nextLast(online, '2026-10-30')?.key, 'guarantee');
});
