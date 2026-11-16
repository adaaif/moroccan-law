import { sexOf } from '../case';
import type { Heir } from '../engine';
import type { useT } from '../strings';

type T = ReturnType<typeof useT>['t'];
export type Sex = 'm' | 'f';

/** A relative in the family's words, the code's word in brackets beside it (IR14 of the inheritance review); the
 *  Arabic possessive agrees with who died («خوه», «خوها»): `heirF`, `heirsF` and `eachF` are a woman's. */
export function heirName(h: Heir, count: number, deceased: Sex, t: T): string {
  const f = deceased === 'f' ? 'F' : '';
  return (count > 1 && t(`heirs${f}.${h}`, { defaultValue: '' })) || t(`heir${f}.${h}`);
}

/** «كل بنت», or the one relative there is. */
export const eachName = (h: Heir, count: number, deceased: Sex, t: T): string =>
  (count > 1 ? t(`each${deceased === 'f' ? 'F' : ''}.${h}`) : heirName(h, 1, deceased, t));

/** The name without the code's word: for a tile, a folded answer, the running line. */
export const bare = (s: string) => s.replace(/\s*\([^()]*\)$/, '');
/** The code's word alone («شقيق», «germain»), or ''. */
export const codeWord = (s: string) => /\(([^()]*)\)$/.exec(s)?.[1] ?? '';

/** «لا يرث هنا», agreeing with the relative's sex and number. */
export const outWord = (h: Heir, count: number, t: T) => t(`ask.tree.out.${sexOf(h)}${count > 1 ? 'p' : ''}`);

/** A name inside a sentence («مع الابن», «avec le fils»): French lowers the article's capital. */
export const inSentence = (s: string, lang: string) => (lang === 'fr' ? s.charAt(0).toLowerCase() + s.slice(1) : s);
