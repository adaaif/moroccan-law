import { createContext, useContext, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import i18n from '@/shared/locales/i18n';
import type { Cite } from './engine';
import arKin from './locales/ar/kin.json';
import arShell from './locales/ar/shell.json';
import arAsk from './locales/ar/ask.json';
import arAnswer from './locales/ar/answer.json';
import arAfter from './locales/ar/after.json';
import arOffice from './locales/ar/office.json';
import frKin from './locales/fr/kin.json';
import frShell from './locales/fr/shell.json';
import frAsk from './locales/fr/ask.json';
import frAnswer from './locales/fr/answer.json';
import frAfter from './locales/fr/after.json';
import frOffice from './locales/fr/office.json';

/** The calculator's words, loaded with its code: the relatives and the reasons (`heir`, `heirs`, `why`, `out`,
 *  `named`), then a part for each of the page's areas (`shell`, `ask`, `answer`, `after`, `office`), each in a file of
 *  its own under locales/. */
export const NS = 'inheritance';
if (!i18n.hasResourceBundle('ar', NS)) {
  i18n.addResourceBundle('ar', NS, { ...arKin, shell: arShell, ask: arAsk, answer: arAnswer, after: arAfter, office: arOffice });
  i18n.addResourceBundle('fr', NS, { ...frKin, shell: frShell, ask: frAsk, answer: frAnswer, after: frAfter, office: frOffice });
}
/** Who died, a man or a woman: the frame sets it, and a part that speaks of an heir who died since sets that heir's.
 *  The relatives' names agree with it («خوه», «خوها»). */
export const DeceasedContext = createContext<'m' | 'f'>('m');

/** The calculator's words. A relative's name (`heir.`, `heirs.`, `each.`) is read in the form that agrees with who
 *  died (`heirF.` and the like, for a woman), so no screen has to ask. `tOf` gives the words for another dead person:
 *  an heir who died since has a family of their own («خوها»). */
export const useT = () => {
  const r = useTranslation(NS);
  const base = r.t;
  const sex = useContext(DeceasedContext);
  const { t, tOf } = useMemo(() => {
    const hers = ((key: string, options?: Record<string, unknown>) => base(key.replace(/^(heir|heirs|each)\./, '$1F.'), options)) as unknown as typeof base;
    const of = (s: 'm' | 'f') => (s === 'f' ? hers : base);
    return { t: of(sex), tOf: of };
  }, [base, sex]);
  return { ...r, t, tOf };
};

/** An article of the family code on the site. The law's words stay Arabic; the chip that names it speaks the page's
 *  language (IR21). */
export const codePath = (article: number) => `/ma/loi/70-03/art_${article}`;
export const citeLabel = (c: Cite, t: ReturnType<typeof useT>['t'], old = false): string =>
  (typeof c === 'number' ? t(old ? 'shell.article1958' : 'shell.article', { a: c }) : t(old ? 'shell.paragraph1958' : 'shell.paragraph', { a: c[0], p: c[1] }));
/** The 1958 book's articles are not cut one by one in the corpus yet: a citation of it opens the Bulletin that
 *  printed it (issue 2371 of 4 April 1958, pages 819 to 823). */
export const OLD_BOOK = '/bo/ar/2371';
