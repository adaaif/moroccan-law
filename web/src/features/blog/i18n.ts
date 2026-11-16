import i18n from '@/shared/locales/i18n';
import ar from './locales/ar.json';
import fr from './locales/fr.json';

/** The blog's words, in both languages, loaded with its pages: t('blog:…'). */
if (!i18n.hasResourceBundle('ar', 'blog')) {
  i18n.addResourceBundle('ar', 'blog', ar);
  i18n.addResourceBundle('fr', 'blog', fr);
}
