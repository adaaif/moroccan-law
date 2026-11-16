import { test } from 'node:test';
import assert from 'node:assert/strict';
import { fundOf, refund } from '../src/topics/health/rules/refund.ts';
import { lastDay } from '../src/topics/health/rules/clock.ts';
import { find, fold } from '../src/topics/health/rules/illness.ts';

// The rows of apps/topics/health/rates.yaml, as the tool reads them.
const cnss = { care: 70, medicine: 70, hospital: 70, public_hospital: 70, long_public: 90, long_private: 70, share_cap: 100 };
const cnops = { care: 80, medicine: 70, hospital: 90, public_hospital: 100, long_public: 100, long_private: 90, share_cap: 10 };

test('a medicine: 70% of its public price at both funds (65.00 art. 12; 2.05.737 art. 2; 2.05.736 art. 1)', () => {
  assert.deepEqual(refund(100, 'cnss', 'medicine', 'private', 'no', cnss), { rate: 70, back: 70, left: 30, why: 'base' });
  assert.equal(refund(100, 'cnops', 'medicine', 'private', 'no', cnops).back, 70);
});

test('the CNSS: 90% for a long illness treated in a public hospital, 70% elsewhere (2.05.737 art. 2)', () => {
  assert.equal(refund(1000, 'cnss', 'hospital', 'public', 'long', cnss).rate, 90);
  assert.equal(refund(1000, 'cnss', 'hospital', 'private', 'long', cnss).rate, 70);
  assert.equal(refund(1000, 'cnss', 'care', 'public', 'no', cnss).rate, 70);
});

test('the CNOPS: 80 outpatient, 90 hospital, 100 public; a long illness leaves at most 10%, a costly one nothing (2.05.736)', () => {
  assert.equal(refund(200, 'cnops', 'care', 'private', 'no', cnops).rate, 80);
  assert.equal(refund(200, 'cnops', 'hospital', 'private', 'no', cnops).rate, 90);
  assert.equal(refund(200, 'cnops', 'hospital', 'public', 'no', cnops).rate, 100);
  assert.equal(refund(200, 'cnops', 'medicine', 'private', 'long', cnops).rate, 90);
  assert.deepEqual(refund(200, 'cnops', 'medicine', 'private', 'costly', cnops), { rate: 100, back: 200, left: 0, why: 'costly' });
});

test('the fund of an answer: the CNOPS for civil servants, the CNSS for every other regime', () => {
  assert.equal(fundOf('cnops'), 'cnops');
  for (const a of ['private', 'tadamon', 'self', 'achamil', 'student', null]) assert.equal(fundOf(a), 'cnss');
});

test('the clock: two months from the first act, sixty days after a treatment, ninety to be paid, a year to contest', () => {
  assert.equal(lastDay('first-act', '2026-10-14').date, '2026-12-14');
  assert.equal(lastDay('end-treatment', '2026-10-14').date, '2026-12-13');
  assert.equal(lastDay('deposit', '2026-10-14').date, '2027-01-12');
  assert.equal(lastDay('refusal', '2026-10-14').date, '2027-10-14');
});

test('the finder: the list\'s words in either language, and people\'s («السكر» is n° 9, «الكلاوي» n° 16 and 17)', () => {
  const rows: [string, string, string][] = [['9', 'داء السكري المعتمد على الأنسولين', 'Diabète insulinodépendant'], ['16', 'الإعتلالات الكلوية الشديدة', 'Insuffisance rénale aiguë'], ['17', 'العوز الكلوي المزمن', 'Insuffisance rénale chronique terminale'], ['39', 'الأورام الخبيثة', 'Tumeurs malignes']];
  assert.deepEqual(find(rows, 'السكر').map((r) => r[0]), ['9']);
  assert.deepEqual(find(rows, 'الكلاوي').map((r) => r[0]), ['16', '17']);
  assert.deepEqual(find(rows, 'cancer').map((r) => r[0]), ['39']);
  assert.deepEqual(find(rows, 'rénale').map((r) => r[0]), ['16', '17']);
  assert.equal(fold('الأورامُ'), 'الاورام');
});
