import i18n from '@/shared/locales/i18n';
import ar from './words.ar.json';
import fr from './words.fr.json';

/** The finance law's words, loaded with its pages (P4 of the polish review made room in the first load): the
 *  `budget` namespace, which i18n falls back to, so t('budget.title') reads as before. */
if (!i18n.hasResourceBundle('ar', 'budget')) {
  i18n.addResourceBundle('ar', 'budget', ar);
  i18n.addResourceBundle('fr', 'budget', fr);
}
