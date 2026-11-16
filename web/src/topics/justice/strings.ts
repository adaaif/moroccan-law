import { useTranslation } from 'react-i18next';
import i18n from '@/shared/locales/i18n';
import ar from './locales/ar.json';
import fr from './locales/fr.json';

/** The justice module's words (the justice review: the deadlines, the custody clock, the courts, the alternative
 *  sentence), loaded with its code. */
export const NS = 'justice';
if (!i18n.hasResourceBundle('ar', NS)) {
  i18n.addResourceBundle('ar', NS, ar);
  i18n.addResourceBundle('fr', NS, fr);
}
export const useJusticeT = () => useTranslation(NS);

/** An article's address as a chip's label, the law's own name kept in Arabic: «/ma/loi/58-25/art_204» → «قانون المسطرة
 *  المدنية، المادة 204», «/ma/dahir/1-59-413/art_35-6» → «القانون الجنائي، الفصل 35-6». */
const NAMES: Record<string, [string, string]> = {
  '/ma/loi/22-01': ['قانون المسطرة الجنائية', 'المادة'], '/ma/loi/58-25': ['قانون المسطرة المدنية', 'المادة'],
  '/ma/dahir/1-59-413': ['القانون الجنائي', 'الفصل'], '/ma/loi/66-23': ['قانون المحاماة', 'المادة'],
  '/ma/decret-loi/514-65': ['مرسوم المساعدة القضائية', 'الفصل'], '/ma/loi/10-23': ['قانون المؤسسات السجنية', 'المادة'],
};
const KIND: Record<string, string> = { loi: 'القانون', decret: 'المرسوم', arrete: 'القرار', dahir: 'الظهير' };
export function articleLabel(path: string): string {
  const m = path.match(/^(\/ma\/[^/]+\/[^/]+)\/art_([\w-]+)$/);
  if (!m) return path;
  const [, text, n] = m;
  const [name, word] = NAMES[text] ?? [`${KIND[text.split('/')[2]] ?? 'النص'} ${text.split('/').pop()!.replace(/-/g, '.')}`, 'المادة'];
  return `${name}، ${word} ${n}`;
}

/** Dirhams as the reader's language writes them: «1.250 درهم», «1 250 DH». */
export function useMoney() {
  const { i18n: i } = useJusticeT();
  const fr = i.language === 'fr';
  return (x: number) => {
    const s = Math.round(x).toLocaleString('de-DE');
    return fr ? `${s.replace(/\./g, ' ')} DH` : `${s} درهم`;
  };
}

/** A number of hours as the reader's language groups it: «3.600», «3 600». */
export const grouped = (n: number, lang: string) => {
  const s = Math.round(n).toLocaleString('de-DE');
  return lang === 'fr' ? s.replace(/\./g, ' ') : s;
};

/** The registry stamp's foot in the reader's language (PX29 of the where-it-trips review): on a French page the drawn stamp
 *  said «قانون المسطرة المدنية، المادة 204». The chips keep the law's own Arabic name. */
const FRENCH: Record<string, string> = {
  '/ma/loi/22-01': 'Code de procédure pénale', '/ma/loi/58-25': 'Code de procédure civile', '/ma/dahir/1-59-413': 'Code pénal',
  '/ma/loi/66-23': 'Loi sur la profession d’avocat', '/ma/decret-loi/514-65': 'Décret royal sur l’assistance judiciaire',
  '/ma/loi/10-23': 'Loi sur les établissements pénitentiaires',
};
export function stampLabel(path: string, lang: string): string {
  const m = path.match(/^(\/ma\/[^/]+\/[^/]+)\/art_([\w-]+)$/);
  return lang === 'fr' && m && FRENCH[m[1]] ? `${FRENCH[m[1]]}, article ${m[2]}` : articleLabel(path);
}
