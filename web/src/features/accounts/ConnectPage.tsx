import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { Button, Note } from '@/shared/components/ui';
import { api, ApiError } from '@/shared/services/api';
import { useSession } from '@/shared/stores/session';
import { AuthLayout } from './AuthLayout';
import { ME_KEY, useMe, type User } from './accounts.service';
import { formError } from './errorText';
import { keepRequest, sameHost, waitingRequest } from './pendingConnect';
import { useMcpOpen, useRegistrationOpen } from './registration';
import '@/shared/locales/pages';

type Request = {
  client: { name: string; known: boolean; domain: string; self_named: boolean };
  redirect_host: string;
  loopback: boolean;
  scope: string;
  expires_at: string;
};

/** The request's id after «#» (never in a server's log), or the refusal the site shows itself; then out of the address. */
function readAsk(): { r: string; error: string } {
  if (typeof window === 'undefined') return { r: '', error: '' };
  const parts = new URLSearchParams(window.location.hash.slice(1));
  const r = parts.get('r') ?? '';
  const error = parts.get('error') ?? '';
  if (window.location.hash) window.history.replaceState(window.history.state, '', window.location.pathname);
  if (r) keepRequest(r);
  return { r: r || (error ? '' : waitingRequest()), error };
}

/**
 * «/connect» (MC7 of the MCP review, 3 Nov 2026): an assistant (ChatGPT, Claude) asks to read the site with the
 * person's account. Sign in if needed, prove the email in place (C2), then one card: who asks, the host the answer goes to
 * large, what it may read and what it never sees, «سماح» or «رفض». The answer goes back to the assistant's address,
 * once the browser reads that address as going to the host shown.
 */
export default function ConnectPage() {
  const { t } = useTranslation();
  const [ask] = useState(readAsk);
  const signedIn = useSession((s) => s.tokens !== null);
  const me = useMe();
  const registrationOpen = useRegistrationOpen();
  const mcpOpen = useMcpOpen();
  // No account is needed to read the site from an assistant: said to whoever lands here without one.
  const noAccountNeeded = mcpOpen ? <Note tone="law"><p className="m-0 text-body">{t('pages:connect.noAccount')}</p></Note> : null;
  const request = useQuery({
    queryKey: ['oauth-request', ask.r],
    queryFn: () => api<Request>('/oauth/request/', { method: 'POST', json: { r: ask.r } }),
    enabled: Boolean(ask.r),
    retry: false,
    staleTime: Infinity,
    refetchOnWindowFocus: false,
  });
  const [leaving, setLeaving] = useState('');
  const [mismatch, setMismatch] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const decide = async (yes: boolean) => {
    setError(null);
    try {
      const { redirect } = await api<{ redirect: string }>(yes ? '/oauth/approve/' : '/oauth/deny/', {
        method: 'POST', json: { r: ask.r },
      });
      keepRequest(null);
      // The browser's own reading of the address must name the host the page showed: else nothing leaves.
      if (!sameHost(redirect, request.data?.redirect_host ?? '')) {
        setMismatch(true);
        return;
      }
      setLeaving(request.data?.redirect_host ?? '');
      window.location.assign(redirect);
    } catch (e) {
      setError(e);
    }
  };

  const expired = request.error instanceof ApiError && request.error.codeFor('request') === 'expired';
  const title = t('pages:connect.title');

  if (mismatch) {
    return (
      <AuthLayout title={title}>
        <p role="alert" className="m-0 text-body">{t('pages:connect.mismatch')}</p>
        <p className="m-0 mt-4 text-body text-ink-soft">{t('pages:connect.retry')}</p>
      </AuthLayout>
    );
  }
  if (ask.error || (!ask.r && !request.data)) {
    return (
      <AuthLayout title={title}>
        <p role="alert" className="m-0 text-body">
          {t(`pages:connect.errors.${ask.error || 'none'}`, { defaultValue: t('pages:connect.errors.client_invalid') })}
        </p>
        <p className="m-0 mt-4 text-body text-ink-soft">{t('pages:connect.retry')}</p>
        {noAccountNeeded ? <div className="mt-4">{noAccountNeeded}</div> : null}
        <Link to="/ai" className="mt-4 inline-block text-body">{t('pages:connect.howTo')}</Link>
      </AuthLayout>
    );
  }
  if (expired) {
    keepRequest(null);
    return (
      <AuthLayout title={title}>
        <p role="alert" className="m-0 text-body">{t('pages:connect.expired')}</p>
      </AuthLayout>
    );
  }
  if (!request.data) {
    return (
      <AuthLayout title={title}>
        <p role="status" className="m-0 text-body text-ink-soft">
          {request.isError ? formError(t, request.error, []) : t('pages:connect.loading')}
        </p>
      </AuthLayout>
    );
  }

  const asker = request.data;
  const name = asker.client.name || asker.redirect_host;
  return (
    <AuthLayout title={title}>
      <div className="flex flex-col gap-5">
        <div className="flex flex-col gap-1.5">
          <p className="m-0 text-lead font-semibold">{t('pages:connect.asks', { name })}</p>
          <p dir="ltr" className="m-0 self-start font-mono text-h3 text-stamp">{asker.redirect_host}</p>
          {asker.client.self_named ? (
            <p className="m-0 text-meta text-ink-soft">{t('pages:connect.selfNamed')}</p>
          ) : (
            <p className="m-0 text-meta text-in-force">✓ {t('pages:connect.known')}</p>
          )}
        </div>
        {asker.loopback ? (
          <Note tone="warn"><p className="m-0 text-body">{t('pages:connect.loopback')}</p></Note>
        ) : null}
        <div className="flex flex-col gap-2">
          <p className="m-0 text-body font-semibold">{t('pages:connect.can')}</p>
          <ul className="m-0 flex flex-col gap-1 ps-5 text-body">
            <li>{t('pages:connect.canSearch')}</li>
            <li>{t('pages:connect.canBulletin')}</li>
            <li>{t('pages:connect.canCheck')}</li>
          </ul>
          <p className="m-0 text-body">{t('pages:connect.never')}</p>
          <p className="m-0 text-meta text-ink-soft">{t('pages:connect.limits')}</p>
        </div>

        {!signedIn ? (
          <div className="flex flex-col gap-3 border-t border-rule pt-5">
            {noAccountNeeded}
            <p className="m-0 text-body">{t('pages:connect.signInFirst')}</p>
            <div className="flex flex-wrap gap-3">
              <Button variant="primary" to="/login" state={{ from: '/connect' }}>{t('pages:auth.signIn')}</Button>
              {registrationOpen ? (
                <Button to="/register" state={{ from: '/connect' }}>{t('pages:auth.createAccount')}</Button>
              ) : null}
            </div>
          </div>
        ) : me.data && !me.data.email_proven ? (
          <ProveHere user={me.data} />
        ) : leaving ? (
          <p role="status" className="m-0 border-t border-rule pt-5 text-body">{t('pages:connect.leaving', { name: leaving })}</p>
        ) : (
          <div className="flex flex-col gap-3 border-t border-rule pt-5">
            {me.data ? (
              <p className="m-0 text-meta text-ink-soft">
                {t('pages:connect.as')} <bdi className="font-semibold">{me.data.username}</bdi>
              </p>
            ) : null}
            <div className="flex flex-wrap gap-3">
              <Button variant="primary" onClick={() => void decide(true)} disabled={!me.data}>{t('pages:connect.allow')}</Button>
              <Button onClick={() => void decide(false)}>{t('pages:connect.deny')}</Button>
            </div>
            <p className="m-0 text-meta text-ink-soft">{t('pages:connect.goesTo', { host: asker.redirect_host })}</p>
            {error ? <p role="alert" className="m-0 text-body text-repealed">{formError(t, error, [])}</p> : null}
          </div>
        )}
      </div>
    </AuthLayout>
  );
}

/** The six-digit code, in place: connecting needs a proven email (C2). */
function ProveHere({ user }: { user: User }) {
  const { t } = useTranslation();
  const client = useQueryClient();
  const [code, setCode] = useState('');
  const [sent, setSent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  return (
    <form
      className="flex flex-col gap-3 border-t border-rule pt-5"
      onSubmit={async (e) => {
        e.preventDefault(); setBusy(true); setError(null);
        try {
          client.setQueryData(ME_KEY, await api<User>('/auth/email/prove/', { method: 'POST', json: { code } }));
        } catch (err) { setError(err); } finally { setBusy(false); }
      }}
    >
      <p className="m-0 text-body">{t('pages:connect.prove', { email: `⁨${user.email}⁩` })}</p>
      <div className="flex flex-wrap items-end gap-3">
        <label className="flex flex-col gap-1 text-meta">
          {t('pages:connect.code')}
          <input value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))} inputMode="numeric"
                 autoComplete="one-time-code" dir="ltr" placeholder="••••••"
                 className="h-11 w-36 rounded-control border border-field bg-sheet px-3 text-center text-lead tracking-[0.3em] focus:border-stamp focus:outline-none" />
        </label>
        <Button variant="primary" type="submit" disabled={busy || code.length !== 6}>{t('pages:connect.proveIt')}</Button>
        <Button disabled={busy} onClick={async () => {
          setBusy(true); setError(null);
          try { await api('/auth/email/code/', { method: 'POST' }); setSent(true); } catch (err) { setError(err); } finally { setBusy(false); }
        }}>{t('pages:connect.sendCode')}</Button>
      </div>
      {sent ? <p role="status" className="m-0 text-meta text-in-force">{t('pages:connect.codeSent')}</p> : null}
      {error ? <p role="alert" className="m-0 text-meta text-repealed">{t(`pages:errors.${error instanceof ApiError && error.errors[0] ? `${error.errors[0].field}.${error.errors[0].code}` : 'unknown'}`, { defaultValue: formError(t, error, []) })}</p> : null}
    </form>
  );
}
