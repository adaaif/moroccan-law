import i18n from '@/shared/locales/i18n';
import { NS } from '../api';
import ar from './locales/ar.json';
import fr from './locales/fr.json';

/** The words of a bill's pages (its changes, its vote, what was said and what people say): they load with these pages'
 *  code, never in the first load, merged into the kit's own namespace so `t('changes.today')` reads as before. */
if (!i18n.exists('vote.for', { ns: NS, lng: 'ar' })) {
  i18n.addResourceBundle('ar', NS, ar, true, false);
  i18n.addResourceBundle('fr', NS, fr, true, false);
}
