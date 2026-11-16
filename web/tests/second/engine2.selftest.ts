// Cases worked by hand from book 6 of the Family Code (arts 321–372), for the second engine.
// Run: cd web && node --test tests/second/
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { second } from './engine2.ts';
import type { Heir, Input, Branch } from './engine2.ts';

type Each = Partial<Record<Heir, string>>;

const SINGLE = new Set<string>(['husband', 'father', 'mother', 'grandfather', 'grandmotherM', 'grandmotherF']);

function frac(s: string): [bigint, bigint] {
  const [n, d] = s.split('/');
  return [BigInt(n), BigInt(d)];
}

/** Everything the output hands out, person by person, must make the whole estate. */
function wholeEstate(input: Input, each: Each, bequest: { son: string; daughter: string }[], treasury: string) {
  const counts: Record<string, number> = { ...input.counts };
  for (const b of input.predeceased ?? []) {
    if (b.sex === 'm') {
      counts.sonsSon = (counts.sonsSon ?? 0) + b.sons;
      counts.sonsDaughter = (counts.sonsDaughter ?? 0) + b.daughters;
    }
  }
  let n = 0n, d = 1n;
  const plus = (s: string, k: number) => {
    const [a, b] = frac(s);
    n = n * b + a * BigInt(k) * d;
    d = d * b;
  };
  for (const [h, s] of Object.entries(each)) plus(s as string, SINGLE.has(h) ? 1 : counts[h]);
  (input.predeceased ?? []).forEach((b: Branch, i) => {
    plus(bequest[i].son, b.sons);
    plus(bequest[i].daughter, b.daughters);
  });
  plus(treasury, 1);
  assert.equal(n, d, `the parts make ${n}/${d}, not the whole estate`);
}

function check(
  name: string,
  input: Input,
  each: Each,
  more: { bequest?: [string, string][]; treasury?: string } = {},
) {
  test(name, () => {
    const out = second(input);
    assert.ok(!('stop' in out), 'unexpected stop');
    if ('stop' in out) return;
    assert.deepEqual(out.each, each);
    assert.equal(out.treasury, more.treasury ?? '0/1');
    assert.deepEqual(out.bequest, (more.bequest ?? []).map(([son, daughter]) => ({ son, daughter })));
    wholeEstate(input, out.each, out.bequest, out.treasury);
  });
}

function mixed(name: string, input: Input) {
  test(name, () => assert.deepEqual(second(input), { stop: 'mixed' }));
}

const M = (counts: Input['counts'], predeceased?: Branch[]): Input => ({ deceased: 'm', counts, predeceased });
const F = (counts: Input['counts'], predeceased?: Branch[]): Input => ({ deceased: 'f', counts, predeceased });

// ---------------------------------------------------------------------------------------------------------------
// Arts 360–368, the special cases, with the numbers the articles print.

check('art. 366, the Gharrawayn with a wife: 1/4, a third of the rest (1/4), the rest to the father',
  M({ wife: 1, father: 1, mother: 1 }), { wife: '1/4', mother: '1/4', father: '1/2' });
check('art. 366, the Gharrawayn with a husband: 1/2, a third of the rest (1/6), the rest to the father',
  F({ husband: 1, father: 1, mother: 1 }), { husband: '1/2', mother: '1/6', father: '1/3' });
check('art. 366 does not reach the grandfather: husband 1/2, mother 1/3 of the whole, grandfather the rest',
  F({ husband: 1, mother: 1, grandfather: 1 }), { husband: '1/2', mother: '1/3', grandfather: '1/6' });
check('art. 367, the Mubahala: from 6, raised to 8: husband 3, full sister 3, mother 2',
  F({ husband: 1, mother: 1, fullSister: 1 }), { husband: '3/8', fullSister: '3/8', mother: '1/4' });
check('art. 367 with a paternal sister', F({ husband: 1, mother: 1, patSister: 1 }),
  { husband: '3/8', patSister: '3/8', mother: '1/4' });
check('art. 368, the Minbariyya: from 24, raised to 27: daughters 16, parents 8, wife 3 (her eighth becomes a ninth)',
  M({ wife: 1, daughter: 2, father: 1, mother: 1 }),
  { wife: '1/9', daughter: '8/27', father: '4/27', mother: '4/27' });
check('art. 361, the Akdariyya: of 27, husband 9, mother 6, sister 4, grandfather 8',
  F({ husband: 1, fullSister: 1, grandfather: 1, mother: 1 }),
  { husband: '1/3', mother: '2/9', fullSister: '4/27', grandfather: '8/27' });
check('art. 361, the Akdariyya with a paternal sister', F({ husband: 1, patSister: 1, grandfather: 1, mother: 1 }),
  { husband: '1/3', mother: '2/9', patSister: '4/27', grandfather: '8/27' });
check('art. 364, the Kharqa: mother a third, the rest grandfather and sister two to one',
  M({ mother: 1, grandfather: 1, fullSister: 1 }), { mother: '1/3', grandfather: '4/9', fullSister: '2/9' });
check('art. 364 with a paternal sister', M({ mother: 1, grandfather: 1, patSister: 1 }),
  { mother: '1/3', grandfather: '4/9', patSister: '2/9' });
check('art. 362, the Malikiyya: husband 1/2, mother 1/6, grandfather the rest; paternal brother and uterine nothing',
  F({ husband: 1, mother: 1, grandfather: 1, patBrother: 1, matBrother: 2 }),
  { husband: '1/2', mother: '1/6', grandfather: '1/3' });
check('art. 362 with both grandmothers (no mother), two paternal brothers and two uterine sisters',
  F({ husband: 1, grandmotherM: 1, grandmotherF: 1, grandfather: 1, patBrother: 2, matSister: 2 }),
  { husband: '1/2', grandmotherM: '1/12', grandmotherF: '1/12', grandfather: '1/3' });
check('art. 363, like the Malikiyya: a full brother takes nothing beside the grandfather',
  F({ husband: 1, mother: 1, grandfather: 1, fullBrother: 1, matBrother: 1, matSister: 1 }),
  { husband: '1/2', mother: '1/6', grandfather: '1/3' });
check('art. 363 with the mother\'s mother and two full brothers',
  F({ husband: 1, grandmotherM: 1, grandfather: 1, fullBrother: 2, matSister: 2 }),
  { husband: '1/2', grandmotherM: '1/6', grandfather: '1/3' });
mixed('reading 4: full and paternal brothers under the conditions of arts 362–363',
  F({ husband: 1, mother: 1, grandfather: 1, fullBrother: 1, patBrother: 1, matBrother: 2 }));
mixed('reading 4: a full brother with a full sister', F({ husband: 1, mother: 1, grandfather: 1, fullBrother: 1, fullSister: 1, matBrother: 2 }));
mixed('reading 4: a paternal brother with a paternal sister, the father\'s mother',
  F({ husband: 1, grandmotherF: 1, grandfather: 1, patBrother: 1, patSister: 1, matSister: 2 }));
mixed('reading 4: a paternal brother with a full sister', F({ husband: 1, mother: 1, grandfather: 1, patBrother: 1, fullSister: 1, matBrother: 2 }));
check('reading 4: sisters only under the same conditions go by the ordinary rules (best of 1/6, 1/9, 2/9)',
  F({ husband: 1, mother: 1, grandfather: 1, fullSister: 1, matBrother: 2 }),
  { husband: '1/2', mother: '1/6', grandfather: '2/9', fullSister: '1/9' });
check('one uterine brother only: not art. 362; the grandfather shares a third (both 1/6)',
  F({ husband: 1, mother: 1, grandfather: 1, patBrother: 1, matBrother: 1 }),
  { husband: '1/2', mother: '1/6', grandfather: '1/6', patBrother: '1/6' });
check('art. 365, the Mushtaraka: the third by head among uterine and full siblings, male and female alike',
  F({ husband: 1, mother: 1, matBrother: 2, fullBrother: 1, fullSister: 1 }),
  { husband: '1/2', mother: '1/6', matBrother: '1/12', fullBrother: '1/12', fullSister: '1/12' });
check('art. 365 with a grandmother; paternal brothers take nothing',
  F({ husband: 1, grandmotherM: 1, matSister: 2, fullBrother: 1, patBrother: 2 }),
  { husband: '1/2', grandmotherM: '1/6', matSister: '1/9', fullBrother: '1/9' });
check('no Mushtaraka with full sisters only: their half by \'awl (6 raised to 9)',
  F({ husband: 1, mother: 1, matBrother: 2, fullSister: 1 }),
  { husband: '1/3', mother: '1/9', matBrother: '1/9', fullSister: '1/3' });

// ---------------------------------------------------------------------------------------------------------------
// The grandfather with full or paternal siblings (arts 354, 360, 361, 364; reading 3).

check('art. 360, the mu\'adda (Zayd\'s ten): grandfather 2/5; the full sister completes her half; paternal brother 1/10',
  M({ grandfather: 1, fullSister: 1, patBrother: 1 }), { grandfather: '2/5', fullSister: '1/2', patBrother: '1/10' });
check('art. 360 (Zayd\'s twenty): two paternal sisters share the tenth left over',
  M({ grandfather: 1, fullSister: 1, patSister: 2 }), { grandfather: '2/5', fullSister: '1/2', patSister: '1/20' });
check('art. 360 with the mother (the Mukhtasara, of 54): 9, 15, 27, 2, 1',
  M({ mother: 1, grandfather: 1, fullSister: 1, patBrother: 1, patSister: 1 }),
  { mother: '1/6', grandfather: '5/18', fullSister: '1/2', patBrother: '1/27', patSister: '1/54' });
check('art. 360 with the mother (the Tis\'iniyya, of 90): 15, 25, 45, 2 + 2, 1',
  M({ mother: 1, grandfather: 1, fullSister: 1, patBrother: 2, patSister: 1 }),
  { mother: '1/6', grandfather: '5/18', fullSister: '1/2', patBrother: '1/45', patSister: '1/90' });
check('art. 360: a full brother counts the paternal one, then takes his part', M({ grandfather: 1, fullBrother: 1, patBrother: 1 }),
  { grandfather: '1/3', fullBrother: '2/3' });
check('art. 360: two full sisters take back the paternal sister\'s part', M({ grandfather: 1, fullSister: 2, patSister: 1 }),
  { grandfather: '2/5', fullSister: '3/10' });
check('art. 354 §1: a third of the whole beats sharing with five sisters', M({ grandfather: 1, fullSister: 5 }),
  { grandfather: '1/3', fullSister: '2/15' });
check('art. 354 §3: sharing beside a daughter (1/4 against 1/6 and 1/6)', M({ grandfather: 1, daughter: 1, fullBrother: 1 }),
  { daughter: '1/2', grandfather: '1/4', fullBrother: '1/4' });
check('art. 361: no share for the sister beside the grandfather and a daughter; they share two to one',
  M({ grandfather: 1, daughter: 1, fullSister: 1 }), { daughter: '1/2', grandfather: '1/3', fullSister: '1/6' });
check('art. 354 §3: a third of what is left (wife and four full brothers)', M({ wife: 1, grandfather: 1, fullBrother: 4 }),
  { wife: '1/4', grandfather: '1/4', fullBrother: '1/8' });
check('art. 354 §3: a sixth of the whole (husband, grandmother, three full brothers)',
  F({ husband: 1, grandmotherM: 1, grandfather: 1, fullBrother: 3 }),
  { husband: '1/2', grandmotherM: '1/6', grandfather: '1/6', fullBrother: '1/18' });
check('art. 354 §3: sharing with the mother present', M({ mother: 1, grandfather: 1, fullBrother: 1 }),
  { mother: '1/3', grandfather: '1/3', fullBrother: '1/3' });
check('reading 3: the shares leave exactly a sixth, the grandfather takes it, the brother nothing',
  M({ grandfather: 1, daughter: 2, mother: 1, fullBrother: 1 }), { daughter: '1/3', mother: '1/6', grandfather: '1/6' });
check('reading 3: the shares leave less than a sixth, the grandfather takes a sixth by \'awl (12 raised to 13)',
  F({ husband: 1, daughter: 2, grandfather: 1, fullBrother: 1 }), { husband: '3/13', daughter: '4/13', grandfather: '2/13' });
check('art. 360 beside a daughter: the full sister takes all the siblings\' part',
  M({ daughter: 1, grandfather: 1, fullSister: 1, patBrother: 1 }), { daughter: '1/2', grandfather: '1/5', fullSister: '3/10' });
check('art. 347 §7: the grandfather beside a son takes a sixth; the brother is out',
  M({ son: 1, grandfather: 1, fullBrother: 1 }), { grandfather: '1/6', son: '5/6' });
check('art. 353: the grandfather beside a daughter, a sixth and the rest', M({ daughter: 1, grandfather: 1 }),
  { daughter: '1/2', grandfather: '1/2' });

// ---------------------------------------------------------------------------------------------------------------
// The ordinary rules, 'awl and radd.

check('husband and son', F({ husband: 1, son: 1 }), { husband: '1/4', son: '3/4' });
check('wife, son and daughter', M({ wife: 1, son: 1, daughter: 1 }), { wife: '1/8', son: '7/12', daughter: '7/24' });
check('three wives, two daughters, father: a sixth and the rest', M({ wife: 3, daughter: 2, father: 1 }),
  { wife: '1/24', daughter: '1/3', father: '5/24' });
check('\'awl: husband and two full sisters, 6 raised to 7', F({ husband: 1, fullSister: 2 }), { husband: '3/7', fullSister: '2/7' });
check('\'awl: the mother of the chicks, 6 raised to 10', F({ husband: 1, mother: 1, fullSister: 2, matBrother: 2 }),
  { husband: '3/10', mother: '1/10', fullSister: '1/5', matBrother: '1/10' });
check('radd: mother and daughter', M({ mother: 1, daughter: 1 }), { mother: '1/4', daughter: '3/4' });
check('radd reaches the husband (reading 1)', F({ husband: 1, daughter: 1 }), { husband: '1/3', daughter: '2/3' });
check('radd: wife, mother, two uterine brothers', M({ wife: 1, mother: 1, matBrother: 2 }),
  { wife: '1/3', mother: '2/9', matBrother: '2/9' });
check('radd: two wives alone', M({ wife: 2 }), { wife: '1/2' });
check('no heir: everything to the Treasury', M({}), {}, { treasury: '1/1' });
check('a husband given for a dead man is ignored', M({ husband: 1 }), {}, { treasury: '1/1' });
check('art. 359 §1: two siblings bring the mother down even when the father shuts them out',
  M({ father: 1, mother: 1, fullBrother: 1, fullSister: 1 }), { mother: '1/6', father: '5/6' });
check('art. 359 §1: a full brother and a uterine sister', M({ mother: 1, fullBrother: 1, matSister: 1 }),
  { mother: '1/6', matSister: '1/6', fullBrother: '2/3' });
check('art. 347 §3: son\'s daughters complete the two thirds', M({ daughter: 1, sonsDaughter: 2, fullUncle: 1 }),
  { daughter: '1/2', sonsDaughter: '1/12', fullUncle: '1/3' });
check('art. 347 §4: a paternal sister completes the two thirds (then radd)', M({ fullSister: 1, patSister: 1 }),
  { fullSister: '3/4', patSister: '1/4' });

// ---------------------------------------------------------------------------------------------------------------
// Art. 358, each exclusion the 23 kinds can express.

check('§1: the son shuts out the son\'s son', M({ son: 1, sonsSon: 1 }), { son: '1/1' });
check('§2: the son shuts out the son\'s daughter', M({ son: 1, daughter: 1, sonsDaughter: 1 }), { son: '2/3', daughter: '1/3' });
check('§2: two daughters shut out the son\'s daughter', M({ daughter: 2, sonsDaughter: 1, fullBrother: 1 }),
  { daughter: '1/3', fullBrother: '1/3' });
check('§2: unless a son\'s son of her rank makes her residuary', M({ daughter: 2, sonsDaughter: 1, sonsSon: 1 }),
  { daughter: '1/3', sonsSon: '2/9', sonsDaughter: '1/9' });
check('§3: the father shuts out the grandfather', M({ father: 1, grandfather: 1, son: 1 }), { father: '1/6', son: '5/6' });
check('§4: the son\'s son shuts out the full sister', M({ wife: 1, sonsSon: 1, fullSister: 1 }), { wife: '1/8', sonsSon: '7/8' });
check('§5: the full brother shuts out the paternal siblings', M({ fullBrother: 1, patBrother: 1, patSister: 1 }),
  { fullBrother: '1/1' });
check('§5: the full sister does not', M({ fullSister: 1, patBrother: 1 }), { fullSister: '1/2', patBrother: '1/2' });
check('§6: two full sisters shut out the paternal sister', M({ fullSister: 2, patSister: 1, fullUncle: 1 }),
  { fullSister: '1/3', fullUncle: '1/3' });
check('§6: unless a paternal brother is with her', M({ fullSister: 2, patSister: 1, patBrother: 1 }),
  { fullSister: '1/3', patBrother: '2/9', patSister: '1/9' });
check('art. 352: a full sister beside a daughter stands as a full brother', M({ daughter: 1, fullSister: 1, patBrother: 1 }),
  { daughter: '1/2', fullSister: '1/2' });
check('art. 352: a paternal sister beside a daughter shuts out the nephew', M({ daughter: 1, patSister: 1, fullNephew: 1 }),
  { daughter: '1/2', patSister: '1/2' });
check('§7: the grandfather shuts out the full nephew', M({ grandfather: 1, fullNephew: 1 }), { grandfather: '1/1' });
check('§7: the paternal brother shuts out the full nephew', M({ patBrother: 1, fullNephew: 1 }), { patBrother: '1/1' });
check('§7: a full sister by share leaves the rest to the nephew', M({ fullSister: 1, fullNephew: 1 }),
  { fullSister: '1/2', fullNephew: '1/2' });
check('§8: the full nephew shuts out the paternal nephew', M({ fullNephew: 2, patNephew: 1 }), { fullNephew: '1/2' });
check('§9: the paternal nephew shuts out the full uncle', M({ patNephew: 1, fullUncle: 1 }), { patNephew: '1/1' });
check('§10: the full uncle shuts out the paternal uncle', M({ fullUncle: 1, patUncle: 1 }), { fullUncle: '1/1' });
check('§11: the paternal uncle shuts out the full cousin', M({ patUncle: 1, fullCousin: 1 }), { patUncle: '1/1' });
check('§12: the full cousin shuts out the paternal cousin', M({ fullCousin: 3, patCousin: 1 }), { fullCousin: '1/3' });
check('a paternal cousin takes the rest after the wife', M({ wife: 1, patCousin: 1 }), { wife: '1/4', patCousin: '3/4' });
check('§13: the daughter shuts out the uterine brother', M({ daughter: 1, matBrother: 1, fullUncle: 1 }),
  { daughter: '1/2', fullUncle: '1/2' });
check('§13: the son\'s daughter shuts out the uterine sister', M({ sonsDaughter: 1, matSister: 1, fullUncle: 1 }),
  { sonsDaughter: '1/2', fullUncle: '1/2' });
check('§13: the grandfather shuts out the uterine brother', M({ grandfather: 1, matBrother: 1 }), { grandfather: '1/1' });
check('§13: the father shuts out the uterine sister', M({ father: 1, matSister: 1 }), { father: '1/1' });
check('§14: the mother shuts out the mother\'s mother', M({ mother: 1, grandmotherM: 1, father: 1 }),
  { mother: '1/3', father: '2/3' });
check('§15: the father shuts out his own mother, not the mother\'s mother', M({ father: 1, grandmotherF: 1, grandmotherM: 1 }),
  { grandmotherM: '1/6', father: '5/6' });
check('art. 347 §6: two grandmothers share the sixth', M({ grandmotherM: 1, grandmotherF: 1, son: 1 }),
  { grandmotherM: '1/12', grandmotherF: '1/12', son: '5/6' });
check('the grandfather does not shut out the father\'s mother', M({ grandmotherF: 1, grandfather: 1 }),
  { grandmotherF: '1/6', grandfather: '5/6' });

// ---------------------------------------------------------------------------------------------------------------
// The compulsory bequest (arts 369–372, reading 8 as amended: stage 2 counts only spouse, parent, grandparent through
// the deceased and children, and has no radd; what the children do not take goes back to the first estate).

check('a predeceased son beside a living son: half each in stage 1, cut to a third',
  M({ son: 1 }, [{ sex: 'm', sons: 1, daughters: 1 }]), { son: '2/3' }, { bequest: [['2/9', '1/9']] });
check('a predeceased daughter beside a son and a daughter: her quarter to her two sons',
  M({ son: 1, daughter: 1 }, [{ sex: 'f', sons: 2, daughters: 0 }]), { son: '1/2', daughter: '1/4' },
  { bequest: [['1/8', '0/1']] });
check('stage 2 with her husband and her mother, no radd: her daughter keeps her half, 7/24 × 1/2',
  M({ wife: 1, son: 1 }, [{ sex: 'f', sons: 0, daughters: 1, spouse: true, parent: true }]),
  { wife: '41/384', son: '287/384' }, { bequest: [['0/1', '7/48']] });
check('a daughter\'s branch beside a son\'s son who inherits', M({ sonsSon: 1 }, [{ sex: 'f', sons: 1, daughters: 0 }]),
  { sonsSon: '2/3' }, { bequest: [['1/3', '0/1']] });
check('art. 371: a son\'s children who inherit are owed nothing', M({ daughter: 1 }, [{ sex: 'm', sons: 1, daughters: 0 }]),
  { daughter: '1/2', sonsSon: '1/2' }, { bequest: [['0/1', '0/1']] });
check('a son\'s son left nothing by \'awl is owed; stage 2 gives the mother\'s mother a sixth',
  F({ husband: 1, father: 1, mother: 1, daughter: 2 }, [{ sex: 'm', sons: 1, daughters: 0 }]),
  { husband: '119/720', father: '119/1080', mother: '119/1080', daughter: '119/540' }, { bequest: [['25/144', '0/1']] });
check('two daughters\' branches over a third (8/19 and 4/19), each cut in proportion',
  M({ wife: 1 }, [{ sex: 'f', sons: 1, daughters: 0 }, { sex: 'f', sons: 0, daughters: 1 }]),
  { wife: '2/3' }, { bequest: [['2/9', '0/1'], ['0/1', '1/9']] });
check('a dead daughter\'s father is the living husband: he takes half in stage 2',
  F({ husband: 1, son: 1 }, [{ sex: 'f', sons: 0, daughters: 1, parent: true }]),
  { husband: '7/32', son: '21/32' }, { bequest: [['0/1', '1/8']] });
check('the deceased\'s father is the dead son\'s grandfather in stage 2',
  M({ father: 1, son: 1 }, [{ sex: 'm', sons: 0, daughters: 2 }]),
  { father: '13/108', son: '65/108' }, { bequest: [['0/1', '5/36']] });
check('the deceased\'s brother is not counted in stage 2; the only granddaughter keeps half, 1/3 × 1/2',
  M({ daughter: 1, fullBrother: 1 }, [{ sex: 'f', sons: 0, daughters: 1 }]),
  { daughter: '5/12', fullBrother: '5/12' }, { bequest: [['0/1', '1/6']] });
check('a son\'s son in the counts beside a living son: the branch is owed, the given grandson takes nothing',
  M({ son: 1, sonsSon: 1 }, [{ sex: 'm', sons: 1, daughters: 0 }]), { son: '2/3' }, { bequest: [['1/3', '0/1']] });
check('a dead woman\'s living son is not counted in stage 2; the only granddaughter keeps half',
  F({ son: 1 }, [{ sex: 'f', sons: 0, daughters: 1 }]), { son: '5/6' }, { bequest: [['0/1', '1/6']] });
check('the dead son\'s wife and mother in stage 2; his father\'s mother shut out by his mother',
  M({ wife: 1, mother: 1, son: 1 }, [{ sex: 'm', sons: 1, daughters: 0, spouse: true, parent: true }]),
  { wife: '863/9216', mother: '863/6912', son: '14671/27648' }, { bequest: [['289/1152', '0/1']] });
check('a son\'s and a daughter\'s branch together, under a third once his daughter keeps only half (1/7 + 1/7)',
  M({ son: 2 }, [{ sex: 'm', sons: 0, daughters: 1 }, { sex: 'f', sons: 1, daughters: 1 }]),
  { son: '5/14' }, { bequest: [['0/1', '1/7'], ['2/21', '1/21']] });
check('two predeceased sons of a dead woman: 1/6 and 1/3, cut to a third together',
  F({ son: 1 }, [{ sex: 'm', sons: 0, daughters: 1 }, { sex: 'm', sons: 1, daughters: 0 }]),
  { son: '2/3' }, { bequest: [['0/1', '1/9'], ['2/9', '0/1']] });
check('two predeceased sons, \'awl: his daughter half, his son what the mother\'s mother leaves',
  F({ husband: 1, father: 1, mother: 1, daughter: 2 }, [{ sex: 'm', sons: 0, daughters: 1 }, { sex: 'm', sons: 1, daughters: 0 }]),
  { husband: '22/135', father: '44/405', mother: '44/405', daughter: '88/405' },
  { bequest: [['0/1', '5/72'], ['25/216', '0/1']] });
check('a dead woman: the predeceased son\'s son is not counted in his aunt\'s stage 2; her daughter keeps half',
  F({}, [{ sex: 'f', sons: 0, daughters: 1 }, { sex: 'm', sons: 1, daughters: 0 }]),
  { sonsSon: '3/4' }, { bequest: [['0/1', '1/4'], ['0/1', '0/1']] });
check('a dead man: the same family gives the same half (no radd to the only granddaughter)',
  M({}, [{ sex: 'f', sons: 0, daughters: 1 }, { sex: 'm', sons: 1, daughters: 0 }]),
  { sonsSon: '3/4' }, { bequest: [['0/1', '1/4'], ['0/1', '0/1']] });
check('two granddaughters take two thirds of their mother\'s share, 1/3 × 2/3',
  M({ son: 1 }, [{ sex: 'f', sons: 0, daughters: 2 }]), { son: '7/9' }, { bequest: [['0/1', '1/9']] });
check('the deceased\'s grandfather stands in for his dead father in stage 2: a sixth before the children',
  M({ grandfather: 1, son: 1, daughter: 1 }, [{ sex: 'm', sons: 1, daughters: 1 }]),
  { grandfather: '13/108', son: '65/162', daughter: '65/324' }, { bequest: [['5/27', '5/54']] });
check('the deceased\'s mother is the dead son\'s father\'s mother in stage 2',
  M({ mother: 1, son: 1, daughter: 1 }, [{ sex: 'm', sons: 1, daughters: 0 }]),
  { mother: '13/108', son: '65/162', daughter: '65/324' }, { bequest: [['5/18', '0/1']] });
check('\'awl inside stage 2: husband, mother, grandfather and two daughters, 12 raised to 15',
  M({ wife: 1, father: 1, son: 1 }, [{ sex: 'f', sons: 0, daughters: 2, spouse: true, parent: true }]),
  { wife: '59/540', father: '59/405', son: '1003/1620' }, { bequest: [['0/1', '17/270']] });
check('radd in stage 1 (2/3), none in stage 2: beside her husband and father the only daughter keeps half',
  F({ husband: 1 }, [{ sex: 'f', sons: 0, daughters: 1, spouse: true, parent: true }]),
  { husband: '2/3' }, { bequest: [['0/1', '1/3']] });
check('no heir but a daughter\'s children: a third to them, the rest to the Treasury',
  M({}, [{ sex: 'f', sons: 1, daughters: 1 }]), {}, { bequest: [['2/9', '1/9']], treasury: '2/3' });
mixed('a mixed case stays mixed with a bequest', F({ husband: 1, mother: 1, grandfather: 1, fullBrother: 1, fullSister: 1, matBrother: 2 },
  [{ sex: 'f', sons: 1, daughters: 0 }]));
