import { useTranslation } from 'react-i18next';
import i18n from '@/shared/locales/i18n';
import ar from './locales/ar.json';
import fr from './locales/fr.json';

/** The road module's words (its tools: the fine, the points, the compensation), loaded with its code. */
export const NS = 'road';
if (!i18n.hasResourceBundle('ar', NS)) {
  i18n.addResourceBundle('ar', NS, ar);
  i18n.addResourceBundle('fr', NS, fr);
}
export const useRoadT = () => useTranslation(NS);

/** An article's address as a chip's label, the law's own name for it kept in Arabic: «/ma/loi/52-05/art_219» →
 *  «القانون 52.05، المادة 219», «/ma/dahir/1-84-177/art_5» → «الظهير 1.84.177، المادة 5». */
const NAMES: Record<string, string> = {
  '/ma/loi/52-05': 'مدونة السير 52.05', '/ma/dahir/1-84-177': 'الظهير 1.84.177', '/ma/loi/70-24': 'القانون 70.24',
  '/ma/decret/2-10-420': 'مرسوم قواعد السير 2.10.420', '/ma/loi/17-99': 'مدونة التأمينات 17.99',
};
export function articleLabel(path: string): string {
  const m = path.match(/^(\/ma\/.+)\/(art_(.+)|annex)$/);
  if (!m) return path;
  const [, text, , n] = m;
  const name = NAMES[text] ?? `${text.split('/')[2] === 'decret' ? 'المرسوم' : 'القانون'} ${text.split('/').pop()!.replace(/-/g, '.')}`;
  return n ? `${name}، المادة ${n.replace(/-bis$/, ' المكررة').replace(/^1-bis$/, '1 المكررة')}` : `${name}، الملحق`;
}
