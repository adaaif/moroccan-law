import { useTranslation } from 'react-i18next';
import i18n from '@/shared/locales/i18n';
import ar from './locales/ar.json';
import fr from './locales/fr.json';

/** The consumer module's words (its tools: returning, the guarantee, a late delivery, credit, where to complain, the
 *  clauses, sugar's price, the letters), loaded with its code. */
export const NS = 'consumer';
if (!i18n.hasResourceBundle('ar', NS)) {
  i18n.addResourceBundle('ar', NS, ar);
  i18n.addResourceBundle('fr', NS, fr);
}
export const useConsumerT = () => useTranslation(NS);

/** An article's address as a chip's label, the law's own name kept in Arabic: «/ma/loi/31-08/art_36» → «القانون
 *  31.08، المادة 36», «/ma/code/doc/art_556» → «قانون الالتزامات والعقود، الفصل 556». */
const NAMES: Record<string, string> = {
  '/ma/loi/31-08': 'القانون 31.08', '/ma/code/doc': 'قانون الالتزامات والعقود', '/ma/decret/2-12-503': 'المرسوم 2.12.503',
  '/ma/loi/104-12': 'القانون 104.12', '/ma/decret/2-14-652': 'المرسوم 2.14.652', '/ma/loi/24-09': 'القانون 24.09',
  '/ma/loi/28-07': 'القانون 28.07', '/ma/loi/13-83': 'القانون 13.83',
};
export function articleLabel(path: string): string {
  const m = path.match(/^(\/ma\/[^/]+\/[^/]+)\/(?:art_(.+)|annex)$/);
  if (!m) return path;
  const [, text, n] = m;
  const kind = text.split('/')[2];
  const number = text.split('/').pop()!.replace(/-/g, '.');
  const name = NAMES[text] ?? `${kind === 'arrete' ? 'القرار' : kind === 'decret' ? 'المرسوم' : 'القانون'} ${number}`;
  const word = kind === 'code' ? 'الفصل' : 'المادة';
  return n ? `${name}، ${word} ${n.replace(/-bis$/, ' المكررة')}` : `${name}، الملحق`;
}
