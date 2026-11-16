import { useTranslation } from 'react-i18next';
import i18n from '@/shared/locales/i18n';
import ar from './locales/ar.json';
import fr from './locales/fr.json';

/** The digital module's words (the digital review: the offences, the information request, the data letter,
 *  copyright's term), loaded with its code. */
export const NS = 'digital';
if (!i18n.hasResourceBundle('ar', NS)) {
  i18n.addResourceBundle('ar', NS, ar);
  i18n.addResourceBundle('fr', NS, fr);
}
export const useDigitalT = () => useTranslation(NS);

/** An article's address as a chip's label, the law's own name kept in Arabic. */
const NAMES: Record<string, [string, string]> = {
  '/ma/dahir/1-59-413': ['القانون الجنائي', 'الفصل'], '/ma/loi/88-13': ['قانون الصحافة والنشر', 'المادة'],
  '/ma/loi/9-08': ['القانون 09.08', 'المادة'], '/ma/loi/31-13': ['القانون 31.13', 'المادة'], '/ma/loi/2-00': ['قانون حقوق المؤلف', 'المادة'],
  '/ma/loi/22-01': ['قانون المسطرة الجنائية', 'المادة'], '/ma/loi/43-20': ['القانون 43.20', 'المادة'], '/ma/code/doc': ['قانون الالتزامات والعقود', 'الفصل'],
};
export function articleLabel(path: string): string {
  const m = path.match(/^(\/ma\/[^/]+\/[^/]+)\/art_([\w-]+)$/);
  if (!m) return path;
  const [name, word] = NAMES[m[1]] ?? [`النص ${m[1].split('/').pop()!.replace(/-/g, '.')}`, 'المادة'];
  // The number isolated left to right, or an Arabic line shows «447-1» as «1-447».
  return `${name}، ${word} \u2066${m[2]}\u2069`;
}

/** Dirhams as the reader's language writes them: «2.000 درهم», «2 000 DH». */
export function useMoney() {
  const { i18n: i } = useDigitalT();
  const fr = i.language === 'fr';
  return (x: number) => {
    const s = Math.round(x).toLocaleString('de-DE');
    return fr ? `${s.replace(/\./g, ' ')} DH` : `${s} درهم`;
  };
}
