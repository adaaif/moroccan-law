/** The articles «what surrounds the shares» rests on (IR23–IR25 of the inheritance review, 14 Nov 2026), each with
 *  the address it opens, the law it belongs to and the chip's words in the page's language: the family code's through
 *  `codePath`, and the other laws a family meets after the shares, read in the corpus the day these lines were
 *  written. Pure. */
import { article, type Cite } from '../engine';
import { citeLabel, codePath, type useT } from '../strings';

type T = ReturnType<typeof useT>['t'];
export type Ref = { path: string; label: string; law: string };

/** Law 39.08 (real rights: co-ownership, pre-emption, partition), the DOC, the tax code, law 51.26 (the adouls), and
 *  decree 2.22.04 (civil status: the 30 days to declare a death). */
const ROOT = {
  rights: '/ma/loi/39-08', doc: '/ma/code/doc', cgi: '/ma/code/cgi', adouls: '/ma/loi/51-26', civil: '/ma/decret/2-22-04',
} as const;

export const law = (l: keyof typeof ROOT, a: number, t: T): Ref => ({
  path: `${ROOT[l]}/art_${a}`, law: t(`after.law.name.${l}`),
  // The DOC numbers its articles as «الفصل».
  label: t(l === 'doc' ? 'after.law.chapter' : 'after.law.article', { a }),
});
export const code = (c: Cite, t: T): Ref => ({ path: codePath(article(c)), label: citeLabel(c, t), law: t('after.law.name.family') });
