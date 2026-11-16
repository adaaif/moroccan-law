import type { TFunction } from 'i18next';
import { useTranslation } from 'react-i18next';
import i18n from '@/shared/locales/i18n';
import { topicColour } from '@/features/topics/colour';
import { ApiError, NetworkError } from '@/shared/services/api';
import ar from './locales/ar.json';
import fr from './locales/fr.json';

/** The discussion's words load with its code, in both languages (a few kilobytes): the first visit to a text never
 *  pays for them. */
export const NS = 'discussion';
if (!i18n.hasResourceBundle('ar', NS)) {
  i18n.addResourceBundle('ar', NS, ar);
  i18n.addResourceBundle('fr', NS, fr);
}

export function useT() {
  return useTranslation(NS);
}

/** The sentence for a refusal: the field's code from the discussion's words, then the generic ones. */
export function errorText(t: TFunction, error: unknown, field?: string): string | undefined {
  if (!error) return undefined;
  if (error instanceof NetworkError) return t('errors.network');
  if (!(error instanceof ApiError)) return t('errors.unknown');
  const found = field ? error.errors.find((e) => e.field === field) : error.errors[0];
  if (found) return t(`errors.${found.field}.${found.code}`, { defaultValue: t('errors.unknown'), count: found.minutes });
  if (error.status === 429) return t('errors.tooMany');
  return field ? undefined : t('errors.unknown');
}

const UNITS: [Intl.RelativeTimeFormatUnit, number][] = [
  ['year', 31_536_000], ['month', 2_592_000], ['week', 604_800], ['day', 86_400], ['hour', 3_600], ['minute', 60],
];

/** «قبل يومين», «il y a 2 jours». Western digits, as the site prints them. */
export function ago(iso: string, lang: string, now = Date.now()): string {
  const seconds = Math.round((new Date(iso).getTime() - now) / 1000);
  const format = new Intl.RelativeTimeFormat(lang === 'fr' ? 'fr-MA' : 'ar-MA', { numeric: 'auto' });
  for (const [unit, size] of UNITS) {
    if (Math.abs(seconds) >= size) return format.format(Math.round(seconds / size), unit);
  }
  return i18n.t('time.now', { ns: NS });
}

export function shortDate(iso: string | null, lang: string): string {
  if (!iso) return '';
  return new Intl.DateTimeFormat(lang === 'fr' ? 'fr-MA' : 'ar-MA', { dateStyle: 'long' }).format(new Date(iso));
}

/** m:ss, digits only: the player and the recorder read left to right. */
export function clock(ms: number): string {
  const total = Math.max(0, Math.floor(ms / 1000));
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, '0')}`;
}

/** How long reviews take, in words: minutes under an hour, hours above. */
export function reviewWait(t: TFunction, hours: number, keys: [string, string] = ['reviewTimeMinutes', 'reviewTime']): string {
  return hours < 1 ? t(keys[0], { minutes: Math.max(1, Math.round(hours * 60)), m: Math.max(1, Math.round(hours * 60)) })
    : t(keys[1], { hours: Math.round(hours), h: Math.round(hours) });
}

/** The rule's number on the rules page (1 to 7). */
export const RULE_ORDER = ['privacy', 'respect', 'soliciting', 'lawful', 'decent', 'on_topic', 'honest'];
export const ruleNo = (rule: string | null | undefined) => RULE_ORDER.indexOf(rule ?? '') + 1;

/** An address said by the name people know (P6 of the polish review): a law's everyday name, or a topic's; French when
 *  the API has it. */
export function labelName(label: { text: string; name?: { ar: string; fr: string | null } | null; place?: string },
                          lang: string): string {
  if (label.place) return (lang === 'fr' && label.name?.fr) || label.name?.ar || '';
  return (lang === 'fr' && label.name?.fr) || label.text;
}

/** A topic's name in the reader's language. */
export const placeName = (name: { ar: string; fr: string | null } | null | undefined, lang: string) =>
  (lang === 'fr' && name?.fr) || name?.ar || '';

/** The colour of a person's topic: the place they write in most; none (the conversation's teal) before they write. */
export const homeColour = (places?: { slug: string }[]) => (places?.length ? topicColour(places[0].slug) : undefined);

/** A place's topic from its address (/talk/family) or a label's slug (family); the general place is «general». */
export const slugOf = (place: string) => (place.includes('/') ? place.split('/')[2] : place) || 'general';

/** Where a contribution is read: a post's own page (/talk/family/12), or an article's page of before. */
export const pageOf = (path: string) => (path.startsWith('/talk/') || path.startsWith('/explain/') ? path : `/discussion${path}`);
