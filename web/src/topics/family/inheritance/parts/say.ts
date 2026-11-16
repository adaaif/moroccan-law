import type { Heir } from '../engine';
import type { Q } from '../frac';
import type { useT } from '../strings';

type T = ReturnType<typeof useT>['t'];

/** A share said as a person says it (IR15, IR18): «الثمن», «الثلثان», «التركة كلها», or «5 من 48»: never a bare
 *  number, which a reader takes for a count. */
export function sayShare(x: Q, t: T): string {
  if (x.n === x.d) return t('shell.say.all');
  const key = `${x.n}/${x.d}`;
  return ['1/2', '1/3', '2/3', '1/4', '1/6', '1/8'].includes(key) ? t(`shell.say.${key}`) : t('shell.say.of', { n: x.n.toString(), d: x.d.toString() });
}

/** A name without the code's word in brackets beside it: «خوه من الأب والأم» of «خوه من الأب والأم (شقيق)». */
export const bare = (s: string) => s.replace(/\s*\([^()]*\)$/, '');

/** A relative by name, in the family's words: one («البنت»), several («البنات»), or each of several («كل بنت»). */
export const kin = (h: Heir, count: number, t: T): string => bare((count > 1 && t(`heirs.${h}`, { defaultValue: '' })) || t(`heir.${h}`));
export const eachKin = (h: Heir, count: number, t: T): string => bare(count > 1 ? t(`each.${h}`) : t(`heir.${h}`));
/** The same in the code's own words («الأخ الشقيق», «كل أخ شقيق»), for the adoul's table and the sheet. */
export const lawKin = (h: Heir, count: number, t: T): string => (count > 1 && t(`lawHeirs.${h}`, { defaultValue: '' })) || t(`lawHeir.${h}`);
export const lawEachKin = (h: Heir, count: number, t: T): string => (count > 1 ? t(`lawEach.${h}`) : t(`lawHeir.${h}`));
/** A relative named inside a sentence («مع الابن», «avec le fils»): French lowers the article's capital. */
export const midKin = (h: Heir, t: T, lang: string): string => {
  const s = kin(h, 1, t);
  return lang === 'fr' ? s.charAt(0).toLowerCase() + s.slice(1) : s;
};

/** A part of the estate as a percentage with one decimal, the sign to the right of its number whatever the page's
 *  direction (the charts' rule): «12,5 %» inside an isolate. */
export function percent(x: Q): string {
  const tenths = (x.n * 2000n + x.d) / (2n * x.d);
  const s = tenths % 10n ? `${tenths / 10n},${tenths % 10n}` : `${tenths / 10n}`;
  // A no-break space: the sign never falls alone onto the next line.
  return `⁦${s}\u00A0%⁩`;
}
/** «ورثة البنت», «héritiers du fils»: French joins «de» to the article. */
export const ofKin = (h: Heir, t: T, lang: string): string => {
  const s = midKin(h, t, lang);
  return lang === 'fr' ? s.replace(/^le /, 'du ').replace(/^les /, 'des ').replace(/^(la |l’)/, 'de $1') : s;
};
