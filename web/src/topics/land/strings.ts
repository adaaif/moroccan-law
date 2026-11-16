import { useTranslation } from 'react-i18next';
import i18n from '@/shared/locales/i18n';
import ar from './locales/ar.json';
import fr from './locales/fr.json';

/** The land module's words (the land review: the clock, the permit's road, before you buy, the finder), loaded with
 *  its code. */
export const NS = 'land';
if (!i18n.hasResourceBundle('ar', NS)) {
  i18n.addResourceBundle('ar', NS, ar);
  i18n.addResourceBundle('fr', NS, fr);
}
export const useLandT = () => useTranslation(NS);

/** An article's address as a chip's label, the law's own name kept in Arabic: «/ma/loi/39-08/art_304» → «مدونة الحقوق
 *  العينية، المادة 304», «/ma/code/land-registration/art_27» → «ظهير التحفيظ العقاري، الفصل 27». */
const NAMES: Record<string, string> = {
  '/ma/loi/39-08': 'مدونة الحقوق العينية', '/ma/code/land-registration': 'ظهير التحفيظ العقاري', '/ma/loi/12-90': 'قانون التعمير',
  '/ma/loi/25-90': 'القانون 25.90', '/ma/loi/7-81': 'قانون نزع الملكية', '/ma/loi/62-17': 'القانون 62.17',
  '/ma/decret/2-18-577': 'المرسوم 2.18.577', '/ma/loi/41-25': 'القانون 41.25',
};
const CHAPTERS = new Set(['/ma/code/land-registration', '/ma/loi/7-81']);
export function articleLabel(path: string): string {
  const m = path.match(/^(\/ma\/[^/]+\/[^/]+)\/art_(.+)$/);
  if (!m) return path;
  const [, text, n] = m;
  const kind = text.split('/')[2];
  const name = NAMES[text] ?? `${kind === 'decret' ? 'المرسوم' : 'القانون'} ${text.split('/').pop()!.replace(/-/g, '.')}`;
  return `${name}، ${CHAPTERS.has(text) ? 'الفصل' : 'المادة'} ${n.replace(/-bis$/, ' المكرر')}`;
}
