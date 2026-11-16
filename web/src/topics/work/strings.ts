import { useTranslation } from 'react-i18next';
import i18n from '@/shared/locales/i18n';
import ar from './locales/ar.json';
import fr from './locales/fr.json';

/** The work module's words (its tools: what is owed at the end of a contract, pay, the dates, the CNSS), loaded with
 *  its code. */
export const NS = 'work';
if (!i18n.hasResourceBundle('ar', NS)) {
  i18n.addResourceBundle('ar', NS, ar);
  i18n.addResourceBundle('fr', NS, fr);
}
export const useWorkT = () => useTranslation(NS);

/** An article's address as a chip's label, the law's own name for it kept in Arabic: «/ma/loi/65-99/art_53» →
 *  «مدونة الشغل، المادة 53». */
const NAMES: Record<string, string> = {
  '/ma/loi/65-99': 'مدونة الشغل', '/ma/dahir/1-72-184': 'ظهير الضمان الاجتماعي', '/ma/loi/58-25': 'القانون 58.25',
  '/ma/loi/18-12': 'القانون 18.12', '/ma/loi/19-12': 'القانون 19.12', '/ma/code/cgi': 'المدونة العامة للضرائب',
};
export function articleLabel(path: string): string {
  const m = path.match(/^(\/ma\/[^/]+\/[^/]+)\/art_(.+)$/);
  if (!m) return path;
  const [, text, n] = m;
  const number = n.replace('-bis', ' المكرر').replace('-ter', ' المكرر مرتين').replace('-quater', ' المكرر ثلاث مرات');
  const word = text.startsWith('/ma/dahir') ? 'الفصل' : 'المادة';
  if (NAMES[text]) return `${NAMES[text]}، ${word} ${number}`;
  const [, kind, num] = text.split('/').slice(1);
  return `${kind === 'decret' ? 'المرسوم' : 'القانون'} ${num.replace(/-/g, '.')}، ${word} ${number}`;
}
