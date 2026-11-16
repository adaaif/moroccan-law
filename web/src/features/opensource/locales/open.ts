import i18n from '@/shared/locales/i18n';
import ar from './open.ar.json';
import fr from './open.fr.json';

/** The words of /open-source, in both languages: they load with the page, never with the first load. Use them as
 *  useTranslation('open'). */
export const NS = 'open';
if (!i18n.hasResourceBundle('ar', NS)) {
  i18n.addResourceBundle('ar', NS, ar);
  i18n.addResourceBundle('fr', NS, fr);
}
