import { useTranslation } from 'react-i18next';
import { secondaryButton } from '@/shared/components/buttons';
import { startGoogle } from './google';
import { useRegistration } from './registration';

/** «المتابعة بحساب Google» above the sign-in and sign-up forms, then «أو» (9 Nov 2026): nothing while Google is off. Its
 *  «G» in Google's colours, as Google asks of a button that signs in with it. */
export function GoogleButton({ next }: { next: string }) {
  const { t } = useTranslation();
  // Google's client id when it is on (GOOGLE_OAUTH_CLIENT_ID on the server), else ''; read here, never at first load.
  const clientId = useRegistration().data?.google ?? '';
  if (!clientId) return null;
  return (
    <div className="mb-6 flex flex-col gap-5">
      <button type="button" className={`${secondaryButton} gap-3`} onClick={() => startGoogle(clientId, next)}>
        <svg aria-hidden="true" width="20" height="20" viewBox="0 0 48 48">
          <path fill="#EA4335" d="M24 9.5c3.5 0 6.6 1.2 9 3.6l6.7-6.7C35.6 2.4 30.2 0 24 0 14.6 0 6.6 5.4 2.6 13.2l7.8 6.1C12.3 13.6 17.7 9.5 24 9.5z" />
          <path fill="#4285F4" d="M46.5 24.5c0-1.6-.1-3.1-.4-4.5H24v9h12.7c-.6 3-2.3 5.5-4.8 7.2l7.6 5.9c4.4-4.1 7-10.1 7-17.6z" />
          <path fill="#FBBC05" d="M10.4 28.7c-.5-1.4-.8-3-.8-4.7s.3-3.2.8-4.7l-7.8-6.1C1 16.5 0 20.1 0 24s1 7.5 2.6 10.8l7.8-6.1z" />
          <path fill="#34A853" d="M24 48c6.5 0 11.9-2.1 15.9-5.8l-7.6-5.9c-2.1 1.4-4.9 2.3-8.3 2.3-6.3 0-11.7-4.1-13.6-9.8l-7.8 6.1C6.6 42.6 14.6 48 24 48z" />
        </svg>
        {t('pages:auth.google')}
      </button>
      <p className="m-0 flex items-center gap-3 text-meta text-ink-soft" aria-hidden="true">
        <span className="h-px flex-1 bg-rule" />{t('pages:auth.or')}<span className="h-px flex-1 bg-rule" />
      </p>
    </div>
  );
}
