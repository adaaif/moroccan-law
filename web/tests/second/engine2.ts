// A second, independent reckoning of inheritance shares under the Moroccan Family Code (law 70.03, book 6,
// arts 321–395; the Maliki rite where the text is silent, art. 400), with the compulsory bequest of arts 369–372.
// Written from the code's text alone, to be run against the site's engine.

export type Heir = 'husband' | 'wife' | 'son' | 'daughter' | 'sonsSon' | 'sonsDaughter' | 'father' | 'mother' | 'grandfather'
  | 'grandmotherM' /* mother's mother */ | 'grandmotherF' /* father's mother */
  | 'fullBrother' | 'fullSister' | 'patBrother' | 'patSister' | 'matBrother' | 'matSister'
  | 'fullNephew' /* son of a full brother */ | 'patNephew' | 'fullUncle' /* father's full brother */ | 'patUncle' | 'fullCousin' /* son of a full uncle */ | 'patCousin';
/** A son or daughter of the deceased who died before (or with) the deceased and left children. `spouse`: their own wife or
 *  husband is alive. `parent`: the deceased's surviving wife or husband is this dead child's mother or father. */
export type Branch = { sex: 'm' | 'f'; sons: number; daughters: number; spouse?: boolean; parent?: boolean };
export type Input = { deceased: 'm' | 'f'; counts: Partial<Record<Heir, number>>; predeceased?: Branch[] };
export type Output =
  | { stop: 'mixed' }
  | { each: Partial<Record<Heir, string>>;
      bequest: { son: string; daughter: string }[];
      treasury: string };

// ---------------------------------------------------------------------------------------------------------------
// Exact fractions over BigInt.

type Q = { n: bigint; d: bigint };

function gcd(a: bigint, b: bigint): bigint {
  if (a < 0n) a = -a;
  if (b < 0n) b = -b;
  while (b !== 0n) { const t = a % b; a = b; b = t; }
  return a;
}
function q(n: bigint | number, d: bigint | number = 1n): Q {
  let N = BigInt(n), D = BigInt(d);
  if (D === 0n) throw new Error('zero denominator');
  if (D < 0n) { N = -N; D = -D; }
  const g = gcd(N, D) || 1n;
  return { n: N / g, d: D / g };
}
const ZERO = q(0);
const ONE = q(1);
const add = (a: Q, b: Q): Q => q(a.n * b.d + b.n * a.d, a.d * b.d);
const sub = (a: Q, b: Q): Q => q(a.n * b.d - b.n * a.d, a.d * b.d);
const mul = (a: Q, b: Q): Q => q(a.n * b.n, a.d * b.d);
const div = (a: Q, b: Q): Q => q(a.n * b.d, a.d * b.n);
const cmp = (a: Q, b: Q): number => { const x = a.n * b.d - b.n * a.d; return x < 0n ? -1 : x > 0n ? 1 : 0; };
const isZero = (a: Q): boolean => a.n === 0n;
const str = (a: Q): string => `${a.n}/${a.d}`;
const max = (...xs: Q[]): Q => xs.reduce((m, x) => (cmp(x, m) > 0 ? x : m));
const min = (a: Q, b: Q): Q => (cmp(a, b) <= 0 ? a : b);

// ---------------------------------------------------------------------------------------------------------------

const HEIRS: Heir[] = ['husband', 'wife', 'son', 'daughter', 'sonsSon', 'sonsDaughter', 'father', 'mother', 'grandfather',
  'grandmotherM', 'grandmotherF', 'fullBrother', 'fullSister', 'patBrother', 'patSister', 'matBrother', 'matSister',
  'fullNephew', 'patNephew', 'fullUncle', 'patUncle', 'fullCousin', 'patCousin'];
const SINGLE: Heir[] = ['husband', 'father', 'mother', 'grandfather', 'grandmotherM', 'grandmotherF'];

type Counts = Record<Heir, number>;
type Shares = Partial<Record<Heir, Q>>;
type Dist = { total: Shares; treasury: Q };
/** A residuary class: who, how many, weight of one head (2 for a man, 1 for a woman). */
type Resid = [Heir, number, number];

function normalize(sex: 'm' | 'f', raw: Partial<Record<Heir, number>>): Counts {
  const c = {} as Counts;
  for (const h of HEIRS) {
    const v = Math.floor(Number(raw[h] ?? 0));
    c[h] = Number.isFinite(v) && v > 0 ? v : 0;
  }
  for (const h of SINGLE) c[h] = Math.min(c[h], 1);
  if (sex === 'm') c.husband = 0; else c.wife = 0;
  return c;
}

const sum = (s: Shares): Q => Object.values(s).reduce((a: Q, b) => add(a, b as Q), ZERO);

function scale(s: Shares, k: Q): Shares {
  const out: Shares = {};
  for (const [h, v] of Object.entries(s) as [Heir, Q][]) out[h] = mul(v, k);
  return out;
}

/** Fixed shares first (art. 335), the rest to the residuaries (art. 336); 'awl when the shares exceed the estate;
 *  radd to every fixed-share heir, spouse included, when no residuary takes the rest (art. 349 §6); the Treasury when
 *  there is no heir at all. Without radd (stage 2 of the bequest), the rest stays out, in `treasury`. */
function settle(fixed: Shares, resid: Resid[], radd = true): Dist {
  const F = sum(fixed);
  const units = resid.reduce((a, [, n, w]) => a + n * w, 0);
  if (units > 0) {
    if (cmp(F, ONE) >= 0) return { total: cmp(F, ONE) > 0 ? scale(fixed, div(ONE, F)) : { ...fixed }, treasury: ZERO };
    const rest = sub(ONE, F);
    const total: Shares = { ...fixed };
    for (const [h, n, w] of resid) {
      if (n <= 0) continue;
      total[h] = add(total[h] ?? ZERO, mul(rest, q(n * w, units)));
    }
    return { total, treasury: ZERO };
  }
  if (isZero(F)) return { total: {}, treasury: ONE };
  if (cmp(F, ONE) === 0) return { total: { ...fixed }, treasury: ZERO };
  if (cmp(F, ONE) < 0 && !radd) return { total: { ...fixed }, treasury: sub(ONE, F) };
  return { total: scale(fixed, div(ONE, F)), treasury: ZERO };
}

/** The class totals of one distribution, or 'mixed' (reading 4). */
function distribute(sex: 'm' | 'f', raw: Partial<Record<Heir, number>>, radd = true): Dist | 'mixed' {
  const c = normalize(sex, raw);
  const fixed: Shares = {};

  const son = c.son, dau = c.daughter;
  const desc = c.son + c.daughter + c.sonsSon + c.sonsDaughter > 0;      // الفرع الوارث
  const maleDesc = c.son + c.sonsSon > 0;
  const ss = son > 0 ? 0 : c.sonsSon;                                     // art. 358 §1
  const sd = son > 0 || (dau >= 2 && ss === 0) ? 0 : c.sonsDaughter;      // art. 358 §2
  const femDesc = dau + sd > 0;                                           // art. 352: the daughter or son's daughter
  const father = c.father > 0;
  const gf = !father && c.grandfather > 0;                                // art. 358 §3
  const mother = c.mother > 0;
  const gmM = !mother && c.grandmotherM > 0;                              // art. 358 §14
  const gmF = !mother && !father && c.grandmotherF > 0;                   // art. 358 §15
  const husband = c.husband > 0;
  const wives = c.wife;
  const ut = c.matBrother + c.matSister;
  const sibs = c.fullBrother + c.fullSister + c.patBrother + c.patSister + ut;   // art. 359 §1: heirs or not
  const fullOut = father || maleDesc;                                     // art. 358 §4 (the grandfather does not)
  const FB = fullOut ? 0 : c.fullBrother;
  const FS = fullOut ? 0 : c.fullSister;
  const PBc = fullOut ? 0 : c.patBrother;
  const PSc = fullOut ? 0 : c.patSister;

  // Spouse (arts 342–344).
  const spouseShare = husband ? (desc ? q(1, 4) : q(1, 2)) : wives > 0 ? (desc ? q(1, 8) : q(1, 4)) : ZERO;
  if (husband) fixed.husband = spouseShare;
  else if (wives > 0) fixed.wife = spouseShare;

  // Grandmothers: one sixth, shared when both inherit (art. 347 §6).
  const nGm = (gmM ? 1 : 0) + (gmF ? 1 : 0);
  if (gmM) fixed.grandmotherM = q(1, 6 * nGm);
  if (gmF) fixed.grandmotherF = q(1, 6 * nGm);

  // The Mushtaraka (art. 365).
  if (husband && (mother || nGm > 0) && !father && c.grandfather === 0 && !desc && ut >= 2 && c.fullBrother >= 1) {
    fixed.husband = q(1, 2);
    if (mother) fixed.mother = q(1, 6);
    const heads = ut + c.fullBrother + c.fullSister;
    for (const h of ['matBrother', 'matSister', 'fullBrother', 'fullSister'] as Heir[]) {
      if (c[h] > 0) fixed[h] = q(c[h], 3 * heads);
    }
    return { total: fixed, treasury: ZERO };
  }

  // Mother (arts 346 §1, 347 §2, 366).
  if (mother) {
    if (desc || sibs >= 2) fixed.mother = q(1, 6);
    else if (father && (husband || wives > 0)) fixed.mother = mul(q(1, 3), sub(ONE, spouseShare));
    else fixed.mother = q(1, 3);
  }

  // Daughters and son's daughters (arts 342, 345, 347 §3).
  if (son === 0 && dau > 0) fixed.daughter = dau === 1 ? q(1, 2) : q(2, 3);
  if (ss === 0 && sd > 0) fixed.sonsDaughter = dau === 0 ? (sd === 1 ? q(1, 2) : q(2, 3)) : q(1, 6);

  // The grandfather with full or paternal siblings (arts 354, 360–364).
  if (gf && !maleDesc && FB + FS + PBc + PSc > 0) return grandfatherWithSiblings(c, fixed, { husband, mother, nGm, desc, femDesc, ut });

  // Uterine siblings (arts 346 §2, 347 §5, 358 §13).
  if (!desc && !father && !gf && ut > 0) {
    const t = ut === 1 ? q(1, 6) : q(1, 3);
    if (c.matBrother > 0) fixed.matBrother = mul(t, q(c.matBrother, ut));
    if (c.matSister > 0) fixed.matSister = mul(t, q(c.matSister, ut));
  }

  // Father and grandfather: a sixth beside a descendant (arts 347 §1, §7, 353).
  if (father && desc) fixed.father = q(1, 6);
  if (gf && desc) fixed.grandfather = q(1, 6);

  // Full sisters by share (arts 342 §4, 345 §3).
  if (FB === 0 && FS > 0 && !femDesc && !gf) fixed.fullSister = FS === 1 ? q(1, 2) : q(2, 3);

  // Paternal siblings (art. 358 §5–6; art. 352: a full sister beside a daughter stands as a full brother).
  const patOut = fullOut || FB > 0 || (FS > 0 && femDesc);
  const PB = patOut ? 0 : PBc;
  const PS = patOut ? 0 : PSc;
  if (PB === 0 && PS > 0 && !femDesc && !gf) {
    if (FS === 0) fixed.patSister = PS === 1 ? q(1, 2) : q(2, 3);
    else if (FS === 1) fixed.patSister = q(1, 6);
  }

  // Residuaries in the order of art. 349, ties by arts 350–352.
  let resid: Resid[] = [];
  if (son > 0) resid = [['son', son, 2], ['daughter', dau, 1]];
  else if (ss > 0) resid = [['sonsSon', ss, 2], ['sonsDaughter', c.sonsDaughter, 1]];
  else if (father) resid = [['father', 1, 1]];
  else if (gf) resid = [['grandfather', 1, 1]];
  else if (FB > 0) resid = [['fullBrother', FB, 2], ['fullSister', FS, 1]];
  else if (FS > 0 && femDesc) resid = [['fullSister', FS, 1]];
  else if (PB > 0) resid = [['patBrother', PB, 2], ['patSister', PS, 1]];
  else if (PS > 0 && femDesc) resid = [['patSister', PS, 1]];
  else {
    for (const h of ['fullNephew', 'patNephew', 'fullUncle', 'patUncle', 'fullCousin', 'patCousin'] as Heir[]) {
      if (c[h] > 0) { resid = [[h, c[h], 1]]; break; }
    }
  }
  return settle(fixed, resid, radd);
}

function grandfatherWithSiblings(
  c: Counts, fixed: Shares,
  o: { husband: boolean; mother: boolean; nGm: number; desc: boolean; femDesc: boolean; ut: number },
): Dist | 'mixed' {
  const FB = c.fullBrother, FS = c.fullSister, PB = c.patBrother, PS = c.patSister;

  // Arts 362 and 363 as written; any other brother under the same conditions is 'mixed' (reading 4).
  if (o.husband && (o.mother || o.nGm > 0) && o.ut >= 2 && !o.desc) {
    const malikiyya = PB >= 1 && PS === 0 && FB === 0 && FS === 0;
    const shibh = FB >= 1 && FS === 0 && PB === 0 && PS === 0;
    if (malikiyya || shibh) {
      const total: Shares = { ...fixed, husband: q(1, 2), grandfather: q(1, 3) };
      if (o.mother) total.mother = q(1, 6);
      return { total, treasury: ZERO };
    }
    if (FB + PB >= 1) return 'mixed';
  }

  // The Akdariyya (art. 361), with its own numbers: 9, 6, 4 and 8 of 27.
  if (o.husband && o.mother && !o.desc && o.ut === 0 && FB === 0 && PB === 0 && FS + PS === 1) {
    const total: Shares = { husband: q(9, 27), mother: q(6, 27), grandfather: q(8, 27) };
    total[FS === 1 ? 'fullSister' : 'patSister'] = q(4, 27);
    return { total, treasury: ZERO };
  }

  const f = sum(fixed);
  const R = sub(ONE, f);
  // What the shares leave is a sixth or less: the grandfather takes a sixth, by 'awl if needed (reading 3).
  if (cmp(R, q(1, 6)) <= 0) return settle({ ...fixed, grandfather: q(1, 6) }, []);

  // Art. 354: the best of a sixth of the whole (beside fixed shares), a third of what is left, sharing as a brother
  // with the paternal siblings counted against him (art. 360).
  const units = 2 + 2 * FB + FS + 2 * PB + PS;
  const g = max(isZero(f) ? ZERO : q(1, 6), mul(R, q(1, 3)), mul(R, q(2, units)));
  const P = sub(R, g);
  const total: Shares = { ...fixed, grandfather: g };
  const share = (rest: Q, cls: Resid[]) => {
    const u = cls.reduce((a, [, n, w]) => a + n * w, 0);
    if (u === 0 || isZero(rest)) return;
    for (const [h, n, w] of cls) if (n > 0) total[h] = mul(rest, q(n * w, u));
  };
  const full = FB + FS > 0, pat = PB + PS > 0;
  if (full && pat) {
    // Art. 360: the full siblings take back what was counted for the paternal ones; a single full sister only up
    // to her half, the rest to the paternal siblings. A full sister beside a daughter takes what she would take
    // without the grandfather, which is all of it (art. 352).
    if (FB > 0 || FS >= 2 || o.femDesc) share(P, [['fullBrother', FB, 2], ['fullSister', FS, 1]]);
    else {
      const fs = min(P, q(1, 2));
      total.fullSister = fs;
      share(sub(P, fs), [['patBrother', PB, 2], ['patSister', PS, 1]]);
    }
  } else if (full) share(P, [['fullBrother', FB, 2], ['fullSister', FS, 1]]);
  else share(P, [['patBrother', PB, 2], ['patSister', PS, 1]]);
  return { total, treasury: ZERO };
}

// ---------------------------------------------------------------------------------------------------------------
// The compulsory bequest (arts 369–372, reading 8).

/** Stage 2 counts only the heirs who take before or beside the dead child's children: spouse, parent, the grandfather
 *  (or his father in his place) and the grandmother through the deceased, and the children. No sibling, nephew,
 *  uncle or cousin. */
function stageTwoCounts(sex: 'm' | 'f', base: Counts, b: Branch): Partial<Record<Heir, number>> {
  const c2: Partial<Record<Heir, number>> = { son: b.sons, daughter: b.daughters };
  if (b.spouse) { if (b.sex === 'm') c2.wife = 1; else c2.husband = 1; }
  if (sex === 'm') {
    if (b.parent && base.wife > 0) c2.mother = 1;
    c2.grandfather = base.father > 0 || base.grandfather > 0 ? 1 : 0;   // الجد وإن علا
    c2.grandmotherF = base.mother;
  } else {
    if (b.parent && base.husband > 0) c2.father = 1;
    c2.grandmotherM = base.mother;
  }
  return c2;
}

const nonNeg = (x: number) => (Number.isFinite(x) && x > 0 ? Math.floor(x) : 0);

export function second(input: Input): Output {
  const sex = input.deceased;
  const branches = (input.predeceased ?? []).map((b) => ({ ...b, sons: nonNeg(b.sons), daughters: nonNeg(b.daughters) }));
  const base = normalize(sex, input.counts);

  // The real heirs: a predeceased son's children stand among the son's children (reading 7).
  const real: Counts = { ...base };
  for (const b of branches) if (b.sex === 'm') { real.sonsSon += b.sons; real.sonsDaughter += b.daughters; }
  const d0 = distribute(sex, real);
  if (d0 === 'mixed') return { stop: 'mixed' };

  const sonsChildrenTake = !isZero(add(d0.total.sonsSon ?? ZERO, d0.total.sonsDaughter ?? ZERO));
  const owed = branches.map((b) => b.sons + b.daughters > 0 && (b.sex === 'f' || !sonsChildrenTake));

  const bequests: { son: Q; daughter: Q }[] = branches.map(() => ({ son: ZERO, daughter: ZERO }));
  let T = ZERO;
  if (owed.some(Boolean)) {
    // Stage 1: every owed dead child alive beside the real heirs.
    const c1: Counts = { ...base };
    branches.forEach((b, i) => {
      if (owed[i]) { if (b.sex === 'm') c1.son += 1; else c1.daughter += 1; }
      else if (b.sex === 'm') { c1.sonsSon += b.sons; c1.sonsDaughter += b.daughters; }
    });
    const d1 = distribute(sex, c1);
    if (d1 === 'mixed') return { stop: 'mixed' };
    const oneSon = c1.son > 0 ? div(d1.total.son ?? ZERO, q(c1.son)) : ZERO;
    const oneDaughter = c1.daughter > 0 ? div(d1.total.daughter ?? ZERO, q(c1.daughter)) : ZERO;

    // Stage 2: the dead child's share as their own estate, without radd; their children's part is the bequest, and
    // what is left of the share goes back to the first estate.
    const whole: Q[] = branches.map(() => ZERO);
    branches.forEach((b, i) => {
      if (!owed[i]) return;
      const s1 = b.sex === 'm' ? oneSon : oneDaughter;
      const d2 = distribute(b.sex, stageTwoCounts(sex, base, b), false);
      if (d2 === 'mixed') return;
      const sonsPart = mul(s1, d2.total.son ?? ZERO);
      const daughtersPart = mul(s1, d2.total.daughter ?? ZERO);
      whole[i] = add(sonsPart, daughtersPart);
      bequests[i] = {
        son: b.sons > 0 ? div(sonsPart, q(b.sons)) : ZERO,
        daughter: b.daughters > 0 ? div(daughtersPart, q(b.daughters)) : ZERO,
      };
    });
    T = whole.reduce(add, ZERO);
    // Never more than a third (art. 370).
    if (cmp(T, q(1, 3)) > 0) {
      const k = div(q(1, 3), T);
      for (const x of bequests) { x.son = mul(x.son, k); x.daughter = mul(x.daughter, k); }
      T = q(1, 3);
    }
  }

  const keep = sub(ONE, T);
  const each: Partial<Record<Heir, string>> = {};
  for (const h of HEIRS) {
    const t = d0.total[h];
    if (!t || isZero(t) || real[h] === 0) continue;
    each[h] = str(mul(div(t, q(real[h])), keep));
  }
  return {
    each,
    bequest: bequests.map((x) => ({ son: str(x.son), daughter: str(x.daughter) })),
    treasury: str(mul(d0.treasury, keep)),
  };
}
