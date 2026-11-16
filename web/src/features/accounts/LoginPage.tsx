import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, Navigate, useLocation, useNavigate, useSearchParams } from 'react-router-dom';
import { primaryButton } from '@/shared/components/buttons';
import { PasswordField, TextField } from '@/shared/components/Field';
import { applyLanguage } from '@/shared/locales/i18n';
import { ApiError } from '@/shared/services/api';
import { useSession } from '@/shared/stores/session';
import { AuthLayout } from './AuthLayout';
import { GoogleButton } from './GoogleButton';
import { accountsApi, ME_KEY } from './accounts.service';
import { afterSignIn } from './pendingConnect';
import { useRegistrationOpen } from './registration';
import { errorFor, fieldError, formError } from './errorText';
import '@/shared/locales/pages';

// Cloudflare's Turnstile, loaded only when the brake asks for it. The day of reading has the same loader
// (features/corpus/ReadingLimit.tsx, which also declares window.turnstile): one module shared by two lazy pages would
// be one more chunk named in the first load, and the first load has no bytes to spare.
let loading: Promise<void> | null = null;
function loadTurnstile(): Promise<void> {
  if (window.turnstile) return Promise.resolve();
  loading ??= new Promise<void>((done, fail) => {
    const script = document.createElement('script');
    script.src = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit';
    script.async = true;
    script.onload = () => done();
    script.onerror = () => { loading = null; fail(new Error('turnstile')); };
    document.head.appendChild(script);
  });
  return loading;
}

/** Cloudflare's check, asked when many wrong passwords were tried on this account (back/apps/accounts/services/brake.py):
 *  passing it lets this password be judged, so a stranger's tries never keep the account's holder out. */
function HumanCheck({ sitekey, onToken }: { sitekey: string; onToken: (token: string) => void }) {
  const { t, i18n } = useTranslation();
  const box = useRef<HTMLDivElement>(null);
  const done = useRef(onToken);
  done.current = onToken;
  const [state, setState] = useState<'loading' | 'ready' | 'failed'>('loading');

  useEffect(() => {
    let id = '';
    let gone = false;
    loadTurnstile()
      .then(() => {
        if (gone || !box.current || !window.turnstile) return;
        id = window.turnstile.render(box.current, {
          sitekey,
          language: i18n.language === 'fr' ? 'fr' : 'ar',
          size: window.innerWidth < 360 ? 'compact' : 'normal',
          callback: (token: string) => done.current(token),
          'error-callback': () => { if (!gone) setState('failed'); },
        });
        setState('ready');
      })
      .catch(() => { if (!gone) setState('failed'); });
    return () => {
      gone = true;
      if (id) window.turnstile?.remove(id);
    };
  }, [sitekey, i18n.language]);

  return (
    <div className="flex flex-col items-start gap-2">
      <div ref={box} className="min-h-[65px]" />
      {state === 'loading' ? <p role="status" className="m-0 text-body text-ink-soft">{t('pages:missing.checkLoading')}</p> : null}
      {state === 'failed' ? <p role="alert" className="m-0 text-body text-repealed">{t('pages:missing.checkFailed')}</p> : null}
    </div>
  );
}

export default function LoginPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const [params] = useSearchParams();
  const queryClient = useQueryClient();
  const { tokens, ended, setTokens, acknowledgeEnded } = useSession();
  const [login, setLogin] = useState(params.get('login') ?? '');
  const [password, setPassword] = useState('');
  const from = (location.state as { from?: string } | null)?.from ?? afterSignIn();

  const signIn = useMutation({
    mutationFn: (check: string) => accountsApi.signIn(login.trim(), password, check),
    onSuccess: async (newTokens) => {
      setTokens(newTokens);
      try {
        const me = await queryClient.fetchQuery({ queryKey: ME_KEY, queryFn: accountsApi.me });
        void applyLanguage(me.preferred_language);
      } catch {
        // The account page loads it again.
      }
      navigate(from, { replace: true });
    },
  });

  const registrationOpen = useRegistrationOpen();

  // Signed in (now, or already): where the sign-in was going. Once the sign-in settles this render runs before the
  // navigation its success asked for, and «/account» here sent every reader there (3 Nov 2026).
  if (tokens && !signIn.isPending) return <Navigate to={from} replace />;

  // A wrong password, an address no account holds (with its fix when the provider is misspelt), the brake's wait.
  const refused = errorFor(signIn.error, 'login');
  const suggestion = refused?.code === 'typo' ? refused.suggestion : undefined;
  // Past the brake, with Cloudflare's check set: the check, then the same sign-in with its token.
  const sitekey = refused?.code === 'check' ? refused.sitekey : undefined;
  const message =
    signIn.error instanceof ApiError && signIn.error.codeFor('login')
      ? fieldError(t, signIn.error, 'login')
      : signIn.error instanceof ApiError && signIn.error.status === 401
        ? t('pages:auth.wrongCredentials')
        : formError(t, signIn.error, []);
  const forgot = `/forgot${login.trim() ? `?login=${encodeURIComponent(login.trim())}` : ''}`;

  return (
    <AuthLayout
      title={t('pages:auth.signInTitle')}
      footer={
        registrationOpen ? (
          <>
            {t('pages:auth.noAccount')} <Link to="/register" className="underline">{t('pages:auth.createAccount')}</Link>
          </>
        ) : null
      }
    >
      {ended ? (
        <p role="status" className="mb-6 rounded-control bg-wash px-4 py-3 text-body">
          {t('pages:auth.sessionEnded')}
        </p>
      ) : null}
      <GoogleButton next={from} />
      <form
        noValidate
        className="flex flex-col gap-5"
        onSubmit={(e) => {
          e.preventDefault();
          acknowledgeEnded();
          signIn.mutate('');
        }}
      >
        <TextField
          label={t('pages:auth.login')}
          value={login}
          onChange={(e) => setLogin(e.target.value)}
          autoComplete="username"
          autoCapitalize="none"
          dir="auto"
          required
        />
        <PasswordField
          label={t('pages:auth.password')}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete="current-password"
          required
          after={
            <Link to={forgot} className="self-start text-meta font-medium">
              {t('pages:auth.forgot')}
            </Link>
          }
        />
        {message ? (
          <div role="alert" className="flex flex-col items-start gap-2 text-body text-repealed">
            <p className="m-0">{message}</p>
            {suggestion ? (
              <button
                type="button"
                className="cursor-pointer border-0 bg-transparent p-0 text-body font-medium text-stamp underline"
                onClick={() => {
                  setLogin(suggestion);
                  signIn.reset();
                }}
              >
                {t('pages:auth.useSuggestion')} <bdi dir="ltr">{suggestion}</bdi>
              </button>
            ) : null}
            {sitekey ? <HumanCheck sitekey={sitekey} onToken={(token) => signIn.mutate(token)} /> : null}
            {signIn.error instanceof ApiError && ['locked', 'check'].includes(signIn.error.codeFor('login') ?? '') ? (
              <Link to={forgot} className="font-medium">{t('pages:auth.forgot')}</Link>
            ) : null}
          </div>
        ) : null}
        <button type="submit" disabled={signIn.isPending} className={primaryButton}>
          {signIn.isPending ? t('pages:auth.signingIn') : t('pages:auth.signIn')}
        </button>
      </form>
    </AuthLayout>
  );
}
