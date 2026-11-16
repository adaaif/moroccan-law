import { useTranslation } from 'react-i18next';
import i18n from '@/shared/locales/i18n';
import ar from './locales/ar.json';
import fr from './locales/fr.json';

/** The health module's words (the health review: the refund, the feuille de soins' clock, the long-illness
 *  finder), loaded with its code. */
export const NS = 'health';
if (!i18n.hasResourceBundle('ar', NS)) {
  i18n.addResourceBundle('ar', NS, ar);
  i18n.addResourceBundle('fr', NS, fr);
}
export const useHealthT = () => useTranslation(NS);

/** An article's address as a chip's label, the law's own name kept in Arabic: «/ma/decret/2-05-737/art_2» → «المرسوم
 *  2.05.737، المادة 2», «/ma/loi/65-00/art_120-bis» → «القانون 65.00، المادة 120 المكررة». */
const NAMES: Record<string, string> = { '/ma/loi/65-99': 'مدونة الشغل', '/ma/code/doc': 'قانون الالتزامات والعقود', '/ma/dahir/1-59-413': 'القانون الجنائي' };
const KIND: Record<string, string> = { loi: 'القانون', decret: 'المرسوم', arrete: 'القرار', dahir: 'الظهير' };
export function articleLabel(path: string): string {
  const m = path.match(/^(\/ma\/[^/]+\/[^/]+)\/(?:art_(\d+)(?:-(\w+))?|(annex))$/);
  if (!m) return path;
  const [, text, n, bis, annex] = m;
  const kind = text.split('/')[2];
  const name = NAMES[text] ?? `${KIND[kind] ?? 'النص'} ${text.split('/').pop()!.replace(/-/g, '.')}`;
  return annex ? `${name}، الملحق` : `${name}، المادة ${n}${bis === 'bis' ? ' المكررة' : bis ? ` ${bis}` : ''}`;
}

/** Amounts as the reader's language writes them: «1.250» in Arabic (the Bulletin's), «1 250» in French; cents shown
 *  only when there are any. */
export function useMoney() {
  const { i18n } = useHealthT();
  const fr = i18n.language === 'fr';
  return (x: number) => {
    const whole = Math.round(x * 100) % 100 === 0;
    const s = x.toLocaleString('de-DE', { minimumFractionDigits: whole ? 0 : 2, maximumFractionDigits: 2 });
    return fr ? s.replace(/\./g, ' ') : s;
  };
}
