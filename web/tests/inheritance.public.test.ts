// Cases whose answers were published before the calculator existed: the named cases every manual of «الفرائض» gives
// with their numbers, and a worked example from the article the bequest's reading rests on (choices.ts names it).
// The code's own named cases (arts 360 to 368) are in inheritance.cases.json. Each expected number here is the
// published one, as a count of `of` for one person.
import test from 'node:test';
import assert from 'node:assert/strict';
import { EMPTY, type Case } from '../src/topics/family/inheritance/case.ts';
import { solve } from '../src/topics/family/inheritance/solve.ts';

type Public = { name: string; of: number; c: Partial<Case>; each: Record<string, number>; rise?: [number, number] };

const CASES: Public[] = [
  // 600 dinars: 75 to the wife, 100 to the mother, 200 to each daughter, 2 to each brother and 1 to the sister.
  { name: 'الدينارية الكبرى', of: 600, c: { counts: { wife: 1, mother: 1, daughter: 2, fullBrother: 12, fullSister: 1 } },
    each: { wife: 75, mother: 100, daughter: 200, fullBrother: 2, fullSister: 1 } },
  // Seventeen women and seventeen dinars, one each: 12 rises to 17.
  { name: 'أم الأرامل، السبعة عشرية', of: 17, rise: [12, 17],
    c: { counts: { wife: 3, grandmotherM: 1, grandmotherF: 1, matSister: 4, fullSister: 8 } },
    each: { wife: 1, grandmotherM: 1, grandmotherF: 1, matSister: 1, fullSister: 1 } },
  // The highest rise there is: 6 to 10.
  { name: 'أم الفروخ، الشريحية', of: 10, rise: [6, 10],
    c: { deceased: 'f', counts: { husband: 1, mother: 1, fullSister: 2, matBrother: 1, matSister: 1 } },
    each: { husband: 3, mother: 1, fullSister: 2, matBrother: 1, matSister: 1 } },
  { name: 'المروانية', of: 9, rise: [6, 9], c: { deceased: 'f', counts: { husband: 1, fullSister: 2, matSister: 2 } },
    each: { husband: 3, fullSister: 2, matSister: 1 } },
  // The grandfather beside brothers of both kinds (art. 360): the three cases named after Zayd.
  { name: 'عشرينية زيد', of: 20, c: { counts: { grandfather: 1, fullSister: 1, patSister: 2 } },
    each: { grandfather: 8, fullSister: 10, patSister: 1 } },
  { name: 'مختصرة زيد', of: 54, c: { counts: { mother: 1, grandfather: 1, fullSister: 1, patBrother: 1, patSister: 1 } },
    each: { mother: 9, grandfather: 15, fullSister: 27, patBrother: 2, patSister: 1 } },
  { name: 'تسعينية زيد', of: 90, c: { counts: { mother: 1, grandfather: 1, fullSister: 1, patBrother: 2, patSister: 1 } },
    each: { mother: 15, grandfather: 25, fullSister: 45, patBrother: 2, patSister: 1 } },
  // Two deaths: a man leaves his parents and two daughters, then a daughter dies before the division, leaving her
  // grandfather, her father's mother and her sister. From 54.
  { name: 'المأمونية، والميت الأول رجل', of: 54,
    c: { counts: { father: 1, mother: 1, daughter: 2 }, later: [{ heir: 'daughter', counts: { grandfather: 1, grandmotherF: 1, fullSister: 1 }, branches: [] }] },
    each: { father: 9, mother: 9, daughter: 18, 'l0.grandfather': 10, 'l0.grandmotherF': 3, 'l0.fullSister': 5 } },
];

for (const k of CASES) {
  test(k.name, () => {
    const a = solve({ ...EMPTY, ...k.c } as Case);
    assert.equal(a.state, 'ok');
    if (a.state !== 'ok') return;
    const got = Object.fromEntries(a.shares.map((s) => {
      assert.equal((s.each.n * BigInt(k.of)) % s.each.d, 0n, `${s.key} is a whole number of ${k.of}`);
      return [s.key, Number((s.each.n * BigInt(k.of)) / s.each.d)];
    }));
    assert.deepEqual(got, k.each);
    if (k.rise) assert.deepEqual([a.result.base, a.result.awl], k.rise.map(BigInt));
  });
}

// H. Mansif, «الوصية الواجبة علما وعملا وفي تزاحمها مع باقي الوصايا»: two sons, a daughter and the daughter of a son
// who died first, 700 left. The article prints the reading it argues against: 200 to the granddaughter, her father's
// whole share. By the reading the Court of Cassation follows she takes her own part of it, a half: 100.
test('the article\'s example: both readings of the bequest', () => {
  const a = solve({ ...EMPTY, counts: { son: 2, daughter: 1 }, branches: [{ sex: 'm', sons: 0, daughters: 1, spouse: false, parent: false }] });
  assert.equal(a.state, 'ok');
  if (a.state !== 'ok') return;
  const of = (key: string) => { const s = a.shares.find((x) => x.key === key)!; return Number((s.each.n * 700n) / s.each.d); };
  assert.equal(of('b0.daughter'), 100);
  assert.equal(of('son'), 240);
  assert.equal(of('daughter'), 120);
  assert.ok(a.result.otherBequest);
  assert.equal(Number((a.result.otherBequest!.n * 700n) / a.result.otherBequest!.d), 200);
});
