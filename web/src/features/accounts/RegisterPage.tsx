import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom';
import { primaryButton, secondaryButton } from '@/shared/components/buttons';
import { PasswordField, TextField } from '@/shared/components/Field';
import { currentLanguage } from '@/shared/locales/i18n';
import { ApiError } from '@/shared/services/api';
import { useSession } from '@/shared/stores/session';
import { AuthLayout } from './AuthLayout';
import { GoogleButton } from './GoogleButton';
import { accountsApi, ME_KEY, type RegisterBody } from './accounts.service';
import { errorFor, fieldError, formError } from './errorText';
import { afterSignIn } from './pendingConnect';
import { useRegistration } from './registration';
import '@/shared/locales/pages';

const FIELDS = ['username', 'email', 'password', 'display_name'];

export default function RegisterPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const queryClient = useQueryClient();
  const { tokens, setTokens } = useSession();
  const [form, setForm] = useState({ username: '', email: '', display_name: '', password: '' });

  // `extra`: the address fixed as suggested, or kept as typed (`email_confirmed`).
  const register = useMutation({
    mutationFn: (extra: Partial<RegisterBody>) =>
      accountsApi.register({ ...form, preferred_language: currentLanguage(), ...extra }),
    onSuccess: ({ user, access, refresh }) => {
      setTokens({ access, refresh });
      queryClient.setQueryData(ME_KEY, user);
      // Back where the reader was (a discussion they wanted to write in), else the account (F3).
      navigate((location.state as { from?: string } | null)?.from ?? afterSignIn(), { replace: true });
    },
  });

  const registration = useRegistration();

  if (tokens && !register.isPending) return <Navigate to={(location.state as { from?: string } | null)?.from ?? afterSignIn()} replace />;

  // Sign-up closed (REGISTRATION_OPEN): said, with the way in for those who have an account.
  const refused = register.error instanceof ApiError && register.error.codeFor('registration') === 'closed';
  if (registration.data?.open === false || refused) {
    return (
      <AuthLayout
        title={t('pages:auth.registerTitle')}
        footer={
          <>
            {t('pages:auth.haveAccount')} <Link to="/login">{t('pages:auth.goSignIn')}</Link>
          </>
        }
      >
        <p role="status" className="m-0 text-body">{t('pages:errors.registration.closed')}</p>
      </AuthLayout>
    );
  }

  const set = (field: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((f) => ({ ...f, [field]: e.target.value }));

  // «Email in use» must lead into the existing account, never to a second one.
  const emailTaken = register.error instanceof ApiError && register.error.codeFor('email') === 'email_taken';
  // A misspelt provider (gamil.com): its fix, or the address kept as typed (a typo kept at sign-up was for life).
  const emailError = errorFor(register.error, 'email');
  const fix = emailError?.code === 'typo' ? emailError.suggestion : undefined;

  return (
    <AuthLayout
      title={t('pages:auth.registerTitle')}
      footer={
        <>
          {t('pages:auth.haveAccount')} <Link to="/login">{t('pages:auth.goSignIn')}</Link>
        </>
      }
    >
      <GoogleButton next={(location.state as { from?: string } | null)?.from ?? afterSignIn()} />
      <form
        noValidate
        className="flex flex-col gap-5"
        onSubmit={(e) => {
          e.preventDefault();
          register.mutate({});
        }}
      >
        <TextField
          label={t('pages:auth.username')}
          hint={t('pages:auth.usernameHint')}
          error={fieldError(t, register.error, 'username')}
          value={form.username}
          onChange={set('username')}
          autoComplete="username"
          autoCapitalize="none"
          dir="auto"
          required
        />
        <TextField
          label={t('pages:auth.email')}
          error={fieldError(t, register.error, 'email')}
          after={
            emailTaken ? (
              <Link to={`/login?login=${encodeURIComponent(form.email.trim())}`} className="text-body font-medium">
                {t('pages:auth.signInWithEmail')}
              </Link>
            ) : fix ? (
              <div className="flex flex-col gap-2.5 rounded-control bg-wash px-3 py-3">
                <p className="m-0 text-body">
                  {t('pages:auth.didYouMean')} <bdi dir="ltr" className="font-semibold">{fix}</bdi>
                </p>
                <div className="flex flex-wrap gap-2">
                  <button type="button" className={secondaryButton} disabled={register.isPending}
                          onClick={() => { setForm((f) => ({ ...f, email: fix })); register.mutate({ email: fix }); }}>
                    {t('pages:auth.fixIt')}
                  </button>
                  <button type="button" className={secondaryButton} disabled={register.isPending}
                          onClick={() => register.mutate({ email_confirmed: true })}>
                    {t('pages:auth.keepMine')}
                  </button>
                </div>
              </div>
            ) : null
          }
          type="email"
          dir="ltr"
          value={form.email}
          onChange={set('email')}
          autoComplete="email"
          required
        />
        <TextField
          label={t('pages:auth.displayName')}
          hint={t('pages:auth.displayNameHint')}
          error={fieldError(t, register.error, 'display_name')}
          value={form.display_name}
          onChange={set('display_name')}
          autoComplete="nickname"
          dir="auto"
        />
        <PasswordField
          label={t('pages:auth.password')}
          hint={t('pages:auth.passwordHint')}
          error={fieldError(t, register.error, 'password')}
          value={form.password}
          onChange={set('password')}
          autoComplete="new-password"
          required
        />
        {formError(t, register.error, FIELDS) ? (
          <p role="alert" className="text-body text-repealed">
            {formError(t, register.error, FIELDS)}
          </p>
        ) : null}
        <button type="submit" disabled={register.isPending} className={primaryButton}>
          {register.isPending ? t('pages:auth.registering') : t('pages:auth.register')}
        </button>
      </form>
    </AuthLayout>
  );
}
