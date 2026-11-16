// The calculator's case code, its dirhams, the adoul's table and the solver (IR5, IR12, IR16, IR19, IR23, IR26 of
// the inheritance review): `node --test tests/`.
import test from 'node:test';
import assert from 'node:assert/strict';
import { compute } from '../src/topics/family/inheritance/engine.ts';
import { eq, q, type Q } from '../src/topics/family/inheritance/frac.ts';
import { EMPTY, decode, encode, older, type Case } from '../src/topics/family/inheritance/case.ts';
import { formatAmount, inMillions, parseAmount } from '../src/topics/family/inheritance/money.ts';
import { closes, solve } from '../src/topics/family/inheritance/solve.ts';
import { tableOf } from '../src/topics/family/inheritance/table.ts';

const f = (x: Q) => (x.d === 1n ? `${x.n}` : `${x.n}/${x.d}`);
const first: Case = { ...EMPTY, counts: { wife: 1, daughter: 3, fullBrother: 2 }, estate: '80000000' };

test('an amount is read the ways it is written here', () => {
  const read: [string, bigint | null][] = [
    ['800000', 80000000n], ['800.000', 80000000n], ['800 000', 80000000n], ['800,000', 80000000n], ['800.000,00', 80000000n],
    ['1.200.000', 120000000n], ['800000.50', 80000050n], ['800.000,5', 80000050n], ['٨٠٠٠٠٠', 80000000n], ['800000 درهم', 80000000n],
    ['80 مليون', 80000000n], ['1,5 مليون', 1500000n], ['12345.678', null], ['1.2.3', null], ['', null], ['درهم', null],
  ];
  for (const [typed, want] of read) assert.equal(parseAmount(typed), want, typed);
  assert.equal(parseAmount('80', 'million'), 80000000n);
  assert.equal(formatAmount(17777778n, 'ar'), '177.777,78');
  assert.equal(formatAmount(80000000n, 'ar'), '800.000');
  assert.equal(inMillions(80000000n), '80');
  assert.equal(inMillions(1500000n), '1,5');
  assert.equal(inMillions(50000n), null);
});

test('the first family: the lines add up to 800,000 and the daughters are paid alike', () => {
  const a = solve(first);
  assert.ok(a.state === 'ok' && a.paid);
  assert.equal(a.paid.each.wife, 10000000n);
  assert.equal(a.paid.each.daughter, 17777778n);
  assert.equal(a.paid.each.fullBrother, 8333333n);
  assert.equal(a.paid.rest, 0n);
  assert.equal(a.common, 144n);
  assert.ok(closes(a.shares));
});

test('a hundred dirhams among three sons: a centime that cannot be shared is said', () => {
  const a = solve({ ...EMPTY, counts: { son: 3 }, estate: '10000' });
  assert.ok(a.state === 'ok' && a.paid);
  assert.equal(a.paid.each.son, 3333n);
  assert.equal(a.paid.rest, 1n);
});

test('the adoul\'s table: 24, six times, 144', () => {
  const r = compute({ deceased: 'm', counts: first.counts });
  assert.ok(r.ok);
  const t = tableOf(r);
  assert.deepEqual([t.base, t.awl, t.radd, t.working, t.times, t.corrected], [24n, null, null, 24n, 6n, 144n]);
  assert.deepEqual(t.rows.map((x) => [x.heir, x.group, x.each]), [['wife', 3n, 18n], ['daughter', 16n, 32n], ['fullBrother', 5n, 15n]]);
});

test('the table says a rise and a return', () => {
  const rise = compute({ deceased: 'f', counts: { husband: 1, mother: 1, fullSister: 1 } });
  assert.ok(rise.ok);
  const a = tableOf(rise);
  assert.deepEqual([a.base, a.awl, a.radd, a.working, a.corrected], [6n, 8n, null, 8n, 8n]);
  const back = compute({ deceased: 'm', counts: { wife: 2, daughter: 1 } });
  assert.ok(back.ok);
  const b = tableOf(back);
  assert.deepEqual([b.base, b.awl, b.radd, b.working, b.times, b.corrected], [8n, null, 5n, 5n, 2n, 10n]);
  assert.deepEqual(b.rows.map((x) => [x.heir, x.group, x.each]), [['wife', 1n, 1n], ['daughter', 4n, 8n]]);
});

test('with a bequest the heirs\' own table stands apart', () => {
  const r = compute({ deceased: 'm', counts: { wife: 1, son: 1, daughter: 1 }, predeceased: [{ sex: 'm', sons: 1, daughters: 1, spouse: true, parent: true }] });
  assert.ok(r.ok);
  const t = tableOf(r);
  assert.deepEqual([t.base, t.corrected], [8n, 24n]);
  assert.deepEqual(t.rows.map((x) => [x.heir, x.each]), [['wife', 3n], ['son', 14n], ['daughter', 7n]]);
  assert.equal(r.tashih, 11520n);
});

test('a case and its code', () => {
  const c: Case = {
    ...EMPTY, deceased: 'f', died: '1998', counts: { husband: 1, mother: 1, son: 2, daughter: 1, fullBrother: 3 },
    branches: [{ sex: 'm', sons: 1, daughters: 2, spouse: true, parent: false }, { sex: 'f', sons: 0, daughters: 1, spouse: false, parent: true }],
    estate: '80000000', funeral: '500000', debts: '12000000', dowry: '', will: { kind: 'part', value: '1/3', heir: false, agreed: true },
    tanzil: { as: 'daughter', count: 2, equal: true, agreed: false },
    later: [{ heir: 'son', counts: { wife: 1, son: 2 }, branches: [{ sex: 'f', sons: 1, daughters: 0, spouse: true, parent: true }] }], unborn: false, other: false,
  };
  const code = encode(c);
  assert.equal(code, 'v2~f~h~s2~d1~mo~fb3~xm1a2w~xf0a1p~t1998~e80000000~of500000~od12000000~op1j3a~zd2e~ls!w1!s2!xf1a0wp');
  assert.deepEqual(decode(code)?.case, c);
  assert.deepEqual(decode('#' + code)?.case, c);
  assert.equal(encode(EMPTY), '');
  assert.equal(decode('hello'), null);
  assert.equal(decode('v2~x'), null);
  // A man leaves no husband; what the code does not know is left out.
  assert.deepEqual(decode('v2~m~h~w2~qq9~s1')?.case.counts, { wife: 2, son: 1 });
  assert.ok(older('1') && !older('2'));
  assert.equal(decode('v1~m~s1')?.version, '1');
});

test('what leaves the estate first, a will inside the third, and a stop', () => {
  // 800,000 left; 5,000 for the funeral, 120,000 of debts, 25,000 of dowry still owed: 650,000 shared.
  const a = solve({ ...EMPTY, counts: { wife: 1, son: 1 }, estate: '80000000', funeral: '500000', debts: '12000000', dowry: '2500000',
    will: { kind: 'amount', value: '30000000', heir: false, agreed: false } });
  assert.ok(a.state === 'ok' && a.money && a.paid);
  assert.equal(a.money.net, 65000000n);
  // A will of 300,000 is more than the third of 650,000: cut to 216,666.66 and a centime left over.
  assert.equal(a.result.will?.cut, 'third');
  assert.ok(eq(a.result.will.granted, q(1, 3)));
  assert.equal(a.paid.each.will + a.paid.each.wife + a.paid.each.son + a.paid.rest, 65000000n);
  assert.equal(a.common, null);
  // More debts than estate.
  assert.deepEqual(solve({ ...EMPTY, counts: { son: 1 }, estate: '100000', debts: '200000' }), { state: 'stop', why: 'overdrawn', cites: [322] });
  assert.equal(solve({ ...EMPTY, counts: { son: 1 }, unborn: true }).state, 'stop');
  assert.equal(solve(EMPTY).state, 'empty');
  // A will typed with no estate waits for it.
  const w = solve({ ...EMPTY, counts: { son: 1 }, will: { kind: 'amount', value: '100000', heir: false, agreed: false } });
  assert.ok(w.state === 'ok' && w.willWaits && w.result.will === null);
});

test('an heir who died before the division: his part goes to his own heirs', () => {
  // A man leaves a wife and two sons; one son then dies, leaving his mother (that wife), a wife and a son.
  const a = solve({ ...EMPTY, counts: { wife: 1, son: 2 }, estate: '96000000',
    later: [{ heir: 'son', counts: { mother: 1, wife: 1, son: 1 }, branches: [] }] });
  assert.ok(a.state === 'ok' && a.paid);
  const each = Object.fromEntries(a.shares.map((s) => [s.key, f(s.each)]));
  // First estate: wife 1/8, each son 7/16. The dead son's 7/16: his mother 1/6, his wife 1/8, his son the rest.
  assert.deepEqual(each, { wife: '1/8', son: '7/16', 'l0.wife': '7/128', 'l0.mother': '7/96', 'l0.son': '119/384' });
  assert.equal(a.shares.find((s) => s.key === 'son')?.count, 1);
  assert.ok(closes(a.shares));
  assert.equal(a.common, 384n);
  assert.equal(Object.entries(a.paid.each).reduce((s, [k, v]) => s + v * BigInt(a.shares.find((x) => x.key === k)?.count ?? 0), 0n) + a.paid.rest, 96000000n);
});

test('a «تنزيل» and a will share the third in proportion', () => {
  const r = compute({ deceased: 'm', counts: { son: 1 }, tanzil: { as: 'son', count: 1, equal: true }, will: { share: q(1, 6) } });
  assert.ok(r.ok && r.tanzil && r.will);
  // Asked: a half by rise and a sixth; the third is shared 3 to 1.
  assert.ok(eq(r.tanzil.asked, q(1, 2)) && eq(r.tanzil.total, q(1, 4)) && eq(r.will.granted, q(1, 12)));
  assert.ok(eq(r.left, q(2, 3)));
});

test('a death between 4 April 1958 and 4 February 2004: the old book, no return, the bequest for a son\'s children only', () => {
  const r = compute({ deceased: 'm', died: '1990-06-01', counts: { wife: 1 } });
  assert.ok(r.ok && r.rules.code === '1958');
  // A wife alone keeps her quarter; the rest goes to the Treasury, where the 2004 code returns it to her.
  assert.deepEqual([f(r.lines[0].each), f(r.treasury), r.radd], ['1/4', '3/4', false]);
  assert.deepEqual(r.lines[0].cites, [[240, 2]]);
  const today = compute({ deceased: 'm', counts: { wife: 1 } });
  assert.ok(today.ok && today.rules.code === '70-03' && f(today.lines[0].each) === '1' && today.radd);
  // A dead daughter's children are owed nothing before 2004; a dead son's are, by the Court's reading.
  const girl = compute({ deceased: 'm', died: '1998', counts: { son: 1 }, predeceased: [{ sex: 'f', sons: 1, daughters: 0 }] });
  assert.ok(girl.ok && girl.bequest.length === 0 && f(girl.lines[0].each) === '1');
  const boy = compute({ deceased: 'm', died: '1998-01-01', counts: { son: 2, daughter: 1 }, predeceased: [{ sex: 'm', sons: 0, daughters: 1 }] });
  assert.ok(boy.ok && f(boy.bequest[0].daughter) === '1/7');
  // The exclusions carry the old book's numbers: art. 255 §3 for brothers shut out by a son (art. 358 §4 today).
  const out = compute({ deceased: 'm', died: '1990-06-01', counts: { son: 1, fullBrother: 1 } });
  assert.ok(out.ok);
  assert.deepEqual(out.excluded[0].cites, [[255, 3]]);
  // Before the first code: not counted.
  assert.deepEqual(compute({ deceased: 'm', died: '1950-01-01', counts: { son: 1 } }), { ok: false, reason: 'before' });
  assert.deepEqual(solve({ ...EMPTY, died: '1950', counts: { son: 1 } }), { state: 'stop', why: 'before', cites: [] });
  const old = solve({ ...EMPTY, died: '1998', counts: { daughter: 1 }, estate: '10000000' });
  assert.ok(old.state === 'ok' && old.paid && old.paid.each.treasury === 5000000n);
});

test('the families with an address of their own open on an answer that says what their words say', async () => {
  const { readFileSync } = await import('node:fs');
  const landings = JSON.parse(readFileSync(new URL('../src/topics/family/inheritance/landings.json', import.meta.url), 'utf8')) as { slug: string; code: string }[];
  assert.equal(new Set(landings.map((l) => l.slug)).size, landings.length);
  const each = (code: string) => {
    const a = solve(decode(code)!.case);
    assert.ok(a.state === 'ok');
    return Object.fromEntries(a.shares.map((s) => [s.key, f(s.each)]));
  };
  for (const l of landings) assert.ok(/^[a-z0-9-]+$/.test(l.slug) && decode(l.code), l.slug);
  const by = Object.fromEntries(landings.map((l) => [l.slug, each(l.code)]));
  assert.deepEqual(by['zawja-3-banat-akhawan'], { wife: '1/8', daughter: '2/9', fullBrother: '5/48' });
  assert.deepEqual(by['zawja-ibn-bint'], { wife: '1/8', son: '7/12', daughter: '7/24' });
  assert.deepEqual(by['zawj-ibn-bintan'], { husband: '1/4', son: '3/8', daughter: '3/16' });
  assert.deepEqual(by['zawja-abawan-awlad'], { wife: '1/8', son: '13/60', daughter: '13/120', father: '1/6', mother: '1/6' });
  assert.deepEqual(by['zawja-banat-bila-asib'], { wife: '3/19', daughter: '8/19' });
  assert.deepEqual(by['zawja-um-ikhwa'], { wife: '1/4', mother: '1/6', fullBrother: '7/30', fullSister: '7/60' });
  assert.deepEqual(by['zawj-abawan'], { husband: '1/2', father: '1/3', mother: '1/6' });
  assert.deepEqual(by['bint-wa-akh'], { daughter: '1/2', fullBrother: '1/2' });
  assert.deepEqual(by['zawja-um-banat-amm'], { wife: '1/8', daughter: '1/3', mother: '1/6', fullUncle: '1/24' });
  assert.equal(by['ahfad-ibn-mutawaffa']['b0.son'], '119/720');
});

test('the Akdariyya in the adoul\'s table: the fixed shares the code names, six raised to nine, twenty-seven', () => {
  const r = compute({ deceased: 'f', counts: { husband: 1, mother: 1, grandfather: 1, fullSister: 1 } });
  assert.ok(r.ok);
  assert.deepEqual(r.lines.map((l) => [l.heir, l.fard && f(l.fard), f(l.each)]),
    [['husband', '1/2', '1/3'], ['mother', '1/3', '2/9'], ['fullSister', '1/2', '4/27'], ['grandfather', '1/6', '8/27']]);
  const t = tableOf(r);
  assert.deepEqual([t.base, t.awl, t.corrected], [6n, 9n, 27n]);
  // A grandfather who shares as a brother, or takes the rest in art. 362's case, has no fixed share.
  const shares = compute({ deceased: 'm', counts: { grandfather: 1, fullBrother: 1 } });
  assert.ok(shares.ok && shares.lines[0].fard === null && shares.lines[0].basis === 'asaba');
  const third = compute({ deceased: 'm', counts: { grandfather: 1, fullBrother: 3 } });
  assert.ok(third.ok && third.lines[0].fard && f(third.lines[0].fard) === '1/3');
  // Each bequest line names its dead child's place in the case.
  const b = compute({ deceased: 'm', counts: { son: 1 }, predeceased: [{ sex: 'm', sons: 0, daughters: 0 }, { sex: 'f', sons: 1, daughters: 0 }] });
  assert.ok(b.ok && b.bequest[0].index === 1);
});
