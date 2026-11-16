import type { TFunction } from 'i18next';
import { ApiError, NetworkError, type FieldError } from '@/shared/services/api';
import '@/shared/locales/pages';

/** One field's error with the data it carries; kept out of ApiError, which loads with the first page. */
export function errorFor(error: unknown, field: string): FieldError | undefined {
  return error instanceof ApiError ? error.errors.find((e) => e.field === field) : undefined;
}

/** The sentence for one field's error code, from the locales, with the data it carries (minutes to wait, where a link
 *  went, a suggested address). */
export function fieldError(t: TFunction, error: unknown, field: string): string | undefined {
  if (!(error instanceof ApiError)) return undefined;
  const found = errorFor(error, field);
  return found
    ? t(`pages:errors.${field}.${found.code}`, {
        defaultValue: t('pages:errors.unknown'), count: found.minutes,
        to: found.to && `\u2068${found.to}\u2069`, suggestion: found.suggestion && `\u2068${found.suggestion}\u2069`,
      })
    : undefined;
}

/** The form-level sentence: nothing when the fields already say what is wrong. */
export function formError(t: TFunction, error: unknown, fields: string[]): string | undefined {
  if (!error) return undefined;
  if (error instanceof NetworkError) return t('pages:auth.network');
  if (error instanceof ApiError) {
    if (error.status === 429) return t('pages:auth.tooMany');
    if (error.errors.some((e) => fields.includes(e.field))) return undefined;
  }
  return t('pages:errors.unknown');
}
