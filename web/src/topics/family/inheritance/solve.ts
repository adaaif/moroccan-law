/** A case solved for the page (IR5, IR7, IR18–IR26 of the inheritance review): what leaves the estate first
 *  (art. 322), the shares, each person's dirhams to the centime, an heir who died before the division with their own
 *  heirs, and the adoul's numbers. The screens only draw what this returns. Pure. */
import { compute, type Cite, type Heir, type Line, type Result } from './engine.ts';
import { ONE, ZERO, cmp, isZero, lcm, mul, q, sub, type Q } from './frac.ts';
import { allot, type Paid, type Payee } from './money.ts';
import { nobody, sexOf, type Case, type Later } from './case.ts';

type Solved = Extract<Result, { ok: true }>;

/** Centimes: what was left, what leaves first, and what the third and the shares are counted on. */
export type Money = { gross: bigint; funeral: bigint; debts: bigint; dowry: bigint; net: bigint };

/** Who is paid, by a key the page can name: an heir's kind («wife»), a dead child's sons or daughters («b0.son»), a
 *  will («will»), those set in an heir's place («tanzil»), the Treasury («treasury»), and the heirs of an heir who
 *  died since («l0.mother», «l0.b1.son», «l0.treasury»). */
export type Share = Payee & { group: 'heir' | 'bequest' | 'will' | 'tanzil' | 'treasury' | 'later'; heir?: Heir; later?: number };

/** An heir who died since: their part of the first estate, shared among their own heirs. `gone`: that kind of heir
 *  takes nothing in the first estate, so there is nothing to pass on. */
export type LaterAnswer = { later: Later; share: Q; result: Result | null; gone: boolean };

export type Answer =
  | { state: 'empty' }
  /** `unborn`, `other`: IR7's stops. `mixed`: arts 362–363's mixed forms. `before`: a death older than the rules held.
   *  `overdrawn`: what leaves the estate first is more than what was left. */
  | { state: 'stop'; why: 'unborn' | 'other' | 'mixed' | 'before' | 'overdrawn'; cites: Cite[] }
  | {
    state: 'ok'; result: Solved; money: Money | null; shares: Share[]; paid: Paid | null; later: LaterAnswer[];
    /** The number every part comes right from («الجامعة»): the shares of all, the later estates' too, as whole numbers
     *  of it. Null when a will given as an amount makes it unreadable; the heirs' own table still stands. */
    common: bigint | null;
    /** A will was typed but no estate: its part cannot be known, so it was left out and the page asks for the amount. */
    willWaits: boolean;
  };

const cents = (s: string): bigint => (s ? BigInt(s) : 0n);

/** The case's money, when an amount was given. */
export function moneyOf(c: Case): Money | null {
  if (!c.estate) return null;
  const gross = cents(c.estate), funeral = cents(c.funeral), debts = cents(c.debts), dowry = cents(c.dowry);
  return { gross, funeral, debts, dowry, net: gross - funeral - debts - dowry };
}

function willShare(c: Case, net: bigint | null): Q | null {
  if (!c.will?.value) return null;
  if (c.will.kind === 'part') {
    const [n, d] = c.will.value.split('/').map(Number);
    return n > 0 && d > 0 && n <= d ? q(n, d) : null;
  }
  const amount = cents(c.will.value);
  if (net === null || net <= 0n || amount <= 0n) return null;
  return amount >= net ? ONE : q(amount, net);
}

export function solve(c: Case): Answer {
  if (nobody(c)) return { state: 'empty' };
  if (c.unborn) return { state: 'stop', why: 'unborn', cites: [331] };
  if (c.other) return { state: 'stop', why: 'other', cites: [326, 332, 333] };
  const money = moneyOf(c);
  if (money && money.net < 0n) return { state: 'stop', why: 'overdrawn', cites: [322] };
  const share = willShare(c, money ? money.net : null);
  const willWaits = Boolean(c.will?.value && c.will.kind === 'amount' && !money);
  const result = compute({
    deceased: c.deceased, died: c.died ? (c.died.length === 4 ? `${c.died}-07-01` : c.died) : undefined, counts: c.counts,
    predeceased: c.branches, will: share ? { share, heir: c.will?.heir, agreed: c.will?.agreed } : undefined, tanzil: c.tanzil ?? undefined,
  });
  // A death before 4 April 1958 is older than the first code: the Maliki rite alone, which the tool does not count.
  if (!result.ok) return { state: 'stop', why: result.reason, cites: result.reason === 'mixed' ? result.cites : [] };

  // Heirs who died since: one of that kind's people each, their part passed to their own heirs.
  const gone: Partial<Record<Heir, number>> = {};
  const later: LaterAnswer[] = c.later.map((l) => {
    const line = result.lines.find((x) => x.heir === l.heir);
    const taken = gone[l.heir] ?? 0;
    if (!line || taken >= line.count) return { later: l, share: ZERO, result: null, gone: true };
    gone[l.heir] = taken + 1;
    const theirs = compute({ deceased: sexOf(l.heir), counts: l.counts, predeceased: l.branches });
    return { later: l, share: line.each, result: theirs, gone: false };
  });

  const shares: Share[] = [];
  const line = (l: Line, key: string, count: number, each: Q, extra: Partial<Share>) =>
    count > 0 && shares.push({ key, count, each, group: 'heir', heir: l.heir, ...extra });
  for (const l of result.lines) line(l, l.heir, l.count - (gone[l.heir] ?? 0), l.each, {});
  result.bequest.forEach((b, n) => {
    if (b.sons) shares.push({ key: `b${n}.son`, count: b.sons, each: b.son, group: 'bequest' });
    if (b.daughters) shares.push({ key: `b${n}.daughter`, count: b.daughters, each: b.daughter, group: 'bequest' });
  });
  if (result.will && !isZero(result.will.granted)) shares.push({ key: 'will', count: 1, each: result.will.granted, group: 'will' });
  if (result.tanzil && !isZero(result.tanzil.total)) shares.push({ key: 'tanzil', count: c.tanzil?.count ?? 1, each: result.tanzil.each, group: 'tanzil' });
  if (!isZero(result.treasury)) shares.push({ key: 'treasury', count: 1, each: result.treasury, group: 'treasury' });
  later.forEach((la, n) => {
    const r = la.result;
    if (la.gone) return;
    // A later estate the engine does not decide stays whole on its line: the page says it goes to an adoul.
    if (!r || !r.ok) { shares.push({ key: `l${n}`, count: 1, each: la.share, group: 'later', later: n }); return; }
    for (const l of r.lines) shares.push({ key: `l${n}.${l.heir}`, count: l.count, each: mul(l.each, la.share), group: 'later', heir: l.heir, later: n });
    r.bequest.forEach((b, k) => {
      if (b.sons) shares.push({ key: `l${n}.b${k}.son`, count: b.sons, each: mul(b.son, la.share), group: 'later', later: n });
      if (b.daughters) shares.push({ key: `l${n}.b${k}.daughter`, count: b.daughters, each: mul(b.daughter, la.share), group: 'later', later: n });
    });
    if (!isZero(r.treasury)) shares.push({ key: `l${n}.treasury`, count: 1, each: mul(r.treasury, la.share), group: 'later', later: n });
  });

  // The common number: unreadable once a will's amount is one of the parts.
  const amountWill = Boolean(result.will && c.will?.kind === 'amount' && !isZero(result.will.granted));
  const common = amountWill ? null : shares.reduce((d, s) => lcm(d, s.each.d), 1n);
  const paid = money ? allot(money.net, shares) : null;
  return { state: 'ok', result, money, shares, paid, later, common, willWaits };
}

/** What the estate lacks of being whole in the shares listed: zero always; kept for the tests. */
export const whole = (shares: Share[]): Q => shares.reduce((s, x) => sub(s, mul(x.each, q(x.count))), ONE);
export const closes = (shares: Share[]) => cmp(whole(shares), ZERO) === 0;
