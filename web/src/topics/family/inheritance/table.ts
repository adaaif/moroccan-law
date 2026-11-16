/** The adoul's table (IR19 of the inheritance review): the heirs' own case as a deed sets it out. The base the code
 *  gives («أصل المسألة»), the base after a rise («العول») or a return («الرد»), the multiplier that makes every person's
 *  part whole («جزء السهم»), and the corrected number («تصح من»). What was taken out first (a bequest, a will, a
 *  «تنزيل») does not enter it: the heirs' table is theirs, and the page says what it applies to. Pure. */
import type { Basis, Heir, Result } from './engine.ts';
import { div, lcm, q, type Q } from './frac.ts';

type Solved = Extract<Result, { ok: true }>;

export type Row = {
  heir: Heir; count: number; basis: Basis;
  /** The fixed share the code names, before any rise or return; null for a pure residuary. */
  fard: Q | null;
  /** The group's shares out of the working base (after a rise or a return). */
  group: bigint;
  /** One person's shares out of the corrected number. */
  each: bigint;
};
export type Table = {
  rows: Row[];
  /** «أصل المسألة», as the fixed shares give it. */
  base: bigint;
  /** The base after the rise, when the fixed shares exceed the estate. */
  awl: bigint | null;
  /** The base after the return, when a rest came back to the heirs of fixed shares. */
  radd: bigint | null;
  /** The base the groups' shares are out of: `awl`, `radd`, or `base`. */
  working: bigint;
  /** «جزء السهم»: what the working base is multiplied by so that every person's part is whole. */
  times: bigint;
  /** «تصح من». */
  corrected: bigint;
  /** The Treasury's shares out of the corrected number. */
  treasury: bigint;
};

export function tableOf(r: Solved): Table {
  // Each line's own share: what it is of the part left to the heirs.
  const own = r.lines.map((l) => ({ l, share: l.own, each: div(l.own, q(l.count)) }));
  const ownTreasury = r.ownTreasury;
  const working = [...own.map((o) => o.share.d), ownTreasury.d].reduce((a, b) => lcm(a, b), 1n);
  const corrected = r.ownTashih;
  return {
    rows: own.map(({ l, share, each }) => ({
      heir: l.heir, count: l.count, basis: l.basis, fard: l.fard,
      group: (share.n * working) / share.d, each: (each.n * corrected) / each.d,
    })),
    base: r.base, awl: r.awl, radd: r.radd ? working : null, working, times: corrected / working, corrected,
    treasury: (ownTreasury.n * corrected) / ownTreasury.d,
  };
}
