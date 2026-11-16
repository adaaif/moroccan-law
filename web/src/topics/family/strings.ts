import { useTranslation } from 'react-i18next';
import i18n from '@/shared/locales/i18n';
import ar from './locales/ar.json';
import fr from './locales/fr.json';

/** The family module's words (its tools: heirs, the reason for each share, dates, amounts), loaded with its code. */
export const NS = 'family';
if (!i18n.hasResourceBundle('ar', NS)) {
  i18n.addResourceBundle('ar', NS, ar);
  i18n.addResourceBundle('fr', NS, fr);
}
export const useFamilyT = () => useTranslation(NS);

/** An article of the family code as a chip's address and label: the law's own words stay Arabic. */
export const codeArticle = (n: number) => ({ path: `/ma/loi/70-03/art_${n}`, label: `المادة ${n}` });
