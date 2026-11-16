import { useQueryClient } from '@tanstack/react-query';
import { type FormEvent, useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate } from 'react-router-dom';
import { primaryButton } from '@/shared/components/buttons';
import { TextField } from '@/shared/components/Field';
import { applyLanguage, type Language } from '@/shared/locales/i18n';
import { ApiError } from '@/shared/services/api';
import { useSession } from '@/shared/stores/session';
import { AuthLayout } from './AuthLayout';
import { accountsApi, ME_KEY, type GoogleAnswer } from './accounts.service';
import { fieldError, formError } from './errorText';
import { forgetGoogle, readGoogleReturn } from './google';
import '@/shared/locales/pages';

type Step = { kind: 'working' } | { kind: 'signup'; email: string } | { kind: 'failed'; message: string };

/** The refusal's sentence, whichever field it names (google, registration, login, username). */
function refusal(t: Parameters<typeof fieldError>[0], err: unknown): string {
  for (const field of ['google', 'registration', 'login', 'username']) {
    const said = fieldError(t, err, field);
    if (said) return said;
  }
  return formError(t, err, []) ?? t('pages:errors.unknown');
}

/** `/auth/google`, where Google sends the tab back (google.ts, 9 Nov 2026). A known account is signed in and sent on; a
 *  newcomer stops here to choose a username, as at the sign-up's door (Google's name is not taken). Google's token
 *  waits in memory meanwhile (it lives an hour) and goes back with the username. */
export default function GooglePage() {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const setTokens = useSession((s) => s.setTokens);
  // Read once: the effect below wipes the address and the tab's secrets.
  const [answer] = useState(() => readGoogleReturn(window.location.hash));
  const [step, setStep] = useState<Step>(() => answer.ok ? { kind: 'working' }
    : { kind: 'failed', message: t(answer.reason === 'cancelled' ? 'pages:auth.googleCancelled' : 'pages:auth.googleStale') });
  const [username, setUsername] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const sent = useRef(false);

  /** In, and on to where the reader was going. */
  const land = async (session: Exclude<GoogleAnswer, { code: 'google_signup' }>, next: string) => {
    setTokens({ access: session.access, refresh: session.refresh });
    queryClient.setQueryData(ME_KEY, session.user);
    void applyLanguage(session.user.preferred_language);
    navigate(next, { replace: true });
  };

  useEffect(() => {
    forgetGoogle();
    if (!answer.ok || sent.current) return;
    sent.current = true;
    accountsApi.google({ credential: answer.credential, nonce: answer.nonce })
      .then((res) => ('code' in res ? setStep({ kind: 'signup', email: res.email }) : land(res, answer.next)))
      .catch((err: unknown) => setStep({ kind: 'failed', message: refusal(t, err) }));
    // Once, on arrival: the answer never changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const signUp = async (e: FormEvent) => {
    e.preventDefault();
    if (busy || !answer.ok) return;
    setBusy(true);
    setError(null);
    try {
      const res = await accountsApi.google({ credential: answer.credential, nonce: answer.nonce, username: username.trim(),
                                             preferred_language: (i18n.language === 'fr' ? 'fr' : 'ar') as Language });
      if (!('code' in res)) await land(res, answer.next);
    } catch (err) {
      // An expired token (an hour on this form) cannot be mended here.
      if (err instanceof ApiError && err.codeFor('google') === 'invalid') setStep({ kind: 'failed', message: t('pages:auth.googleStale') });
      else if (err instanceof ApiError && !err.codeFor('username')) setStep({ kind: 'failed', message: refusal(t, err) });
      else setError(err);
    } finally {
      setBusy(false);
    }
  };

  if (step.kind === 'working') {
    return (
      <AuthLayout title={t('pages:auth.googleTitle')}>
        <p role="status" className="m-0 text-body text-ink-soft">{t('pages:auth.googleWorking')}</p>
      </AuthLayout>
    );
  }
  if (step.kind === 'failed') {
    return (
      <AuthLayout title={t('pages:auth.googleTitle')} footer={<Link to="/login">{t('pages:auth.googleBack')}</Link>}>
        <p role="alert" className="m-0 text-body text-repealed">{step.message}</p>
      </AuthLayout>
    );
  }
  return (
    <AuthLayout title={t('pages:auth.googleSignupTitle')}>
      <form noValidate className="flex flex-col gap-5" onSubmit={(e) => void signUp(e)}>
        <p className="m-0 text-body">
          {t('pages:auth.googleSignupLead')} <bdi dir="ltr" className="font-medium">{step.email}</bdi>
        </p>
        <TextField label={t('pages:auth.username')} hint={t('pages:auth.googleUsernameHint')} value={username}
                   onChange={(e) => { setUsername(e.target.value); setError(null); }} error={fieldError(t, error, 'username')}
                   autoComplete="username" autoCapitalize="none" dir="ltr" required />
        <button type="submit" disabled={busy || !username.trim()} className={primaryButton}>
          {busy ? t('pages:auth.registering') : t('pages:auth.googleCreate')}
        </button>
      </form>
    </AuthLayout>
  );
}
