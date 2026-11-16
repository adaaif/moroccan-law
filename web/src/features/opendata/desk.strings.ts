import { useTranslation } from 'react-i18next';
import i18n from '@/shared/locales/i18n';
import { ApiError, NetworkError } from '@/shared/services/api';
import { refusalKey } from './desk';
import ar from './locales/desk.ar.json';
import fr from './locales/desk.fr.json';

/** The desk's words load with its code, in both languages: no other page pays for them. */
export const NS = 'desk';
if (!i18n.hasResourceBundle('ar', NS)) {
  i18n.addResourceBundle('ar', NS, ar);
  i18n.addResourceBundle('fr', NS, fr);
}

export function useD() {
  return useTranslation(NS);
}

/** A refusal of the server, or a lost connection, in words. */
export function said(t: (key: string, o?: Record<string, unknown>) => string, error: unknown): string {
  if (!error) return '';
  if (error instanceof NetworkError) return t('errors.network');
  if (!(error instanceof ApiError)) return t('errors.unknown');
  return t(refusalKey(error.errors, error.status), { defaultValue: t('errors.unknown') });
}
