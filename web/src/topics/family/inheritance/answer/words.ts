/** What every part of the answer says the same way (IR18, IR21 of the inheritance review): who a line is, the share
 *  in words or out of the one number, the dirhams, the parts of the estate in the order they leave it. The family's
 *  answer, the adoul's table, the steps and the sheet all read from here, so a line is never named two ways. */
import { sexOf, type Case } from '../case';
import type { BequestLine, Cite, Excluded, Heir, Named } from '../engine';
import type { CSSProperties } from 'react';
import { mul, q, type Q } from '../frac';
import { formatAmount } from '../money';
import { eachKin, kin, lawEachKin, lawKin, midKin, ofKin, sayShare } from '../parts/say';
import type { Answer, Share } from '../solve';
import type { useT } from '../strings';

export type T = ReturnType<typeof useT>['t'];
export type Ok = Extract<Answer, { state: 'ok' }>;
export type Sex = 'm' | 'f';

/** The article each case the code names is written in. */
export const NAMED_ART: Record<Named, Cite> = {
  muadda: 360, akdariyya: 361, malikiyya: 362, shibhMalikiyya: 363, kharqa: 364, mushtaraka: 365, gharrawayn: 366,
  mubahala: 367, minbariyya: 368,
};
export const BEQUEST_ARTS: Cite[] = [369, 370, 371, 372];
export const CHOICES = '/topics/family/tools/inheritance/choices';

/** A part of a whole as a number of the estate, rounded to the centime: for a figure that is said, not paid. */
const centsOf = (net: bigint, x: Q): bigint => (net * x.n * 2n + x.d) / (2n * x.d);

export function money(a: Ok, t: T, lang: string) {
  const net = a.money?.net ?? null;
  const dh = (cents: bigint) => t('answer.dh', { amount: formatAmount(cents, lang) });
  return {
    net,
    dh,
    /** « (280.000 درهم)» after a share, or nothing without an estate. */
    paren: (x: Q) => (net === null ? '' : ` (${dh(centsOf(net, x))})`),
    /** One person's amount as allotted, to the centime. */
    paid: (s: Share) => (a.paid ? dh(a.paid.each[s.key]) : null),
  };
}

/** A share as a family reads it: the code's word when it has one («الثمن»), out of the one number when there is one
 *  («18 من 144»), else its own fraction («2 من 9»). Never a bare number. */
export function shareWords(x: Q, common: bigint | null, t: T): { words: string | null; of: string | null } {
  const plain = sayShare(x, t);
  const named = x.n === x.d || ['1/2', '1/3', '2/3', '1/4', '1/6', '1/8'].includes(`${x.n}/${x.d}`);
  const of = common && common > 1n && (common % x.d === 0n)
    ? t('answer.of', { n: (x.n * (common / x.d)).toString(), d: common.toString() }) : null;
  if (named) return { words: plain, of: of && of !== plain && x.n !== x.d ? of : null };
  return { words: of ? null : plain, of };
}
export const sayIt = (x: Q, common: bigint | null, t: T) => {
  const w = shareWords(x, common, t);
  return [w.words, w.of].filter(Boolean).join(' · ');
};

/** «أولاد الابن الذي توفي قبله», numbered when two dead children of one sex left children. */
export function branchName(b: BequestLine, n: number, all: BequestLine[], deceased: Sex, t: T): string {
  const same = all.filter((x) => x.sex === b.sex);
  const name = t(`answer.branch_${b.sex}_${deceased}`);
  return same.length > 1 ? `${name} — ${same.indexOf(all[n]) + 1}` : name;
}

/** «الابن الذي توفي بعده», numbered when two of one kind died since. */
export function laterName(a: Ok, n: number, deceased: Sex, t: T, law = false): string {
  const h = a.later[n].later.heir;
  const same = a.later.filter((x) => x.later.heir === h);
  const name = t(`answer.later.head_${sexOf(h)}`, { heir: (law ? lawKin : kin)(h, 1, t), after: t(`answer.after_${deceased}`) });
  return same.length > 1 ? `${name} — ${same.indexOf(a.later[n]) + 1}` : name;
}

/** The kind of person a line is about, read from its key: an heir, a dead child's son or daughter, and the rest. */
function kindOf(s: Share): { heir?: Heir; grand?: Sex; branch?: number } {
  const key = s.later !== undefined ? s.key.replace(/^l\d+\.?/, '') : s.key;
  const b = /^b(\d+)\.(son|daughter)$/.exec(key);
  if (b) return { grand: b[2] === 'son' ? 'm' : 'f', branch: Number(b[1]) };
  return { heir: s.heir };
}

/** One line's person: «كل بنت (3)», «الحفيدة», «بيت المال». */
export function lineName(s: Share, t: T, law = false): string {
  const k = kindOf(s);
  const count = s.count > 1 ? ` (${s.count})` : '';
  if (k.heir) return `${(law ? lawEachKin : eachKin)(k.heir, s.count, t)}${count}`;
  if (k.grand) return `${t(s.count > 1 ? (k.grand === 'm' ? 'answer.grandsons' : 'answer.granddaughters') : (k.grand === 'm' ? 'answer.grandson' : 'answer.granddaughter'))}${count}`;
  if (s.group === 'will') return t('answer.will.who');
  if (s.group === 'tanzil') return `${t(s.count > 1 ? 'answer.tanzil.many' : 'answer.tanzil.one')}${count}`;
  return t('answer.treasury');
}

/** The group's name for a list of relatives: «البنات (3)». */
export const groupName = (h: Heir, count: number, t: T, law = false) => `${(law ? lawKin : kin)(h, count, t)}${count > 1 ? ` (${count})` : ''}`;

/** The parts of the estate, in the order they leave it (art. 322): the compulsory bequest, a will, a «تنزيل», then the
 *  heirs, each heir who died since as one part, the Treasury. What the bar draws and its legend names. */
export type Part = { key: string; name: string; share: Q; tone: 'heir' | 'bequest' | 'will' | 'later' | 'treasury' };
export function partsOf(a: Ok, c: Case, t: T, lang = 'ar'): Part[] {
  const r = a.result;
  const total = (s: Share) => mul(s.each, q(s.count));
  const out: Part[] = r.bequest.map((b, n) => ({ key: `b${n}`, name: branchName(b, n, r.bequest, c.deceased, t), share: b.share, tone: 'bequest' as const }))
    .filter((p) => p.share.n > 0n);
  for (const s of a.shares) {
    if (s.group === 'will') out.push({ key: s.key, name: t('answer.will.who'), share: total(s), tone: 'will' });
    if (s.group === 'tanzil') out.push({ key: s.key, name: t('answer.tanzil.legend'), share: total(s), tone: 'will' });
  }
  for (const s of a.shares) if (s.group === 'heir' && s.heir) out.push({ key: s.key, name: groupName(s.heir, s.count, t), share: total(s), tone: 'heir' });
  a.later.forEach((la, n) => {
    if (la.gone || la.share.n === 0n) return;
    out.push({ key: `l${n}`, name: t('answer.later.legend', { heir: ofKin(la.later.heir, t, lang) }), share: la.share, tone: 'later' });
  });
  for (const s of a.shares) if (s.group === 'treasury') out.push({ key: s.key, name: t('answer.treasury'), share: total(s), tone: 'treasury' });
  return out;
}

/** The colours of the bar and of the swatches beside the lines: shades of the topic's colour, the heirs' alternating
 *  so neighbours differ; the bequest hatched, a will or a «تنزيل» in grey, the Treasury in the field's grey. */
const mix = (p: number) => `color-mix(in srgb, var(--t) ${p}%, var(--color-sheet))`;
const deep = (p: number) => `color-mix(in srgb, var(--t) ${p}%, var(--color-ink))`;
const SHADES = [mix(100), mix(48), deep(58), mix(22), mix(74), deep(80)];
export function colourOf(parts: Part[]): Record<string, CSSProperties> {
  let h = 0;
  const out: Record<string, CSSProperties> = {};
  for (const p of parts) {
    if (p.tone === 'heir') out[p.key] = { background: SHADES[h++ % SHADES.length] };
    else if (p.tone === 'bequest') out[p.key] = { background: `repeating-linear-gradient(135deg, var(--t) 0 3px, ${mix(28)} 3px 7px)` };
    else if (p.tone === 'later') out[p.key] = { background: `repeating-linear-gradient(45deg, ${mix(70)} 0 3px, ${mix(18)} 3px 7px)` };
    else if (p.tone === 'will') out[p.key] = { background: 'color-mix(in srgb, var(--color-ink-soft) 55%, var(--color-sheet))' };
    else out[p.key] = { background: 'var(--color-field)' };
  }
  return out;
}

/** Each line's swatch: an heir's line takes its group's colour; a dead child's grandchildren their branch's; the heirs
 *  of an heir who died since, that heir's. */
export function swatchKey(s: Share): string {
  if (s.group === 'bequest') return s.key.split('.')[0];
  if (s.group === 'later') return `l${s.later}`;
  return s.key;
}


/** The day as the Bulletin prints it, in Morocco: «14 نونبر 2026». */
export function longDay(iso: string, lang: string): string {
  const [y, m, d] = iso.split('-').map(Number);
  return new Intl.DateTimeFormat(lang === 'fr' ? 'fr-MA' : 'ar-MA', { day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC' })
    .format(new Date(Date.UTC(y, (m || 7) - 1, d || 1)));
}

/** Why someone takes nothing, in plain words; a dead son's children shut out as heirs are said to take by the
 *  compulsory bequest (IR18: never «لا يرث» alone for a grandchild who has a bequest). */
export function outWords(e: Excluded, r: Ok['result'], t: T, lang = 'ar', law = false): string {
  const lower = (s: string) => (lang === 'fr' ? s.charAt(0).toLowerCase() + s.slice(1) : s);
  const by = e.by === 'rule' ? '' : law ? lower(lawKin(e.by, 1, t)) : midKin(e.by, t, lang);
  // The sheet for the adouls says it in the code's wording, the page in the family's.
  const reason = t(`${law ? 'lawOut' : 'out'}.${e.why}`, { by });
  const viaBequest = (e.heir === 'sonsSon' || e.heir === 'sonsDaughter')
    && r.bequest.some((b) => b.sex === 'm' && (e.heir === 'sonsSon' ? b.sons : b.daughters) > 0 && b.share.n > 0n);
  return viaBequest ? `${reason}${t(`answer.out.bequest_${e.count > 1 ? 'many' : sexOf(e.heir)}`)}` : reason;
}
