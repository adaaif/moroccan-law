import { useTranslation } from 'react-i18next';
import i18n from '@/shared/locales/i18n';
import ar from './locales/ar.json';
import fr from './locales/fr.json';

/** The tax module's words (the tax review: the salary, pension, rent, the home's and plot's taxes, the vignette,
 *  a sale, a purchase, the auto-entrepreneur, paying late), loaded with its code. */
export const NS = 'tax';
if (!i18n.hasResourceBundle('ar', NS)) {
  i18n.addResourceBundle('ar', NS, ar);
  i18n.addResourceBundle('fr', NS, fr);
}
export const useTaxT = () => useTranslation(NS);

/** An article's address as a chip's label, the law's own name kept in Arabic: «/ma/code/cgi/art_73» → «المدونة العامة
 *  للضرائب، المادة 73», «/ma/loi/47-06/art_24» → «القانون 47.06، المادة 24». */
const NAMES: Record<string, string> = {
  '/ma/code/cgi': 'المدونة العامة للضرائب', '/ma/loi/47-06': 'القانون 47.06', '/ma/loi/50-25': 'قانون المالية 2026',
  '/ma/loi/60-24': 'قانون المالية 2025', '/ma/projet-loi/60-26': 'مشروع قانون المالية 2027', '/ma/decret/2-01-2723': 'المرسوم 2.01.2723', '/ma/decret/2-05-734': 'المرسوم 2.05.734',
};
const BIS: Record<string, string> = { bis: 'المكررة', ter: 'المكررة مرتين', quater: 'المكررة ثلاث مرات', quinquies: 'المكررة أربع مرات' };
export function articleLabel(path: string): string {
  const m = path.match(/^(\/ma\/[^/]+\/[^/]+)\/art_(\d+)(?:-(\w+))?$/);
  if (!m) return path;
  const [, text, n, bis] = m;
  const kind = text.split('/')[2];
  const name = NAMES[text] ?? `${kind === 'decret' ? 'المرسوم' : 'القانون'} ${text.split('/').pop()!.replace(/-/g, '.')}`;
  return `${name}، المادة ${n}${bis ? ` ${BIS[bis] ?? bis}` : ''}`;
}

/** Amounts as the reader's language writes them, Western digits; whole dirhams unless `cents`. */
export function useMoney() {
  const { i18n } = useTaxT();
  const locale = i18n.language === 'fr' ? 'fr-MA' : 'ar-MA';
  const whole = new Intl.NumberFormat(locale, { maximumFractionDigits: 0 });
  const cents = new Intl.NumberFormat(locale, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  return { n: (x: number) => whole.format(x), c: (x: number) => cents.format(x) };
}

/** The day a year's law is asked about: today in the current year, mid-year for another. */
export const yearDay = (year: string, today: string) => (today.startsWith(year) ? today : `${year}-06-30`);
