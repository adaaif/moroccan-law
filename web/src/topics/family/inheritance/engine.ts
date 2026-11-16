/** The inheritance calculator's engine (F6 of the family plan; the inheritance review, 14 Nov 2026): book 6 of the
 *  family code, computed exactly.
 *
 *  Every share, exclusion and named case says its article and paragraph; nothing here guesses. The rules are chosen by
 *  the day of death: the code of 2004 (law 70.03) from its publication on 5 Feb 2004. An unborn heir, a missing person
 *  (arts 326–327), heirs of different faiths (art. 332) or a killer (art. 333) are outside the tool, and the form asks
 *  about them first (IR7). Where the code can be read two ways the engine follows one reading and carries the other's
 *  figure beside it; `web/src/topics/family/inheritance/choices.ts` writes each choice down with its source (IR11).
 *  Pure functions over exact fractions: the same answer in the browser and under `node --test`. */
import { ONE, ZERO, add, cmp, div, isZero, lcm, max, mul, q, sub, sum, type Q } from './frac.ts';

/** The code each death is counted by, the oldest first. A reform published later adds a line here with its own
 *  `from`; a bill is never a line here (IR30: it would be shown beside the law's answer, as a bill).
 *  `radd`: a rest with no residuary heir returns to the heirs of fixed shares (art. 349 §6), else to the Treasury.
 *  `daughters`: a dead daughter's children are owed the compulsory bequest too (art. 369). */
export type Rules = { code: '1958' | '70-03'; from: string; path: string; radd: boolean; daughters: boolean };
export const RULES: Rules[] = [
  // Book 6 of the code of personal status (dahir 1.58.112 of 3 April 1958), in force from its publication in Bulletin
  // 2371 of 4 April 1958 (IR27). The same shares and named cases, under its own numbers (arts 217–269); no return (its
  // art. 246 stops at the uncles, and art. 297 sends the rest to the Maliki rite: the Treasury); the bequest for a
  // son's children only (art. 266).
  { code: '1958', from: '1958-04-04', path: '/ma/dahir/1-58-112', radd: false, daughters: false },
  { code: '70-03', from: '2004-02-05', path: '/ma/loi/70-03', radd: true, daughters: true },
];
export const TODAY: Rules = RULES[RULES.length - 1];
export const rulesOn = (died: string): Rules | null =>
  [...RULES].reverse().find((r) => died >= r.from) ?? null;

export const HEIRS = [
  'husband', 'wife', 'son', 'daughter', 'sonsSon', 'sonsDaughter', 'father', 'mother', 'grandfather',
  'grandmotherM', 'grandmotherF', 'fullBrother', 'fullSister', 'patBrother', 'patSister', 'matBrother', 'matSister',
  'fullNephew', 'patNephew', 'fullUncle', 'patUncle', 'fullCousin', 'patCousin',
] as const;
export type Heir = (typeof HEIRS)[number];
/** Heirs there is at most one of. */
export const SINGLE: Heir[] = ['husband', 'father', 'mother', 'grandfather', 'grandmotherM', 'grandmotherF'];
const REMOTE: Heir[] = ['fullNephew', 'patNephew', 'fullUncle', 'patUncle', 'fullCousin', 'patCousin'];

export type Counts = Partial<Record<Heir, number>>;
/** A son or daughter who died before (or with) the deceased and left children: their children's compulsory bequest
 *  (arts 369–372); a son's children also inherit when no son survives. */
export type Branch = {
  sex: 'm' | 'f'; sons: number; daughters: number;
  /** Their own wife or husband is alive: an heir of theirs, so the grandchildren's part of their share is less (IR2). */
  spouse?: boolean;
  /** The deceased's surviving wife or husband is their mother or father: an heir of theirs too. */
  parent?: boolean;
};
/** A will (arts 277–314), as a part of the estate. `heir`: made to an heir, void unless the others agree (art. 280).
 *  `agreed`: the heirs of full capacity agreed to it after the death (art. 303), so the third does not hold it. */
export type Will = { share: Q; heir?: boolean; agreed?: boolean };
/** A «تنزيل» (arts 315–320): `count` people who are not heirs set in the place of a son or a daughter, each a place.
 *  `equal`: the words made them the equal of that heir, so the case is counted by rise (art. 317 §1); else they are
 *  counted among the heirs, given that heir's part, and the heirs share the rest as if there were none (art. 317 §2). */
export type Tanzil = { as: 'son' | 'daughter'; count: number; equal: boolean; agreed?: boolean };
/** `died` unset: the rules in force today. */
export type Input = { deceased: 'm' | 'f'; died?: string; counts: Counts; predeceased?: Branch[]; will?: Will; tanzil?: Tanzil };

/** An article of the code, or an article and its paragraph: 358 §4 is `[358, 4]`. */
export type Cite = number | [number, number];

/** A citation of the 2004 code in the numbers of the code that applies. The 1958 book runs 104 articles lower up to
 *  its art. 237 and 103 after it (its art. 238, on the word «الولد», has no heir in 2004); its art. 255 lists fourteen
 *  exclusions where art. 358 lists sixteen, and its art. 246 four ranks of agnates where art. 349 lists five. */
export function citeIn(rules: Rules, c: Cite): Cite {
  if (rules.code !== '1958') return c;
  const [a, p] = typeof c === 'number' ? [c, null] : c;
  const article = a <= 341 ? a - 104 : a - 103;
  if (p === null) return article;
  if (a === 358) return p <= 2 ? [article, 1] : p <= 5 ? [article, p - 1] : p === 6 ? article : [article, p - 2];
  if (a === 349) return [article, p <= 2 ? p : p - 1];
  return [article, p];
}

export type Basis = 'fard' | 'asaba' | 'fard+asaba';
export type Named = 'akdariyya' | 'malikiyya' | 'shibhMalikiyya' | 'mushtaraka' | 'gharrawayn' | 'muadda' | 'kharqa'
  | 'mubahala' | 'minbariyya';
/** `share` is the group's part of the estate left to the heirs, `each` one person's. `why` names the rule (its words
 *  are in the family module's strings), `arts` its articles. */
/** `fard` is the fixed share the code names before any rise («العول») or return («الرد»), and `own` the group's share of
 *  what is left to the heirs, before a bequest, a will or a «تنزيل» is taken out: both for the adoul's table. */
export type Line = { heir: Heir; count: number; share: Q; each: Q; own: Q; basis: Basis; why: string; cites: Cite[]; fard: Q | null };
export type Excluded = { heir: Heir; count: number; by: Heir | 'rule'; why: string; cites: Cite[] };
/** A dead child's children: `parent` is what the dead child would have taken, `part` their children's part of it, and
 *  `share` the bequest that follows (after the cap of a third). `whole` is the bequest by the other reading of art. 370:
 *  the dead child's whole share. */
export type BequestLine = {
  /** The dead child's place among `Input.predeceased`, as given. */
  index: number;
  sex: 'm' | 'f'; sons: number; daughters: number; share: Q; son: Q; daughter: Q; parent: Q; part: Q; whole: Q;
};
export type Result =
  | { ok: false; reason: 'before' }
  /** The mixed forms of arts 362 and 363, which the engine does not decide (IR3). */
  | { ok: false; reason: 'mixed'; cites: Cite[] }
  | {
    ok: true; rules: Rules; lines: Line[]; excluded: Excluded[]; base: bigint; awl: bigint | null; radd: boolean;
    treasury: Q; tashih: bigint; named: Named | null; bequest: BequestLine[]; bequestTotal: Q; capped: boolean;
    /** What is left to the heirs once the bequest, a will and a «تنزيل» are out: every line's share is its own share
     *  times this. `ownTashih`: the heirs' own case comes right from this number, whatever was taken out first. */
    left: Q; ownTashih: bigint; ownTreasury: Q;
    /** A will: what was asked, what the third (after the compulsory bequest, which comes first) lets through, and why
     *  it was cut: `third`, or `heir` (art. 280: void for an heir unless the others agree). */
    will: { asked: Q; granted: Q; cut: 'third' | 'heir' | null } | null;
    /** A «تنزيل»: each person's part, all of them together, and the paragraph of art. 317 it was counted by. */
    tanzil: { each: Q; total: Q; asked: Q; cut: boolean; by: 'rise' | 'among' } | null;
    /** The bequest's total by the other reading of art. 370, when it differs (call C1: both are shown). */
    otherBequest: Q | null;
    /** The rest returned to a husband or wife too (art. 349 §6 as written): their group's share without the return,
     *  for the line that names the other reading (call C2). */
    raddSpouse: { heir: 'husband' | 'wife'; fixed: Q } | null;
  };

/** `named`: the fixed share the code names, where `fard` already holds what the heir ends with (the Akdariyya). */
type Part = { heir: Heir; count: number; fard?: Q; weight?: number; basis: Basis; why: string; cites: Cite[]; got?: Q; named?: Q };
export type Dist = {
  lines: Line[]; excluded: Excluded[]; base: bigint; awl: bigint | null; radd: boolean; treasury: Q; named: Named | null;
  raddSpouse: { heir: 'husband' | 'wife'; fixed: Q } | null; stop?: 'mixed';
};

const SIXTH = q(1, 6), THIRD = q(1, 3), HALF = q(1, 2), QUARTER = q(1, 4), EIGHTH = q(1, 8), TWO_THIRDS = q(2, 3);

function clean(counts: Counts, deceased: 'm' | 'f'): Record<Heir, number> {
  const c = Object.fromEntries(HEIRS.map((h) => [h, Math.max(0, Math.floor(Number(counts[h] ?? 0)) || 0)])) as Record<Heir, number>;
  for (const h of SINGLE) c[h] = Math.min(c[h], 1);
  c.wife = Math.min(c.wife, 4);
  if (deceased === 'm') c.husband = 0;
  else c.wife = 0;
  return c;
}

/** Art. 358's paragraph for each far heir by blood. */
const REMOTE_PAR: Partial<Record<Heir, number>> = { fullNephew: 7, patNephew: 8, fullUncle: 9, patUncle: 10, fullCousin: 11, patCousin: 12 };

/** The heirs' shares of what is left to them (after debts, the will and any compulsory bequest). */
export function distribute(counts: Counts, deceased: 'm' | 'f', rules: Rules = TODAY): Dist {
  const c = clean(counts, deceased);
  const parts: Part[] = [];
  const excluded: Excluded[] = [];
  const drop = (h: Heir, by: Heir | 'rule', why: string, cites: Cite[]) => {
    if (c[h] > 0) {
      excluded.push({ heir: h, count: c[h], by, why, cites });
      c[h] = 0;
    }
  };
  const fard = (h: Heir, f: Q, why: string, cites: Cite[]) =>
    c[h] > 0 && parts.push({ heir: h, count: c[h], fard: f, basis: 'fard', why, cites });
  const asaba = (h: Heir, weight: number, why: string, cites: Cite[]) =>
    c[h] > 0 && parts.push({ heir: h, count: c[h], weight, basis: 'asaba', why, cites });

  // What the shares depend on, read before anyone is excluded: excluded siblings still reduce the mother (art. 346).
  const desc = c.son + c.daughter + c.sonsSon + c.sonsDaughter > 0;
  const siblings = c.fullBrother + c.fullSister + c.patBrother + c.patSister + c.matBrother + c.matSister;
  const mat = c.matBrother + c.matSister;
  const grandmothers = c.grandmotherM + c.grandmotherF;
  const motherLike = c.mother > 0 || grandmothers > 0;
  const spouse = c.husband ? (desc ? QUARTER : HALF) : c.wife ? (desc ? EIGHTH : QUARTER) : ZERO;
  const spouseLine = () => {
    if (c.husband) fard('husband', spouse, desc ? 'husband.quarter' : 'husband.half', [desc ? [343, 1] : [342, 1]]);
    if (c.wife) fard('wife', spouse, desc ? 'wife.eighth' : 'wife.quarter', [desc ? 344 : [343, 2]]);
  };
  /** The mother's sixth, or the grandmothers' in her place. `why` says where her sixth comes from: a descendant, or
   *  two siblings (the named cases of arts 362, 363 and 365 have no descendant: IR3). */
  const motherLine = (share: Q, why: 'mother.sixth' | 'mother.sixthSiblings' = 'mother.sixth') => {
    if (c.mother) return fard('mother', share, why, why === 'mother.sixth' ? [[347, 2]] : [[347, 2], [359, 1]]);
    if (c.grandmotherM && c.grandmotherF) {
      fard('grandmotherM', mul(share, HALF), 'grandmother.shared', [[347, 6]]);
      fard('grandmotherF', mul(share, HALF), 'grandmother.shared', [[347, 6]]);
    } else {
      fard('grandmotherM', share, 'grandmother.sixth', [[347, 6]]);
      fard('grandmotherF', share, 'grandmother.sixth', [[347, 6]]);
    }
  };
  const dropRemote = (by: Heir) => REMOTE.forEach((h) => drop(h, by, 'remote.below', [[358, REMOTE_PAR[h] as number]]));
  if (c.mother) {
    drop('grandmotherM', 'mother', 'grandmother.byMother', [[358, 14]]);
    drop('grandmotherF', 'mother', 'grandmother.byMother', [[358, 15]]);
  }

  // The cases the code names (arts 361–363, 365), as it writes them.
  const onlyHusbandSide = c.husband && motherLike && !c.father && !desc;
  if (c.husband && c.mother && c.grandfather && !c.father && !desc && siblings === 1 && c.fullSister + c.patSister === 1) {
    const sister: Heir = c.fullSister ? 'fullSister' : 'patSister';
    // What each ends with, and the fixed share it starts from: a half, a third, a half and a sixth make nine of six;
    // the grandfather then joins his sixth to the sister's half and they share it two for one.
    parts.push({ heir: 'husband', count: 1, fard: q(9, 27), named: HALF, basis: 'fard', why: 'akdariyya', cites: [361] });
    parts.push({ heir: 'mother', count: 1, fard: q(6, 27), named: THIRD, basis: 'fard', why: 'akdariyya', cites: [361] });
    parts.push({ heir: sister, count: 1, fard: q(4, 27), named: HALF, basis: 'fard', why: 'akdariyya', cites: [361] });
    parts.push({ heir: 'grandfather', count: 1, fard: q(8, 27), named: SIXTH, basis: 'fard', why: 'akdariyya', cites: [361] });
    dropRemote('grandfather');
    return finish(parts, excluded, 'akdariyya', rules, { base: 6n, awl: 9n });
  }
  const withGrandfather = onlyHusbandSide && c.grandfather && mat >= 2;
  const malikiyya = withGrandfather && c.fullBrother + c.fullSister === 0 && c.patBrother >= 1 && c.patSister === 0;
  const shibh = withGrandfather && c.fullBrother >= 1 && c.fullSister + c.patBrother + c.patSister === 0;
  // Brothers beside sisters, or full beside paternal ones, in the conditions of arts 362 and 363: the articles name
  // brothers alone, and their reason («لأن الجد يحجبهم») would shut these out too. Not decided here: an adoul rules (IR3).
  if (withGrandfather && c.fullBrother + c.patBrother >= 1 && !malikiyya && !shibh)
    return { lines: [], excluded: [], base: 1n, awl: null, radd: false, treasury: ZERO, named: null, raddSpouse: null, stop: 'mixed' };
  if (malikiyya) {
    spouseLine();
    motherLine(SIXTH, 'mother.sixthSiblings');
    parts.push({ heir: 'grandfather', count: 1, fard: THIRD, basis: 'asaba', why: 'grandfather.malikiyya', cites: [362] });
    drop('patBrother', 'grandfather', 'malikiyya', [362]);
    drop('matBrother', 'grandfather', 'mat.byGrandfather', [[358, 13], 362]);
    drop('matSister', 'grandfather', 'mat.byGrandfather', [[358, 13], 362]);
    dropRemote('grandfather');
    return finish(parts, excluded, 'malikiyya', rules);
  }
  if (shibh) {
    spouseLine();
    motherLine(SIXTH, 'mother.sixthSiblings');
    parts.push({ heir: 'grandfather', count: 1, fard: THIRD, basis: 'asaba', why: 'grandfather.malikiyya', cites: [363] });
    drop('fullBrother', 'grandfather', 'shibhMalikiyya', [363]);
    drop('matBrother', 'grandfather', 'mat.byGrandfather', [[358, 13], 363]);
    drop('matSister', 'grandfather', 'mat.byGrandfather', [[358, 13], 363]);
    dropRemote('grandfather');
    return finish(parts, excluded, 'shibhMalikiyya', rules);
  }
  if (onlyHusbandSide && !c.grandfather && mat >= 2 && c.fullBrother >= 1) {
    spouseLine();
    motherLine(SIXTH, 'mother.sixthSiblings');
    // The third shared by head, brothers and sisters alike, «لأن جميعهم من أم واحدة».
    const heads = mat + c.fullBrother + c.fullSister;
    for (const h of ['matBrother', 'matSister', 'fullBrother', 'fullSister'] as Heir[])
      fard(h, q(c[h], heads * 3), 'mushtaraka', [365]);
    drop('patBrother', 'fullBrother', 'pat.byFull', [[358, 5]]);
    drop('patSister', 'fullBrother', 'pat.byFull', [[358, 5]]);
    dropRemote('fullBrother');
    return finish(parts, excluded, 'mushtaraka', rules);
  }

  // Exclusion (art. 358).
  if (c.son) {
    drop('sonsSon', 'son', 'grandchild.bySon', [[358, 1]]);
    drop('sonsDaughter', 'son', 'grandchild.bySon', [[358, 2]]);
  }
  if (c.daughter >= 2 && !c.sonsSon) drop('sonsDaughter', 'daughter', 'sonsDaughter.byDaughters', [[358, 2]]);
  if (c.father) {
    drop('grandfather', 'father', 'grandfather.byFather', [[358, 3]]);
    drop('grandmotherF', 'father', 'grandmotherF.byFather', [[358, 15]]);
  }
  const maleDesc = c.son + c.sonsSon > 0;
  const femaleDesc = c.daughter + c.sonsDaughter > 0;
  const fullBy: Heir | null = c.son ? 'son' : c.sonsSon ? 'sonsSon' : c.father ? 'father' : null;
  if (fullBy) {
    drop('fullBrother', fullBy, 'full.excluded', [[358, 4]]);
    drop('fullSister', fullBy, 'full.excluded', [[358, 4]]);
    drop('patBrother', fullBy, 'pat.excluded', [[358, 5]]);
    drop('patSister', fullBy, 'pat.excluded', [[358, 5]]);
  }
  const matBy: Heir | null = c.son ? 'son' : c.daughter ? 'daughter' : c.sonsSon ? 'sonsSon'
    : c.sonsDaughter ? 'sonsDaughter' : c.father ? 'father' : c.grandfather ? 'grandfather' : null;
  if (matBy) {
    drop('matBrother', matBy, 'mat.excluded', [[358, 13]]);
    drop('matSister', matBy, 'mat.excluded', [[358, 13]]);
  }

  // Spouse, children, parents (arts 342–347, 351, 353).
  spouseLine();
  if (c.son) {
    asaba('son', 2, 'son.rest', [[349, 1]]);
    asaba('daughter', 1, 'daughter.withSon', [[351, 1]]);
  } else {
    fard('daughter', c.daughter === 1 ? HALF : TWO_THIRDS, c.daughter === 1 ? 'daughter.half' : 'daughter.twoThirds',
      [c.daughter === 1 ? [342, 2] : [345, 1]]);
    if (c.sonsSon) {
      asaba('sonsSon', 2, 'sonsSon.rest', [[349, 1]]);
      asaba('sonsDaughter', 1, 'sonsDaughter.withBrother', [[351, 2]]);
    } else if (c.daughter === 1) fard('sonsDaughter', SIXTH, 'sonsDaughter.sixth', [[347, 3]]);
    else fard('sonsDaughter', c.sonsDaughter === 1 ? HALF : TWO_THIRDS,
      c.sonsDaughter === 1 ? 'sonsDaughter.half' : 'sonsDaughter.twoThirds', [c.sonsDaughter === 1 ? [342, 3] : [345, 2]]);
  }
  let named: Named | null = null;
  if (c.father) {
    if (maleDesc) fard('father', SIXTH, 'father.sixth', [[347, 1]]);
    else if (femaleDesc) parts.push({ heir: 'father', count: 1, fard: SIXTH, weight: 1, basis: 'fard+asaba', why: 'father.sixthAndRest', cites: [353] });
    else asaba('father', 1, 'father.rest', [[349, 2]]);
  }
  if (c.mother) {
    if ((c.husband || c.wife) && c.father && !desc && siblings < 2) {
      fard('mother', mul(THIRD, sub(ONE, spouse)), 'mother.thirdOfRest', [366]);
      named = 'gharrawayn';
    } else if (desc) fard('mother', SIXTH, 'mother.sixth', [[347, 2]]);
    else if (siblings >= 2) fard('mother', SIXTH, 'mother.sixthSiblings', [[347, 2], [359, 1]]);
    else fard('mother', THIRD, 'mother.third', [[346, 1]]);
  } else if (grandmothers) motherLine(SIXTH);

  // Siblings through the mother (arts 346, 347).
  const m = c.matBrother + c.matSister;
  if (m === 1) {
    fard('matBrother', SIXTH, 'mat.sixth', [[347, 5]]);
    fard('matSister', SIXTH, 'mat.sixth', [[347, 5]]);
  } else if (m > 1) {
    fard('matBrother', q(c.matBrother, m * 3), 'mat.third', [[346, 2]]);
    fard('matSister', q(c.matSister, m * 3), 'mat.third', [[346, 2]]);
  }

  const sibs = c.fullBrother + c.fullSister + c.patBrother + c.patSister;
  const gfMode = c.grandfather > 0 && !maleDesc && sibs > 0;
  if (c.grandfather && !gfMode) {
    if (maleDesc) fard('grandfather', SIXTH, 'grandfather.sixth', [[347, 7]]);
    else if (femaleDesc) parts.push({ heir: 'grandfather', count: 1, fard: SIXTH, weight: 1, basis: 'fard+asaba', why: 'grandfather.sixthAndRest', cites: [353] });
    else asaba('grandfather', 1, 'grandfather.rest', [[349, 3]]);
  }

  if (gfMode) {
    // The grandfather with brothers and sisters (art. 354): the better of a third of all and sharing as a brother, or,
    // with heirs of fixed shares, the best of a sixth of all, a third of the rest and sharing the rest; the full
    // siblings count the paternal ones against him (art. 360). Sisters have no fixed share with him (art. 361).
    const fixed = sum(parts.filter((p) => p.fard).map((p) => p.fard as Q));
    const rest = sub(ONE, fixed);
    const full = c.fullBrother + c.fullSister, pat = c.patBrother + c.patSister;
    // Art. 354's paragraph: 3 with heirs of fixed shares, else 2 when full and paternal siblings stand together, else 1.
    const par = isZero(fixed) ? (full && pat ? 2 : 1) : 3;
    if (cmp(rest, SIXTH) <= 0) {
      parts.push({ heir: 'grandfather', count: 1, fard: SIXTH, basis: 'fard', why: 'grandfather.sixthOnly', cites: [[354, 3]] });
      for (const h of ['fullBrother', 'fullSister', 'patBrother', 'patSister'] as Heir[]) drop(h, 'rule', 'siblings.nothingLeft', [[354, 3]]);
    } else {
      const heads = 2 + 2 * (c.fullBrother + c.patBrother) + c.fullSister + c.patSister;
      const share = mul(rest, q(2, heads));
      const options: [Q, string][] = isZero(fixed)
        ? [[THIRD, 'grandfather.third'], [share, 'grandfather.shares']]
        : [[SIXTH, 'grandfather.sixthAll'], [mul(rest, THIRD), 'grandfather.thirdOfRest'], [share, 'grandfather.shares']];
      const best = max(...options.map((o) => o[0]));
      const why = options.find((o) => cmp(o[0], best) === 0)?.[1] ?? 'grandfather.shares';
      // Sharing as a brother is no fixed share: the table says so.
      parts.push({ heir: 'grandfather', count: 1, fard: best, basis: why === 'grandfather.shares' ? 'asaba' : 'fard', why, cites: [[354, par]] });
      let left = sub(rest, best);
      const split = (hs: Heir[], amount: Q, why: string, cites: Cite[]) => {
        const w = hs.reduce((s, h) => s + c[h] * (h.endsWith('Brother') ? 2 : 1), 0);
        for (const h of hs) if (c[h]) parts.push({ heir: h, count: c[h], fard: mul(amount, q(c[h] * (h.endsWith('Brother') ? 2 : 1), w)), basis: 'asaba', why, cites });
      };
      if (full && pat) {
        named = 'muadda';
        if (c.fullBrother || c.fullSister >= 2) {
          split(['fullBrother', 'fullSister'], left, 'siblings.muadda', [[354, par], 360]);
          drop('patBrother', 'rule', 'pat.muadda', [360]);
          drop('patSister', 'rule', 'pat.muadda', [360]);
        } else {
          const hers = cmp(left, HALF) > 0 ? HALF : left;
          split(['fullSister'], hers, 'fullSister.muadda', [360]);
          left = sub(left, hers);
          if (isZero(left)) {
            drop('patBrother', 'rule', 'pat.muadda', [360]);
            drop('patSister', 'rule', 'pat.muadda', [360]);
          } else split(['patBrother', 'patSister'], left, 'pat.muaddaRest', [360]);
        }
      } else split(full ? ['fullBrother', 'fullSister'] : ['patBrother', 'patSister'], left, 'siblings.withGrandfather', [[354, par]]);
      if (c.mother && full + pat === 1 && c.fullSister + c.patSister === 1 && parts.length === 3) named = 'kharqa';
    }
    dropRemote('grandfather');
  } else {
    // Brothers and sisters (arts 342, 345, 347, 351, 352, 358).
    if (c.fullBrother) {
      asaba('fullBrother', 2, 'fullBrother.rest', [[349, 3]]);
      asaba('fullSister', 1, 'fullSister.withBrother', [[351, 3]]);
    } else if (c.fullSister) {
      if (femaleDesc) asaba('fullSister', 1, 'fullSister.withDaughters', [352]);
      else fard('fullSister', c.fullSister === 1 ? HALF : TWO_THIRDS, c.fullSister === 1 ? 'fullSister.half' : 'fullSister.twoThirds',
        [c.fullSister === 1 ? [342, 4] : [345, 3]]);
    }
    if (c.fullBrother) {
      drop('patBrother', 'fullBrother', 'pat.byFull', [[358, 5]]);
      drop('patSister', 'fullBrother', 'pat.byFull', [[358, 5]]);
    } else if (c.fullSister && femaleDesc) {
      drop('patBrother', 'fullSister', 'pat.bySisterWithDaughters', [352, [358, 5]]);
      drop('patSister', 'fullSister', 'pat.bySisterWithDaughters', [352, [358, 5]]);
    } else if (c.patBrother) {
      asaba('patBrother', 2, 'patBrother.rest', [[349, 3]]);
      asaba('patSister', 1, 'patSister.withBrother', [[351, 3]]);
    } else if (c.patSister) {
      if (femaleDesc) asaba('patSister', 1, 'patSister.withDaughters', [352]);
      else if (c.fullSister === 1) fard('patSister', SIXTH, 'patSister.sixth', [[347, 4]]);
      else if (c.fullSister >= 2) drop('patSister', 'fullSister', 'patSister.byTwoFull', [[358, 6]]);
      else fard('patSister', c.patSister === 1 ? HALF : TWO_THIRDS, c.patSister === 1 ? 'patSister.half' : 'patSister.twoThirds',
        [c.patSister === 1 ? [342, 5] : [345, 4]]);
    }
    // The far heirs by blood, the nearest first (arts 349, 350, 358).
    const above = parts.find((p) => p.weight);
    if (above) dropRemote(above.heir);
    else {
      const first = REMOTE.find((h) => c[h] > 0);
      if (first) {
        asaba(first, 1, `${first}.rest`, [[349, first.endsWith('Nephew') ? 4 : 5], 350]);
        REMOTE.slice(REMOTE.indexOf(first) + 1).forEach((h) => drop(h, first, 'remote.below', [[358, REMOTE_PAR[h] as number]]));
      }
    }
  }

  if (!named) {
    const who = new Set(parts.map((p) => p.heir));
    const only = (...hs: Heir[]) => who.size === hs.length && hs.every((h) => who.has(h));
    if (only('husband', 'mother', 'fullSister') && c.fullSister === 1 || only('husband', 'mother', 'patSister') && c.patSister === 1) named = 'mubahala';
    if (only('wife', 'daughter', 'father', 'mother') && c.daughter >= 2) named = 'minbariyya';
  }
  return finish(parts, excluded, named, rules);
}

/** Shares into lines: the fixed shares first; too many, and the base rises («العول»); a rest, to the residuaries by
 *  weight; a rest and none, back to the fixed shares by their proportion (art. 349 §6, «الرد»); no heir, the Treasury. */
function finish(parts: Part[], excluded: Excluded[], named: Named | null, rules: Rules, fixedBase?: { base: bigint; awl: bigint }): Dist {
  const fixed = parts.filter((p) => p.fard);
  const total = sum(fixed.map((p) => p.fard as Q));
  const base = fixedBase?.base ?? fixed.reduce((b, p) => lcm(b, (p.fard as Q).d), 1n);
  let awl: bigint | null = fixedBase?.awl ?? null;
  let radd = false;
  let treasury = ZERO;
  for (const p of fixed) p.got = p.fard;
  const residuaries = parts.filter((p) => p.weight);
  if (cmp(total, ONE) > 0) {
    awl = awl ?? total.n * (base / total.d);
    for (const p of fixed) p.got = div(p.fard as Q, total);
  } else {
    const rest = sub(ONE, total);
    if (!isZero(rest)) {
      if (residuaries.length) {
        const w = residuaries.reduce((s, p) => s + (p.weight as number) * p.count, 0);
        for (const p of residuaries) p.got = add(p.got ?? ZERO, mul(rest, q((p.weight as number) * p.count, w)));
      } else if (fixed.length && rules.radd) {
        radd = true;
        for (const p of fixed) p.got = add(p.got as Q, mul(rest, div(p.fard as Q, total)));
      } else treasury = rest;
    }
  }
  const lines: Line[] = parts.filter((p) => p.got && !isZero(p.got)).map((p) => ({
    heir: p.heir, count: p.count, share: p.got as Q, each: div(p.got as Q, q(p.count)), own: p.got as Q, basis: p.basis, why: p.why, cites: p.cites,
    fard: p.basis === 'asaba' ? null : (p.named ?? (p.fard as Q)),
  }));
  // Residuaries the fixed shares left nothing to.
  for (const p of parts) if (!p.got || isZero(p.got)) excluded.push({ heir: p.heir, count: p.count, by: 'rule', why: 'nothingLeft', cites: [336] });
  // Residuaries alone: the base is their heads, a male counting twice where females share with him.
  const unit = residuaries.every((p) => p.weight === 2) ? 2 : 1;
  const asl = residuaries.length && !fixed.length ? BigInt(residuaries.reduce((s, p) => s + (p.weight as number) * p.count, 0) / unit) : base;
  // The return reached a husband or wife: their share without it, for the line that names the other reading (C2).
  const mate = radd ? fixed.find((p) => p.heir === 'husband' || p.heir === 'wife') : undefined;
  const raddSpouse = mate ? { heir: mate.heir as 'husband' | 'wife', fixed: mate.fard as Q } : null;
  return { lines, excluded, base: asl, awl, radd, treasury, named, raddSpouse };
}

/** A dead child's own heirs who take before their children do, as the family gives them: their wife or husband; their
 *  surviving parent (the deceased's wife or husband); through a father who is the deceased, his father (or, his father
 *  gone, his grandfather) and his mother; through a mother who is the deceased, her mother. Their brothers, uncles and
 *  cousins are left out: they could only take what the children leave, and that returns to the estate anyway. */
function heirsOf(b: Branch, deceased: 'm' | 'f', living: Record<Heir, number>): Counts {
  const c: Counts = { son: b.sons, daughter: b.daughters };
  if (b.spouse === true) c[b.sex === 'm' ? 'wife' : 'husband'] = 1;
  if (deceased === 'm') {
    if (b.parent === true && living.wife) c.mother = 1;
    c.grandfather = living.father || living.grandfather;
    c.grandmotherF = living.mother;
  } else {
    if (b.parent === true && living.husband) c.father = 1;
    c.grandmotherM = living.mother;
  }
  return c;
}

/** The whole computation: the compulsory bequest first (arts 369–372, at most a third), then the heirs on the rest.
 *
 *  The bequest follows the reading of the Court of Cassation (decision 805 of 28 May 1985; the Minister of Justice's
 *  letter 20396 of 25 January 1980; the ministry's practical guide): a dead child is supposed alive and takes a share;
 *  that share is divided as the dead child's own estate, and their children's part of it is the bequest. The other
 *  reading of art. 370's «بمقدار حصتهم مما يرثه أبوهم أو أمهم», the dead child's whole share, is carried beside it
 *  (`whole`, `otherBequest`): call C1 of the review shows both. */
export function compute(input: Input): Result {
  const rules = input.died ? rulesOn(input.died) : TODAY;
  if (!rules) return { ok: false, reason: 'before' };
  const given = input.predeceased ?? [];
  const branches = given.filter((b) => b.sons + b.daughters > 0);
  // A predeceased son's children stand among the heirs as a son's sons and daughters.
  const counts: Counts = { ...input.counts };
  counts.sonsSon = (counts.sonsSon ?? 0) + branches.filter((b) => b.sex === 'm').reduce((s, b) => s + b.sons, 0);
  counts.sonsDaughter = (counts.sonsDaughter ?? 0) + branches.filter((b) => b.sex === 'm').reduce((s, b) => s + b.daughters, 0);
  const heirs = distribute(counts, input.deceased, rules);
  if (heirs.stop) return { ok: false, reason: 'mixed', cites: [citeIn(rules, 362), citeIn(rules, 363)] };
  const inherit = new Set(heirs.lines.map((l) => l.heir));

  // Grandchildren who inherit from the grandparent take no bequest (art. 371). The others' parents are supposed to
  // have died just after the deceased, all together (art. 370).
  const due = branches.filter((b) => (b.sex === 'f' ? rules.daughters : !(inherit.has('sonsSon') || inherit.has('sonsDaughter'))));
  const alive: Counts = {
    ...counts,
    son: (counts.son ?? 0) + due.filter((b) => b.sex === 'm').length,
    daughter: (counts.daughter ?? 0) + due.filter((b) => b.sex === 'f').length,
  };
  const supposed = due.length ? distribute(alive, input.deceased, rules) : null;
  const living = clean(input.counts, input.deceased);
  const owed = due.flatMap((b) => {
    const line = supposed?.lines.find((l) => l.heir === (b.sex === 'm' ? 'son' : 'daughter'));
    if (!line) return [];
    // The dead child's share as their own estate: what their children take of it. Nothing returns to them here:
    // «وما بقي يضاف كله إلى ورثة الأصل», an only daughter takes her half and no more (decision 805).
    const own = distribute(heirsOf(b, input.deceased, living), b.sex, { ...rules, radd: false });
    const kid = (h: Heir) => own.lines.find((l) => l.heir === h);
    const part = sum([kid('son')?.share ?? ZERO, kid('daughter')?.share ?? ZERO]);
    return [{ b, parent: line.each, part, son: kid('son')?.each ?? ZERO, daughter: kid('daughter')?.each ?? ZERO }];
  });
  const wanted = sum(owed.map((o) => mul(o.parent, o.part)));
  const capped = cmp(wanted, THIRD) > 0;
  const factor = capped ? div(THIRD, wanted) : ONE;
  // The other reading: the whole share, capped the same way.
  const wantedWhole = sum(owed.map((o) => o.parent));
  const factorWhole = cmp(wantedWhole, THIRD) > 0 ? div(THIRD, wantedWhole) : ONE;
  const bequest: BequestLine[] = owed.map(({ b, parent, part, son, daughter }) => ({
    index: given.indexOf(b), sex: b.sex, sons: b.sons, daughters: b.daughters, parent, part,
    share: mul(mul(parent, part), factor), son: mul(mul(parent, son), factor), daughter: mul(mul(parent, daughter), factor),
    whole: mul(parent, factorWhole),
  }));
  const bequestTotal = sum(bequest.map((x) => x.share));
  const whole = sum(bequest.map((x) => x.whole));

  // A «تنزيل» (arts 315–320): what each person set in an heir's place would take.
  let placed: { each: Q; asked: Q; by: 'rise' | 'among' } | null = null;
  const tz = input.tanzil && input.tanzil.count > 0 ? input.tanzil : null;
  if (tz) {
    const n = Math.min(20, Math.floor(tz.count));
    const peer = heirs.lines.find((l) => l.heir === tz.as);
    if (tz.equal && peer) {
      // By rise (art. 317 §1): each takes the shares of the heir they are made equal to, and the base rises by them.
      const add1 = mul(peer.each, q(n));
      placed = { each: div(peer.each, add(ONE, add1)), asked: div(add1, add(ONE, add1)), by: 'rise' };
    } else {
      // Counted among the heirs (arts 317 §2, 318): given what that heir takes in a case that holds them too; the
      // heirs then share the rest as if there were none.
      const among = distribute({ ...counts, [tz.as]: (counts[tz.as] ?? 0) + n }, input.deceased, rules);
      const each = among.lines.find((l) => l.heir === tz.as)?.each ?? ZERO;
      placed = { each, asked: mul(each, q(n)), by: 'among' };
    }
  }
  // The third (art. 277): the compulsory bequest first, as the Court of Cassation rules (decisions 1175 of
  // 27 Dec 2001 and 155 of 14 Mar 2007); a will and a «تنزيل» share what is left of it in proportion (art. 302),
  // unless the heirs agreed to more (art. 303). A will to an heir stands only if the others agree (art. 280).
  const room = sub(THIRD, bequestTotal);
  const willAsked = input.will && !isZero(input.will.share) ? input.will.share : null;
  const willVoid = Boolean(willAsked && input.will?.heir && !input.will?.agreed);
  const bound = [
    willAsked && !willVoid && !input.will?.agreed ? willAsked : ZERO,
    placed && !tz?.agreed ? placed.asked : ZERO,
  ];
  const boundSum = sum(bound);
  const squeeze = cmp(boundSum, room) > 0 ? div(room, boundSum) : ONE;
  const willGranted = !willAsked || willVoid ? ZERO : input.will?.agreed ? willAsked : mul(willAsked, squeeze);
  const tanzilTotal = !placed ? ZERO : tz?.agreed ? placed.asked : mul(placed.asked, squeeze);
  const tanzilEach = placed && !isZero(placed.asked) ? mul(placed.each, div(tanzilTotal, placed.asked)) : ZERO;

  const left = sub(sub(sub(ONE, bequestTotal), willGranted), tanzilTotal);
  const cite = (cs: Cite[]) => cs.map((c) => citeIn(rules, c));
  const lines = heirs.lines.map((l) => ({ ...l, share: mul(l.share, left), each: mul(l.each, left), cites: cite(l.cites) }));
  const treasury = mul(heirs.treasury, left);
  const ownTashih = [...heirs.lines.map((l) => l.each.d), heirs.treasury.d].reduce((a, b) => lcm(a, b), 1n);
  const dens = [...lines.map((l) => l.each.d), ...bequest.flatMap((x) => [x.sons ? x.son.d : 1n, x.daughters ? x.daughter.d : 1n]),
    treasury.d, tanzilEach.d];
  const tashih = dens.reduce((a, b) => lcm(a, b), 1n);
  return {
    ok: true, rules, lines, excluded: heirs.excluded.map((e) => ({ ...e, cites: cite(e.cites) })), base: heirs.base, awl: heirs.awl, radd: heirs.radd, named: heirs.named,
    treasury, tashih, bequest, bequestTotal, capped, left, ownTashih, ownTreasury: heirs.treasury,
    otherBequest: cmp(whole, bequestTotal) === 0 ? null : whole,
    raddSpouse: heirs.raddSpouse ? { heir: heirs.raddSpouse.heir, fixed: mul(heirs.raddSpouse.fixed, left) } : null,
    will: willAsked ? { asked: willAsked, granted: willGranted, cut: willVoid ? 'heir' : cmp(willGranted, willAsked) < 0 ? 'third' : null } : null,
    tanzil: placed ? { each: tanzilEach, total: tanzilTotal, asked: placed.asked, cut: cmp(tanzilTotal, placed.asked) < 0, by: placed.by } : null,
  };
}

/** One person's share as «n من D». */
export const outOf = (x: Q, d: bigint): bigint => (x.n * d) / x.d;

/** A citation's article, and its words for a chip: «المادة 358، البند 4». */
export const article = (c: Cite): number => (typeof c === 'number' ? c : c[0]);
export const paragraph = (c: Cite): number | null => (typeof c === 'number' ? null : c[1]);
