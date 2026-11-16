// Two engines, one answer (IR9 of the inheritance review): the calculator's engine against a second one written from
// the code's articles alone by someone who had not read the first (tests/second/engine2.ts). Any difference stops the
// release. Families shaped like real ones, dead children among them.
import test from 'node:test';
import assert from 'node:assert/strict';
import { compute, HEIRS, SINGLE, type Branch, type Counts, type Heir } from '../src/topics/family/inheritance/engine.ts';
import type { Q } from '../src/topics/family/inheritance/frac.ts';
import { second } from './second/engine2.ts';

let state = 20261115;
const rand = (n: number) => {
  state = (state + 0x6D2B79F5) | 0;
  let t = Math.imul(state ^ (state >>> 15), 1 | state);
  t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
  return ((t ^ (t >>> 14)) >>> 0) % n;
};
const f = (x: Q) => `${x.n}/${x.d}`;

export function differences(n: number, one: number, withBranches: boolean): string[] {
  const out: string[] = [];
  for (let i = 0; i < n; i++) {
    const deceased = rand(2) ? 'm' : 'f';
    const counts: Counts = {};
    for (const h of HEIRS) {
      if (rand(one)) continue;
      counts[h] = SINGLE.includes(h) ? 1 : h === 'wife' ? 1 + rand(4) : 1 + rand(3);
    }
    const predeceased: Branch[] = withBranches ? Array.from({ length: rand(3) }, () => ({
      sex: rand(2) ? 'm' as const : 'f' as const, sons: rand(3), daughters: rand(3), spouse: rand(2) === 1, parent: rand(2) === 1,
    })) : [];
    const a = compute({ deceased, counts, predeceased });
    const b = second({ deceased, counts, predeceased });
    const mine = !a.ok ? { stop: a.reason } : {
      each: Object.fromEntries(a.lines.map((l) => [l.heir, f(l.each)]).sort()) as Partial<Record<Heir, string>>,
      // One entry a branch as given, in order: the second engine lists every branch, owed or not.
      bequest: predeceased.map((p) => {
        const owed = a.bequest.find((x, k) => x.sex === p.sex && x.sons === p.sons && x.daughters === p.daughters
          && a.bequest.slice(0, k).filter((y) => y.sex === p.sex && y.sons === p.sons && y.daughters === p.daughters).length
            === predeceased.slice(0, predeceased.indexOf(p)).filter((y) => y.sex === p.sex && y.sons === p.sons && y.daughters === p.daughters && y.sons + y.daughters > 0).length);
        return { son: owed && p.sons ? f(owed.son) : '0/1', daughter: owed && p.daughters ? f(owed.daughter) : '0/1' };
      }),
      treasury: f(a.treasury),
    };
    const theirs = 'stop' in b ? { stop: b.stop } : { each: Object.fromEntries(Object.entries(b.each).sort()), bequest: b.bequest, treasury: b.treasury };
    if (JSON.stringify(mine) !== JSON.stringify(theirs)) out.push(`${deceased} ${JSON.stringify(counts)} ${JSON.stringify(predeceased)}\n   first  ${JSON.stringify(mine)}\n   second ${JSON.stringify(theirs)}`);
  }
  return out;
}

test('the heirs\' shares: 60,000 families, no dead child', () => {
  const d = differences(60000, 4, false);
  assert.equal(d.length, 0, `${d.length} differences; the first:\n${d.slice(0, 3).join('\n')}`);
});

test('the bequest: 60,000 families with dead children', () => {
  const d = differences(60000, 5, true);
  assert.equal(d.length, 0, `${d.length} differences; the first:\n${d.slice(0, 3).join('\n')}`);
});
