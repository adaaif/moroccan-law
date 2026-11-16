import i18n from '@/shared/locales/i18n';
import ar from './checkWords.ar.json';
import fr from './checkWords.fr.json';

/** The citation checker's words, loaded with its page: the `check` namespace, which i18n falls back to. */
if (!i18n.hasResourceBundle('ar', 'check')) {
  i18n.addResourceBundle('ar', 'check', ar);
  i18n.addResourceBundle('fr', 'check', fr);
}
