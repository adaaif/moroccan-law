import i18n from '@/shared/locales/i18n';
import ar from './mine.ar.json';
import fr from './mine.fr.json';

/** The words of «وصولي» (/data/access) and of what a request sent says, in both languages: they load with that code,
 *  never with the first load. Use them as t('mine:title'). */
export const NS = 'mine';
if (!i18n.hasResourceBundle('ar', NS)) {
  i18n.addResourceBundle('ar', NS, ar);
  i18n.addResourceBundle('fr', NS, fr);
}
