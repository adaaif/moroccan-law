import i18n from './i18n';
import ar from './pages.ar.json';
import fr from './pages.fr.json';

/** The words of the pages that load apart (topics, library, «أنا», explanations: the for-everyone review), in both
 *  languages, with their code: the first load keeps only the home's and a text's. Use them as t('pages:topics.title'). */
if (!i18n.hasResourceBundle('ar', 'pages')) {
  i18n.addResourceBundle('ar', 'pages', ar);
  i18n.addResourceBundle('fr', 'pages', fr);
}
