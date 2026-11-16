/** The questions the calculator asks, in the order of the law, each only if it can change the answer (IR13 of
 *  the inheritance review). A relative who could not move anyone's share in this family is not asked about: with a
 *  son alive the brothers are not, and the page says so once with the article. The tree still lets anyone be added.
 *  Pure; the test adds every relative this file leaves out to thousands of families and checks nothing moves. */
import type { Cite, Heir } from './engine.ts';
import type { Case } from './case.ts';

export type Step = 'who' | 'spouse' | 'children' | 'parents' | 'elders' | 'siblings' | 'agnates' | 'estate' | 'checks';

const n = (c: Case, h: Heir) => c.counts[h] ?? 0;

/** Who stands below the deceased: a son, or a dead son's son, shuts out the brothers; any child or son's child lowers
 *  the spouse and the mother. A son's children are those of the dead sons, or given directly. */
function below(c: Case) {
  const sonsSons = n(c, 'sonsSon') + c.branches.filter((b) => b.sex === 'm').reduce((s, b) => s + b.sons, 0);
  const sonsDaughters = n(c, 'sonsDaughter') + c.branches.filter((b) => b.sex === 'm').reduce((s, b) => s + b.daughters, 0);
  const male = n(c, 'son') + sonsSons > 0;
  const female = n(c, 'daughter') + sonsDaughters > 0;
  return { male, female, any: male || female };
}

/** The relatives worth asking about in this family, by kind. */
export function asked(c: Case): Set<Heir> {
  const d = below(c);
  const father = n(c, 'father') > 0, mother = n(c, 'mother') > 0, grandfather = !father && n(c, 'grandfather') > 0;
  const ask = new Set<Heir>([c.deceased === 'm' ? 'wife' : 'husband', 'son', 'daughter', 'father', 'mother']);
  // The grandparents stand in for a parent who is gone (art. 358 §3, §14, §15).
  if (!father) ask.add('grandfather');
  if (!mother) ask.add('grandmotherM');
  if (!mother && !father) ask.add('grandmotherF');
  // Brothers and sisters inherit when no son, son's son or father stands above them (art. 358 §4, §5); shut out or not,
  // two of them bring the mother down to a sixth when there is no child (arts 346, 359 §1).
  const lowerMother = mother && !d.any;
  if ((!d.male && !father) || lowerMother) for (const h of ['fullBrother', 'fullSister', 'patBrother', 'patSister'] as Heir[]) ask.add(h);
  // Those by the mother are shut out by any child, the father and the grandfather (art. 358 §13), but two of them
  // still lower the mother, and beside the grandfather they make the cases of arts 362 and 363.
  if (!d.any && (!father || mother)) { ask.add('matBrother'); ask.add('matSister'); }
  // The far agnates take only what no nearer one does (arts 349, 350).
  const sisterTakesRest = (n(c, 'fullSister') > 0 || n(c, 'patSister') > 0) && d.female;
  if (!d.male && !father && !grandfather && !n(c, 'fullBrother') && !n(c, 'patBrother') && !sisterTakesRest)
    for (const h of ['fullNephew', 'patNephew', 'fullUncle', 'patUncle', 'fullCousin', 'patCousin'] as Heir[]) ask.add(h);
  return ask;
}

const ELDERS: Heir[] = ['grandfather', 'grandmotherM', 'grandmotherF'];
const SIBLINGS: Heir[] = ['fullBrother', 'fullSister', 'patBrother', 'patSister', 'matBrother', 'matSister'];
const AGNATES: Heir[] = ['fullNephew', 'patNephew', 'fullUncle', 'patUncle', 'fullCousin', 'patCousin'];
export const KIN: Partial<Record<Step, Heir[]>> = { elders: ELDERS, siblings: SIBLINGS, agnates: AGNATES };

/** The steps this family is asked, in order. */
export function steps(c: Case): Step[] {
  const ask = asked(c);
  const has = (hs: Heir[]) => hs.some((h) => ask.has(h));
  return ['who', 'spouse', 'children', 'parents', ...(has(ELDERS) ? ['elders' as Step] : []), ...(has(SIBLINGS) ? ['siblings' as Step] : []),
    ...(has(AGNATES) ? ['agnates' as Step] : []), 'estate', 'checks'];
}

/** Why a group is not asked about, for the line the page says once: the nearest reason, with its paragraph. */
export function skipped(c: Case): { step: 'siblings' | 'agnates'; why: 'son' | 'sonsSon' | 'father' | 'grandfather' | 'brother' | 'sister' | 'nearer'; cites: Cite[] }[] {
  const ask = asked(c);
  const d = below(c);
  const out: ReturnType<typeof skipped> = [];
  if (!SIBLINGS.some((h) => ask.has(h))) {
    const why = n(c, 'son') ? 'son' : d.male ? 'sonsSon' : 'father';
    out.push({ step: 'siblings', why, cites: [[358, 4], [358, 5], [358, 13]] });
  }
  if (!AGNATES.some((h) => ask.has(h))) {
    const why = n(c, 'son') ? 'son' : d.male ? 'sonsSon' : n(c, 'father') ? 'father' : n(c, 'grandfather') ? 'grandfather'
      : n(c, 'fullBrother') || n(c, 'patBrother') ? 'brother' : 'sister';
    out.push({ step: 'agnates', why, cites: why === 'sister' ? [352] : [[358, 7], 350] });
  }
  return out;
}

/** Whether brothers and sisters are asked about only for the mother's share: they inherit nothing beside the father. */
export const siblingsForMother = (c: Case) => n(c, 'father') > 0 && n(c, 'mother') > 0 && !below(c).any;
