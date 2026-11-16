import { useTranslation } from 'react-i18next';
import i18n from '@/shared/locales/i18n';
import ar from './locales/ar.json';
import fr from './locales/fr.json';

/** The housing module's words (its tools: the rent increase and the deposit, a notice to leave, buying off plan, the
 *  housing aid), loaded with its code. */
export const NS = 'housing';
if (!i18n.hasResourceBundle('ar', NS)) {
  i18n.addResourceBundle('ar', NS, ar);
  i18n.addResourceBundle('fr', NS, fr);
}
export const useHousingT = () => useTranslation(NS);

/** An article's address as a chip's label, the law's own name for it kept in Arabic: «/ma/loi/67-12/art_34» →
 *  «القانون 67.12، المادة 34», «/ma/code/doc/art_618-3-quater» → «قانون الالتزامات والعقود، الفصل 618-3 المكرر ثلاث مرات». */
const NAMES: Record<string, [string, string]> = {
  '/ma/code/doc': ['قانون الالتزامات والعقود', 'الفصل'], '/ma/loi/67-12': ['القانون 67.12', 'المادة'],
  '/ma/loi/49-16': ['القانون 49.16', 'المادة'], '/ma/loi/7-03': ['القانون 07.03', 'المادة'],
  '/ma/loi/50-22': ['قانون المالية لسنة 2023', 'المادة'], '/ma/loi/55-23': ['قانون المالية لسنة 2024', 'المادة'],
  '/ma/loi/50-25': ['قانون المالية لسنة 2026', 'المادة'], '/ma/decret/2-23-350': ['المرسوم 2.23.350', 'المادة'],
};
export function articleLabel(path: string): string {
  const m = path.match(/^(\/ma\/.+)\/art_(.+)$/);
  if (!m) return path;
  const [, text, n] = m;
  const number = n.replace(/-quater$/, ' المكرر ثلاث مرات').replace(/-ter$/, ' المكرر مرتين').replace(/-bis$/, ' المكرر');
  const [name, word] = NAMES[text] ?? [`القانون ${text.split('/').pop()!.replace(/-/g, '.')}`, 'المادة'];
  return `${name}، ${word} ${number}`;
}
