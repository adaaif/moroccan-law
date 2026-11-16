import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import ar from './ar.json';

export type Language = 'ar' | 'fr';

const STORAGE_KEY = 'law.lang';

function storedLanguage(): Language {
  try {
    return localStorage.getItem(STORAGE_KEY) === 'fr' ? 'fr' : 'ar';
  } catch {
    return 'ar';
  }
}

/** French's words load when a reader first chooses French (row 17): most readers never need them. Known by their own
 *  flag, merged into what is there (PX9 of the where-it-trips review): the history's link words add a French bundle of
 *  their own when an Arabic law opens, and «is there a French bundle?» then said yes, so a reader who switched to French
 *  read Arabic labels until a reload. */
let french = false;
export async function loadLanguage(lang: Language): Promise<void> {
  if (lang === 'fr' && !french) {
    i18n.addResourceBundle('fr', 'translation', (await import('./fr.json')).default, true, false);
    french = true;
  }
}

/** Arabic reads right to left; the page follows the language. */
export async function applyLanguage(lang: Language): Promise<void> {
  await loadLanguage(lang);
  void i18n.changeLanguage(lang);
  if (typeof document === 'undefined') return; // the prerender, in Node
  document.documentElement.lang = lang;
  document.documentElement.dir = lang === 'ar' ? 'rtl' : 'ltr';
  try {
    localStorage.setItem(STORAGE_KEY, lang);
  } catch {
    // Private mode: the choice lasts this visit only.
  }
}

export function currentLanguage(): Language {
  return i18n.language === 'fr' ? 'fr' : 'ar';
}

// A percent keeps its sign to the right of its number, as Moroccans read it (1 Nov 2026, on every page): after an
// Arabic letter the digits turn Arabic-numbered and «٪» fell to their left («٪39»); an LTR isolate around number and
// sign keeps «39٪».
export const pct = (s: string) => s.replace(/(\d+(?:[.,]\d+)?\s?[%٪])/g, '\u2066$1\u2069');

// In French the isolate changes nothing: the line already runs left to right.
void i18n.use(initReactI18next).use({ type: 'postProcessor', name: 'pct', process: pct }).init({
  postProcess: ['pct'],
  resources: { ar: { translation: ar } },
  partialBundledLanguages: true,
  lng: 'ar',
  fallbackLng: 'ar',
  // Words of pages that load apart, kept under their own namespace and found from the default one (the finance law's,
  // the citation checker's).
  fallbackNS: ['budget', 'check'],
  interpolation: { escapeValue: false },
  showSupportNotice: false,
});

// «{{count, n}}»: a count as the Bulletin prints it, «828.303», «828 303» in French (PX30 of the where-it-trips review).
i18n.services.formatter?.add('n', (value: number, lng?: string) => new Intl.NumberFormat(lng === 'fr' ? 'fr-MA' : 'ar-MA').format(value));

/** Resolves once the stored language's words are in: the app renders after it, so a French reader never sees
 *  the Arabic first. */
export const languageReady: Promise<void> = applyLanguage(storedLanguage());

export default i18n;
