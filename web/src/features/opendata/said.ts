import { useTranslation } from 'react-i18next';
import { longDate } from '@/features/corpus/format';
import { ApiError, NetworkError, type FieldError } from '@/shared/services/api';
import { dayIn } from '@/shared/services/today';
import '@/shared/locales/pages';
import type { AccessRow, RequestRow } from './access';

/** A day or a moment, said as a date of Morocco's calendar. */
export const dateOf = (iso: string, lang: string) => longDate(iso.length > 10 ? dayIn(new Date(iso)) : iso, lang);

/** A refusal's sentence, from its field and code, with the day it carries when it carries one (`request.too_soon`'s
 *  `on`). The words of «وصولي» (`mine:errors.<field>.<code>`, where they are loaded) come before the shared ones
 *  (`pages:errors.<field>.<code>`). */
export function useRefusals() {
  const { t, i18n } = useTranslation();
  const sentence = (e: FieldError & { on?: string }) =>
    t([`mine:errors.${e.field}.${e.code}`, `pages:errors.${e.field}.${e.code}`],
      { defaultValue: t('pages:errors.unknown'), on: e.on ? dateOf(e.on, i18n.language) : '' });
  return {
    /** The sentence beside a field, when the server refused that field. */
    field: (error: unknown, name: string) => {
      const found = error instanceof ApiError ? error.errors.find((e) => e.field === name) : undefined;
      return found ? sentence(found) : undefined;
    },
    /** The sentences that belong to no field of the form; nothing when the fields already say what is wrong. */
    form: (error: unknown, fields: string[] = []): string[] => {
      if (!error) return [];
      if (error instanceof NetworkError) return [t('pages:auth.network')];
      if (!(error instanceof ApiError)) return [t('pages:errors.unknown')];
      const rest = error.errors.filter((e) => !fields.includes(e.field));
      if (rest.length) return rest.map(sentence);
      if (error.errors.length) return [];
      return [error.status === 429 ? t('pages:auth.tooMany') : t('pages:errors.unknown')];
    },
  };
}

/** What an access grants, or a request asked for, in words. */
export function useGranted() {
  const { t } = useTranslation();
  return (a: Pick<AccessRow, 'api' | 'data'> | Pick<RequestRow, 'wants_api' | 'wants_data'>) => {
    const [api, data] = 'api' in a ? [a.api, a.data] : [a.wants_api, a.wants_data];
    return t(`pages:access.granted.${api && data ? 'both' : api ? 'api' : 'data'}`);
  };
}
