// The questions the calculator asks (IR13 of the inheritance review): a relative it does not ask about must not be
// able to move anyone's share in that family. `node --test tests/`.
import test from 'node:test';
import assert from 'node:assert/strict';
import { HEIRS, SINGLE, type Branch, type Counts, type Heir } from '../src/topics/family/inheritance/engine.ts';
import { EMPTY, type Case } from '../src/topics/family/inheritance/case.ts';
import { asked, siblingsForMother, skipped, steps } from '../src/topics/family/inheritance/flow.ts';
import { solve } from '../src/topics/family/inheritance/solve.ts';

let state = 20261116;
const rand = (n: number) => {
  state = (state + 0x6D2B79F5) | 0;
  let t = Math.imul(state ^ (state >>> 15), 1 | state);
  t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
  return ((t ^ (t >>> 14)) >>> 0) % n;
};
const NEVER: Heir[] = ['sonsSon', 'sonsDaughter'];   // a son's children are entered under their dead father, never asked as a kind
const picture = (c: Case) => {
  const a = solve(c);
  return a.state === 'ok' ? JSON.stringify(a.shares.map((s) => [s.key, s.count, `${s.each.n}/${s.each.d}`])) : `${a.state}:${'why' in a ? a.why : ''}`;
};

test('a relative the questions leave out moves nobody', () => {
  let tried = 0;
  for (let i = 0; i < 10000; i++) {
    const deceased = rand(2) ? 'm' : 'f';
    const counts: Counts = {};
    for (const h of HEIRS) {
      if (NEVER.includes(h) || rand(5)) continue;
      counts[h] = SINGLE.includes(h) ? 1 : h === 'wife' ? 1 + rand(4) : 1 + rand(3);
    }
    if (deceased === 'm') delete counts.husband; else delete counts.wife;
    const branches: Branch[] = Array.from({ length: rand(3) }, () => ({ sex: rand(2) ? 'm' as const : 'f' as const, sons: rand(3), daughters: rand(3), spouse: rand(2) === 1, parent: rand(2) === 1 }));
    // The family as the questions would have left it: nobody the questions do not ask about.
    const c: Case = { ...EMPTY, deceased, counts, branches };
    for (let pass = 0; pass < 3; pass++) { const ask = asked(c); for (const h of HEIRS) if (!ask.has(h)) delete c.counts[h]; }
    const before = picture(c);
    const ask = asked(c);
    for (const h of HEIRS) {
      if (ask.has(h) || NEVER.includes(h) || h === (deceased === 'm' ? 'husband' : 'wife')) continue;
      tried++;
      const after = picture({ ...c, counts: { ...c.counts, [h]: SINGLE.includes(h) ? 1 : 2 } });
      assert.equal(after, before, `adding ${h} to ${JSON.stringify(c.counts)} ${JSON.stringify(c.branches)} (${deceased})`);
    }
  }
  assert.ok(tried > 40000, `${tried} left-out relatives tried`);
});

test('the steps of some families', () => {
  const fam = (counts: Counts, branches: Branch[] = [], deceased: 'm' | 'f' = 'm'): Case => ({ ...EMPTY, deceased, counts, branches });
  // A wife and a son: no brothers, no uncles; the father and mother are always asked.
  assert.deepEqual(steps(fam({ wife: 1, son: 1 })), ['who', 'spouse', 'children', 'parents', 'elders', 'estate', 'checks']);
  assert.deepEqual(skipped(fam({ wife: 1, son: 1 })).map((s) => [s.step, s.why]), [['siblings', 'son'], ['agnates', 'son']]);
  // Both parents alive beside a son: nothing more to ask.
  assert.deepEqual(steps(fam({ wife: 1, son: 1, father: 1, mother: 1 })), ['who', 'spouse', 'children', 'parents', 'estate', 'checks']);
  // Daughters only: the brothers, and with none of them the uncles.
  assert.deepEqual(steps(fam({ wife: 1, daughter: 3 })), ['who', 'spouse', 'children', 'parents', 'elders', 'siblings', 'agnates', 'estate', 'checks']);
  assert.deepEqual(steps(fam({ wife: 1, daughter: 3, fullBrother: 2 })), ['who', 'spouse', 'children', 'parents', 'elders', 'siblings', 'estate', 'checks']);
  // A sister beside a daughter takes the rest: no uncles (art. 352).
  assert.deepEqual(skipped(fam({ daughter: 1, fullSister: 1 })).map((s) => [s.step, s.why]), [['agnates', 'sister']]);
  // Father and mother, no child: the brothers inherit nothing, but two of them lower the mother.
  const parents = fam({ father: 1, mother: 1 });
  assert.ok(steps(parents).includes('siblings') && siblingsForMother(parents));
  assert.ok(!asked(parents).has('fullNephew') && asked(parents).has('matBrother'));
  // A dead son's son stands as a son's son: no brothers.
  assert.ok(!steps(fam({ daughter: 1 }, [{ sex: 'm', sons: 1, daughters: 0 }])).includes('siblings'));
  // The father's mother is asked only when both parents are gone.
  assert.ok(!asked(fam({ father: 1 })).has('grandmotherF') && asked(fam({})).has('grandmotherF') && asked(fam({ father: 1 })).has('grandmotherM'));
});
