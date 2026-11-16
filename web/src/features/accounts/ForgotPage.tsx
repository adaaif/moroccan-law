import { useMutation } from '@tanstack/react-query';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useSearchParams } from 'react-router-dom';
import { primaryButton, secondaryButton } from '@/shared/components/buttons';
import { TextField } from '@/shared/components/Field';
import { AuthLayout } from './AuthLayout';
import { accountsApi } from './accounts.service';
import { errorFor, fieldError, formError } from './errorText';
import { useRegistrationOpen } from './registration';
import '@/shared/locales/pages';

/**
 * «نسيت كلمة السر؟» (3 Nov 2026, as sign-up opened with real letters): a username or an address, and a link to the
 * account's address. Asked by an address, the answer shows it back, masked; asked by a username, it says only that the
 * link went to the account's address (usernames are public, and a domain can name the person). An address no account
 * holds is said plainly (sign-up already says «email in use»), with its fix when the provider is misspelt.
 */
export default function ForgotPage() {
  const { t } = useTranslation();
  const [params] = useSearchParams();
  const [login, setLogin] = useState(params.get('login') ?? '');
  const [times, setTimes] = useState(0);
  const registrationOpen = useRegistrationOpen();
  const send = useMutation({
    mutationFn: (value: string) => accountsApi.forgot(value),
    onSuccess: () => setTimes((n) => n + 1),
  });
  const refused = errorFor(send.error, 'login');
  const signIn = `/login${login.trim() ? `?login=${encodeURIComponent(login.trim())}` : ''}`;

  return (
    <AuthLayout
      title={t('pages:auth.forgotTitle')}
      footer={<Link to={signIn}>{t('pages:auth.backToSignIn')}</Link>}
    >
      {send.data ? (
        <div className="flex flex-col gap-5">
          <p role="status" className="m-0 text-body">
            {send.data.to
              ? t('pages:auth.forgotSent', { to: `⁨${send.data.to}⁩` })
              : t('pages:auth.forgotSentAccount')}
          </p>
          <p className="m-0 text-meta text-ink-soft">{t('pages:auth.forgotSpam')}</p>
          <button
            type="button"
            disabled={send.isPending}
            className={`${secondaryButton} self-start`}
            onClick={() => send.mutate(login.trim())}
          >
            {times > 1 ? t('pages:auth.forgotSentAgain') : t('pages:auth.forgotAgain')}
          </button>
        </div>
      ) : (
        <form
          noValidate
          className="flex flex-col gap-5"
          onSubmit={(e) => {
            e.preventDefault();
            send.mutate(login.trim());
          }}
        >
          <p className="m-0 text-body text-ink-soft">{t('pages:auth.forgotLede')}</p>
          <TextField
            label={t('pages:auth.login')}
            value={login}
            onChange={(e) => {
              setLogin(e.target.value);
              if (send.error) send.reset();
            }}
            error={fieldError(t, send.error, 'login')}
            after={
              refused?.code === 'typo' && refused.suggestion ? (
                <button
                  type="button"
                  className="self-start cursor-pointer border-0 bg-transparent p-0 text-body font-medium text-stamp underline"
                  onClick={() => {
                    setLogin(refused.suggestion!);
                    send.mutate(refused.suggestion!);
                  }}
                >
                  {t('pages:auth.useSuggestion')} <bdi dir="ltr">{refused.suggestion}</bdi>
                </button>
              ) : refused?.code === 'no_email' && registrationOpen ? (
                <Link to="/register" className="self-start text-body font-medium">{t('pages:auth.createAccount')}</Link>
              ) : null
            }
            autoComplete="username"
            autoCapitalize="none"
            dir="auto"
            required
          />
          {formError(t, send.error, ['login']) ? (
            <p role="alert" className="m-0 text-body text-repealed">{formError(t, send.error, ['login'])}</p>
          ) : null}
          <button type="submit" disabled={send.isPending || !login.trim()} className={primaryButton}>
            {send.isPending ? t('pages:auth.forgotSending') : t('pages:auth.forgotSend')}
          </button>
        </form>
      )}
    </AuthLayout>
  );
}
