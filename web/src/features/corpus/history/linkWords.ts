import i18n from '@/shared/locales/i18n';
import type { LinkText } from '../corpus.api';
import ar from './links.ar.json';
import fr from './links.fr.json';

// The links' words come with the links' code, a moment after the text's words (the first-load budget).
if (!i18n.exists('links.states.read', { lng: 'ar' })) {
  i18n.addResourceBundle('ar', 'translation', { links: ar }, true, false);
  i18n.addResourceBundle('fr', 'translation', { links: fr }, true, false);
}

type T = (k: string, o?: Record<string, unknown>) => string;

/** «القانون رقم 64.23»: a linked text by its kind and number, its title when it has no number. */
export function textName(x: LinkText, t: T): string {
  const kind = t(`corpus.types.${x.type}`, { defaultValue: '' });
  return x.number ? t('links.named', { kind, number: x.number }).trim() : x.title;
}

export function issueLabel(n: number | null, bis: boolean, t: (k: string) => string): string {
  return n ? `${n}${bis ? ` ${t('corpus.suffix.bis')}` : ''}` : '';
}
