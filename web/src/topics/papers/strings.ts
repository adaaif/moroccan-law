import { useTranslation } from 'react-i18next';
import i18n from '@/shared/locales/i18n';
import ar from './locales/ar.json';
import fr from './locales/fr.json';

/** The papers module's words (the papers review: the card, the civil-status clock, the administration's clock, the
 *  first name, the rehabilitation), loaded with its code. */
export const NS = 'papers';
if (!i18n.hasResourceBundle('ar', NS)) {
  i18n.addResourceBundle('ar', NS, ar);
  i18n.addResourceBundle('fr', NS, fr);
}
export const usePapersT = () => useTranslation(NS);

/** An article's address as a chip's label, the law's own name kept in Arabic: «/ma/loi/4-20/art_13» → «القانون 04.20،
 *  المادة 13», «/ma/code/cgi/art_252» → «المدونة العامة للضرائب، المادة 252». */
const NAMES: Record<string, string> = {
  '/ma/code/cgi': 'المدونة العامة للضرائب', '/ma/loi/22-01': 'المسطرة الجنائية', '/ma/dahir/1-58-250': 'قانون الجنسية',
  '/ma/loi/4-20': 'القانون 04.20', '/ma/loi/9-08': 'القانون 09.08', '/ma/loi/2-03': 'القانون 02.03', '/ma/loi/8-23': 'القانون 08.23',
};
const KIND: Record<string, string> = { loi: 'القانون', decret: 'المرسوم', arrete: 'القرار', dahir: 'الظهير' };
export function articleLabel(path: string): string {
  const m = path.match(/^(\/ma\/[^/]+\/[^/]+)\/(?:art_(\d+)(?:-(\w+))?|(annex))$/);
  if (!m) return path;
  const [, text, n, bis, annex] = m;
  const kind = text.split('/')[2];
  const name = NAMES[text] ?? `${KIND[kind] ?? 'النص'} ${text.split('/').pop()!.replace(/-/g, '.')}`;
  return annex ? `${name}، الملحق` : `${name}، المادة ${n}${bis === 'bis' ? ' المكررة' : bis ? ` ${bis}` : ''}`;
}

/** Dirhams as the reader's language writes them: «1.250» in Arabic, «1 250» in French. */
export function useMoney() {
  const { i18n: i } = usePapersT();
  const fr = i.language === 'fr';
  return (x: number) => {
    const s = x.toLocaleString('de-DE');
    return fr ? `${s.replace(/\./g, ' ')} DH` : `${s} درهم`;
  };
}
