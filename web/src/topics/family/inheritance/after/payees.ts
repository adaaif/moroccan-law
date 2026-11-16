/** Who is paid, as the page names them (IR24): a kind of heir, a grandchild of the compulsory bequest, the will's
 *  legatee, those set in an heir's place, the Treasury; and for an heir who died since, their own heir and through
 *  whom. Kinds only, never a person's name (IR17 was declined). Pure. */
import { sexOf } from '../case';
import { eachKin, kin } from '../parts/say';
import type { Answer, Share } from '../solve';
import type { useT } from '../strings';

type T = ReturnType<typeof useT>['t'];
export type Ok = Extract<Answer, { state: 'ok' }>;
export type Named = { name: string; of: string | null; sex: 'm' | 'f' };

/** `count`: how many of the group the line speaks of («كل بنت» for several, «البنت» for one). `tOf`: the words that
 *  agree with another dead person, since the heirs of an heir who died since are that heir's relatives («خوها»). */
export function payee(s: Share, a: Ok, t: T, count = s.count, tOf: (sex: 'm' | 'f') => T = () => t): Named {
  const tail = s.key.split('.').pop();
  let name = '';
  let sex: 'm' | 'f' = 'm';
  const late = s.group === 'later' && s.later !== undefined && a.later[s.later] ? a.later[s.later].later.heir : null;
  if (s.heir) { name = eachKin(s.heir, count, late ? tOf(sexOf(late)) : t); sex = sexOf(s.heir); }
  else if (s.group === 'will') name = t('after.payee.will');
  else if (s.group === 'tanzil') name = t(count > 1 ? 'after.payee.eachTanzil' : 'after.payee.tanzil');
  else if (s.group === 'treasury' || tail === 'treasury') name = t('after.payee.treasury');
  else if (tail === 'son') name = t(count > 1 ? 'after.payee.eachGrandson' : 'after.payee.grandson');
  else if (tail === 'daughter') { name = t(count > 1 ? 'after.payee.eachGranddaughter' : 'after.payee.granddaughter'); sex = 'f'; }
  let of: string | null = null;
  if (s.group === 'later' && s.later !== undefined && a.later[s.later]) {
    const h = a.later[s.later].later.heir;
    const who = kin(h, 1, t);
    const g = sexOf(h);
    // A later estate the engine does not decide stays whole on one line, named by whose part it is.
    if (!name) { name = t(`after.payee.whole_${g}`, { who }); sex = g; }
    else of = t(`after.payee.of_${g}`, { who: who.charAt(0).toLowerCase() + who.slice(1) });
  }
  return { name, of, sex };
}

/** One person's part as the land registry writes it: «18 من 144» out of the common number, or as the share's own
 *  fraction when a will given as an amount leaves no common number. */
export function outOf(s: Share, common: bigint | null): { n: bigint; d: bigint } {
  return common ? { n: (s.each.n * common) / s.each.d, d: common } : { n: s.each.n, d: s.each.d };
}
