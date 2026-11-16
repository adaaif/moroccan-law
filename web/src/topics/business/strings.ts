import { useTranslation } from 'react-i18next';
import i18n from '@/shared/locales/i18n';
import ar from './locales/ar.json';
import fr from './locales/fr.json';

/** The business module's words (the business review: the forms, the cheque, the late invoice, the company's year),
 *  loaded with its code. */
export const NS = 'business';
if (!i18n.hasResourceBundle('ar', NS)) {
  i18n.addResourceBundle('ar', NS, ar);
  i18n.addResourceBundle('fr', NS, fr);
}
export const useBusinessT = () => useTranslation(NS);

/** An article's address as a chip's label, the law's own name kept in Arabic: «/ma/loi/15-95/art_2-78» → «مدونة
 *  التجارة، المادة 2-78», «/ma/code/cgi/art_42-ter» → «المدونة العامة للضرائب، المادة 42 المكررة مرتين». */
const NAMES: Record<string, string> = {
  '/ma/code/cgi': 'المدونة العامة للضرائب', '/ma/loi/15-95': 'مدونة التجارة', '/ma/loi/5-96': 'القانون 5.96',
  '/ma/loi/114-13': 'القانون 114.13', '/ma/loi/112-12': 'القانون 112.12', '/ma/loi/3-22': 'القانون الإطار 03.22',
};
const KIND: Record<string, string> = { loi: 'القانون', decret: 'المرسوم', arrete: 'القرار', dahir: 'الظهير' };
const BIS: Record<string, string> = { bis: ' المكررة', ter: ' المكررة مرتين', quater: ' المكررة ثلاث مرات' };
export function articleLabel(path: string): string {
  const m = path.match(/^(\/ma\/[^/]+\/[^/]+)\/(?:art_(\d+)(?:-(\w+))?|(annex))$/);
  if (!m) return path;
  const [, text, n, bis, annex] = m;
  const kind = text.split('/')[2];
  const name = NAMES[text] ?? `${KIND[kind] ?? 'النص'} ${text.split('/').pop()!.replace(/-/g, '.')}`;
  if (annex) return `${name}، الملحق`;
  // The commerce code numbers the articles it gained as «2-78»: the number after the dash, as printed.
  const tail = !bis ? '' : /^\d+$/.test(bis) ? `-${bis}` : BIS[bis] ?? ` ${bis}`;
  return `${name}، المادة ${n}${tail}`;
}

/** Dirhams as the reader's language writes them: «1.250» in Arabic, «1 250» in French. */
export function useMoney() {
  const { i18n: i } = useBusinessT();
  const fr = i.language === 'fr';
  return (x: number) => {
    const s = x.toLocaleString('de-DE', { maximumFractionDigits: 2 });
    return fr ? `${s.replace(/\./g, ' ')} DH` : `${s} درهم`;
  };
}
