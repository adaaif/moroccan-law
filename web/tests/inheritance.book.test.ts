// A death before 5 February 2004 is counted by the 1958 book, and every article the page shows for it is that
// book's (IR27 of the inheritance review): the engine's citations and the ones the screens write themselves.
import test from 'node:test';
import assert from 'node:assert/strict';
import { inBook, treasuryCites } from '../src/topics/family/inheritance/book.ts';
import { EMPTY, type Case } from '../src/topics/family/inheritance/case.ts';
import { article, type Cite } from '../src/topics/family/inheritance/engine.ts';
import { solve } from '../src/topics/family/inheritance/solve.ts';

test("today's code keeps its own numbers", () => {
  const cites: Cite[] = [322, [349, 6], 49, 369];
  assert.deepEqual(inBook('70-03', cites), cites);
  assert.deepEqual(treasuryCites('70-03'), [[349, 6]]);
});

test('the 1958 book is cited by its own numbers', () => {
  assert.deepEqual(inBook('1958', [322]), [218]);                          // what leaves the estate first
  assert.deepEqual(inBook('1958', [369, 370, 371, 372]), [266, 267, 268, 269]);   // the compulsory bequest
  assert.deepEqual(inBook('1958', [361, 367, 368]), [258, 264, 265]);       // the Akdariyya, the Mubahala, the Minbariyya
  assert.deepEqual(inBook('1958', [[347, 2], [359, 1]]), [[244, 2], [256, 1]]);   // the mother's sixth beside two siblings
  assert.deepEqual(inBook('1958', [277, 280, 303]), [173, 176, 199]);       // a will
  assert.deepEqual(inBook('1958', [315, 316, 317, 318, 319, 320]), [211, 212, 213, 214, 215, 216]);   // a «تنزيل»
  assert.deepEqual(treasuryCites('1958'), [246, 297]);
});

test('an article outside books 5 and 6 has no place in the 1958 book', () => {
  assert.deepEqual(inBook('1958', [49]), []);
  assert.deepEqual(inBook('1958', [49, 322]), [218]);
});

test('a death of 1990: every article the engine gives is within the 1958 book', () => {
  const families: Partial<Case>[] = [
    { counts: { wife: 1, daughter: 1 } },
    { counts: { wife: 1, son: 1, daughter: 2, mother: 1 } },
    { deceased: 'f', counts: { husband: 1, mother: 1, grandfather: 1, fullSister: 1 } },
    { counts: { wife: 1, son: 1 }, branches: [{ sex: 'm', sons: 1, daughters: 1, spouse: false, parent: false }] },
    { counts: { mother: 1, fullBrother: 2, patBrother: 1, matSister: 1 } },
  ];
  for (const f of families) {
    const a = solve({ ...EMPTY, died: '1990', ...f } as Case);
    assert.equal(a.state, 'ok');
    if (a.state !== 'ok') continue;
    assert.equal(a.result.rules.code, '1958');
    const cites = [...a.result.lines.flatMap((l) => l.cites), ...a.result.excluded.flatMap((e) => e.cites)];
    assert.ok(cites.length > 0);
    for (const c of cites) assert.ok(article(c) >= 173 && article(c) <= 297, `article ${article(c)} is not the 1958 book's`);
  }
});
