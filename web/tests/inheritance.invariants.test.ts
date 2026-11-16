// Invariants over families drawn at random (F6 of the family plan; IR9 of the inheritance review): what must hold
// whatever the case. The generator is mulberry32 over 32-bit integers: the first one multiplied past what a JavaScript
// number holds exactly and fell into a loop, so that 15,000 draws were 592 families.
import test from 'node:test';
import assert from 'node:assert/strict';
import { compute, HEIRS, SINGLE, type Branch, type Counts, type Heir } from '../src/topics/family/inheritance/engine.ts';
import { cmp, eq, mul, q, sum, type Q } from '../src/topics/family/inheritance/frac.ts';
import { allot, type Payee } from '../src/topics/family/inheritance/money.ts';

let state = 20261114;
const rand = (n: number) => {
  state = (state + 0x6D2B79F5) | 0;
  let t = Math.imul(state ^ (state >>> 15), 1 | state);
  t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
  return ((t ^ (t >>> 14)) >>> 0) % n;
};
/** A family shaped like real ones: each kind of relative present one time in `one`, in small numbers. */
function family(one = 4): { deceased: 'm' | 'f'; counts: Counts } {
  const deceased = rand(2) ? 'm' : 'f';
  const counts: Counts = {};
  for (const h of HEIRS) {
    if (rand(one)) continue;
    counts[h] = SINGLE.includes(h) ? 1 : h === 'wife' ? 1 + rand(4) : 1 + rand(3);
  }
  return { deceased, counts };
}
const branches = (): Branch[] => Array.from({ length: rand(3) }, () => ({
  sex: rand(2) ? 'm' as const : 'f' as const, sons: rand(3), daughters: rand(3), spouse: rand(2) === 1, parent: rand(2) === 1,
}));
const died = '2026-10-12';
const N = 20000;

test('the draws are different families', () => {
  const seen = new Set<string>();
  for (let i = 0; i < 5000; i++) seen.add(JSON.stringify(family()));
  assert.ok(seen.size > 4900, `${seen.size} different families in 5,000 draws`);
});

test('every estate is shared out whole, and no share is negative', () => {
  for (let i = 0; i < N; i++) {
    const { deceased, counts } = family();
    const predeceased = branches();
    const r = compute({ deceased, died, counts, predeceased });
    if (!r.ok) { assert.equal(r.reason, 'mixed'); continue; }
    const whole = sum([...r.lines.map((l) => l.share), r.treasury, ...r.bequest.map((b) => b.share)]);
    assert.ok(eq(whole, q(1)), JSON.stringify({ counts, predeceased }));
    for (const l of r.lines) assert.ok(cmp(l.each, q(0)) > 0, l.heir);
  }
});

test('those the code excludes never take (art. 358)', () => {
  const blocked: [Heir, Heir[]][] = [
    ['son', ['sonsSon', 'sonsDaughter', 'fullBrother', 'fullSister', 'patBrother', 'patSister', 'matBrother', 'matSister', 'fullNephew', 'fullUncle']],
    ['father', ['grandfather', 'grandmotherF', 'fullBrother', 'fullSister', 'patBrother', 'patSister', 'matBrother', 'matSister']],
    ['mother', ['grandmotherM', 'grandmotherF']],
    ['daughter', ['matBrother', 'matSister']],
    ['fullBrother', ['patBrother', 'patSister', 'fullNephew', 'patNephew', 'fullUncle']],
  ];
  for (let i = 0; i < N; i++) {
    const { deceased, counts } = family();
    const r = compute({ deceased, died, counts });
    if (!r.ok) continue;
    const took = new Set(r.lines.map((l) => l.heir));
    for (const [by, them] of blocked) {
      if (!counts[by] || (by === 'fullBrother' && r.named === 'mushtaraka')) continue;
      for (const h of them) assert.ok(!took.has(h), `${h} took beside ${by}: ${JSON.stringify(counts)}`);
    }
  }
});

test('a male takes twice a female of his rank; spouses and siblings by the mother share equally', () => {
  const pairs: [Heir, Heir][] = [['son', 'daughter'], ['sonsSon', 'sonsDaughter']];
  for (let i = 0; i < N; i++) {
    const { deceased, counts } = family();
    const r = compute({ deceased, died, counts });
    if (!r.ok) continue;
    const each = Object.fromEntries(r.lines.map((l) => [l.heir, l.each])) as Partial<Record<Heir, Q>>;
    for (const [m, f] of pairs) if (each[m] && each[f]) assert.ok(eq(each[m] as Q, mul(each[f] as Q, q(2))), `${m}/${f}`);
    if (each.matBrother && each.matSister) assert.ok(eq(each.matBrother, each.matSister));
    // Without «عول» or «رد», a spouse takes the code's fraction exactly.
    if (!r.awl && !r.radd && !r.named) {
      const desc = (counts.son ?? 0) + (counts.daughter ?? 0) + (counts.sonsSon ?? 0) + (counts.sonsDaughter ?? 0) > 0;
      const wives = r.lines.find((l) => l.heir === 'wife');
      if (wives) assert.ok(eq(wives.share, desc ? q(1, 8) : q(1, 4)));
      const husband = r.lines.find((l) => l.heir === 'husband');
      if (husband) assert.ok(eq(husband.share, desc ? q(1, 4) : q(1, 2)));
    }
  }
});

test('a relative who takes nothing moves nobody else, outside the rules the code names', () => {
  const siblings: Heir[] = ['fullBrother', 'fullSister', 'patBrother', 'patSister', 'matBrother', 'matSister'];
  const shares = (r: Extract<ReturnType<typeof compute>, { ok: true }>) => JSON.stringify(r.lines.map((l) => [l.heir, `${l.share.n}/${l.share.d}`]).sort());
  for (let i = 0; i < 4 * N; i++) {
    const { deceased, counts } = family(5);
    const add = HEIRS[rand(HEIRS.length)];
    if (counts[add] || (add === 'husband' && deceased === 'm') || (add === 'wife' && deceased === 'f')) continue;
    const a = compute({ deceased, died, counts });
    const b = compute({ deceased, died, counts: { ...counts, [add]: 1 } });
    if (!a.ok || !b.ok || b.lines.some((l) => l.heir === add) || shares(a) === shares(b)) continue;
    const before = siblings.reduce((s, h) => s + (counts[h] ?? 0), 0);
    const known =
      // a second brother or sister lowers the mother to a sixth, even shut out (arts 346, 359)
      (siblings.includes(add) && (counts.mother ?? 0) > 0 && before < 2)
      // the paternal ones are counted against the grandfather (art. 360)
      || ((add === 'patBrother' || add === 'patSister') && (counts.grandfather ?? 0) > 0)
      // a brother who turns his sister from a fixed share to the residue, when nothing is left («الأخ المشؤوم»: art. 351)
      || (add === 'patBrother' && (counts.patSister ?? 0) > 0) || (add === 'sonsSon' && (counts.sonsDaughter ?? 0) > 0)
      // a second brother or sister by the mother makes the case of art. 362 or 363
      || ((add === 'matBrother' || add === 'matSister') && (b.named === 'malikiyya' || b.named === 'shibhMalikiyya'));
    assert.ok(known, `adding ${add} to ${JSON.stringify(counts)}: ${shares(a)} → ${shares(b)}`);
  }
});

test('the bequest: never above a third, never above the other reading, a grandson twice a granddaughter', () => {
  for (let i = 0; i < N; i++) {
    const { deceased, counts } = family(5);
    const predeceased = branches();
    const r = compute({ deceased, died, counts, predeceased });
    if (!r.ok || !r.bequest.length) continue;
    assert.ok(cmp(r.bequestTotal, q(1, 3)) <= 0, 'a third');
    // All branches together take no more than by the other reading (which may be cut to the third when this one is
    // not); each branch takes no more than its dead parent's share.
    assert.ok(cmp(r.bequestTotal, sum(r.bequest.map((b) => b.whole))) <= 0, 'no more than the other reading');
    for (const b of r.bequest) {
      assert.ok(cmp(b.share, b.parent) <= 0, `${b.share.n}/${b.share.d} above the dead parent's share ${b.parent.n}/${b.parent.d}`);
      if (b.sons && b.daughters) assert.ok(eq(b.son, mul(b.daughter, q(2))), 'two for one');
      assert.ok(eq(sum([mul(b.son, q(b.sons)), mul(b.daughter, q(b.daughters))]), b.share), 'the branch adds up');
    }
    // No bequest for a son's children who take as heirs (art. 371).
    if (r.lines.some((l) => l.heir === 'sonsSon' || l.heir === 'sonsDaughter')) assert.ok(r.bequest.every((b) => b.sex === 'f'));
  }
});

test('the dirhams add up to the estate, and equals are paid alike', () => {
  for (let i = 0; i < N; i++) {
    const { deceased, counts } = family(5);
    const r = compute({ deceased, died, counts, predeceased: branches() });
    if (!r.ok) continue;
    const total = BigInt(1 + rand(2000000000));
    const payees: Payee[] = [
      ...r.lines.map((l) => ({ key: l.heir, count: l.count, each: l.each })),
      ...r.bequest.flatMap((b, n) => [{ key: `s${n}`, count: b.sons, each: b.son }, { key: `d${n}`, count: b.daughters, each: b.daughter }]).filter((p) => p.count),
      ...(r.treasury.n ? [{ key: 'treasury', count: 1, each: r.treasury }] : []),
    ];
    const paid = allot(total, payees);
    const out = payees.reduce((s, p) => s + paid.each[p.key] * BigInt(p.count), 0n);
    assert.equal(out + paid.rest, total);
    assert.ok(paid.rest >= 0n && paid.rest < BigInt(payees.reduce((s, p) => s + p.count, 0) || 1), 'the rest is less than a centime a person');
  }
});
