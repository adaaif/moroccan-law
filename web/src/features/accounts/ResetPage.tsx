import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { primaryButton } from '@/shared/components/buttons';
import { PasswordField } from '@/shared/components/Field';
import { applyLanguage } from '@/shared/locales/i18n';
import { ApiError } from '@/shared/services/api';
import { useSession } from '@/shared/stores/session';
import { AuthLayout } from './AuthLayout';
import { accountsApi, ME_KEY } from './accounts.service';
import { fieldError, formError } from './errorText';
import '@/shared/locales/pages';

/** The link's two parts, after «#»: never sent to a server, so the token is in no log. */
function readLink() {
  if (typeof window === 'undefined') return { uid: '', token: '' };
  const parts = new URLSearchParams(window.location.hash.slice(1));
  return { uid: parts.get('u') ?? '', token: parts.get('t') ?? '' };
}

/**
 * The reset link's page: asked at once whether the link still works (a dead one says so before a password is typed),
 * then the new password, which signs in and signs the other devices out (3 Nov 2026).
 */
export default function ResetPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const setTokens = useSession((s) => s.setTokens);
  const [link] = useState(readLink);
  const [password, setPassword] = useState('');

  // The token leaves the address bar and the history once read.
  useEffect(() => {
    if (window.location.hash) window.history.replaceState(window.history.state, '', window.location.pathname);
  }, []);

  const check = useQuery({
    queryKey: ['reset', link.uid, link.token],
    queryFn: () => accountsApi.resetCheck(link.uid, link.token),
    enabled: Boolean(link.uid && link.token),
    retry: false,
    staleTime: Infinity,
    refetchOnWindowFocus: false,
  });
  const save = useMutation({
    mutationFn: () => accountsApi.reset(link.uid, link.token, password),
    onSuccess: ({ user, access, refresh }) => {
      setTokens({ access, refresh });
      queryClient.setQueryData(ME_KEY, user);
      void applyLanguage(user.preferred_language);
    },
  });

  const dead = !link.uid || !link.token
    || (check.error instanceof ApiError && check.error.codeFor('link') === 'dead')
    || (save.error instanceof ApiError && save.error.codeFor('link') === 'dead');

  return (
    <AuthLayout title={t('pages:auth.resetTitle')}>
      {dead ? (
        <div className="flex flex-col gap-5">
          <p role="alert" className="m-0 text-body">{t('pages:errors.link.dead')}</p>
          <Link to="/forgot" className={`${primaryButton} no-underline`}>{t('pages:auth.resetAsk')}</Link>
        </div>
      ) : save.isSuccess ? (
        <div className="flex flex-col gap-5">
          <p role="status" className="m-0 text-body">{t('pages:auth.resetDone')}</p>
          <Link to="/account" replace className={`${primaryButton} no-underline`}>{t('pages:auth.goAccount')}</Link>
        </div>
      ) : check.isPending ? (
        <p role="status" className="m-0 text-body text-ink-soft">{t('pages:auth.resetChecking')}</p>
      ) : check.isError ? (
        <p role="alert" className="m-0 text-body text-repealed">{formError(t, check.error, [])}</p>
      ) : (
        <form
          noValidate
          className="flex flex-col gap-5"
          onSubmit={(e) => {
            e.preventDefault();
            save.mutate();
          }}
        >
          <p className="m-0 text-body">
            {t('pages:auth.resetFor')} <bdi className="font-semibold">{check.data.username}</bdi>
          </p>
          {/* What a password manager files the new password under. */}
          <input type="text" name="username" autoComplete="username" value={check.data.username} readOnly hidden />
          <PasswordField
            label={t('pages:auth.newPassword')}
            hint={t('pages:auth.passwordHint')}
            error={fieldError(t, save.error, 'password')}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="new-password"
            autoFocus
            required
          />
          {formError(t, save.error, ['password', 'link']) ? (
            <p role="alert" className="m-0 text-body text-repealed">{formError(t, save.error, ['password', 'link'])}</p>
          ) : null}
          <button type="submit" disabled={save.isPending} className={primaryButton}>
            {save.isPending ? t('pages:auth.resetSaving') : t('pages:auth.resetSave')}
          </button>
        </form>
      )}
    </AuthLayout>
  );
}
