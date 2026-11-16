import { useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate } from 'react-router-dom';
import { accountsApi, ME_KEY, type User } from '@/features/accounts/accounts.service';
import { errorFor, fieldError, formError } from '@/features/accounts/errorText';
import { PasswordField, TextField } from '@/shared/components/Field';
import { Button, LinesSkeleton } from '@/shared/components/ui';
import { applyLanguage, type Language } from '@/shared/locales/i18n';
import { api } from '@/shared/services/api';
import { fileName } from '@/shared/services/fileName';
import { useSession } from '@/shared/stores/session';
import { errorText, shortDate, useT } from '../strings';
import { Line, Part } from './Part';
import { useScrollToHash } from './scroll';

const field = 'h-11 rounded-control border border-field bg-sheet px-3 text-body focus:border-stamp focus:outline-none';

/**
 * «الإعدادات» (/account/settings, 16 Nov 2026): how the account is named, addressed and written to; how it signs in;
 * the assistants connected to it; its personal data (a copy, or deleting the account: law 09-08); leaving this device.
 * Each part is opened by its old address too (/account#apps leads to /account/settings#apps).
 */
export default function AccountSettings({ user }: { user: User }) {
  useScrollToHash(true);
  return (
    <div className="ac-settings">
      <Settings user={user} />
      <SignIn user={user} />
      <Connections />
      <Data user={user} />
      <Leave />
    </div>
  );
}

/** The name others see, the site's language, how the site addresses one, letters: one form. */
function Settings({ user }: { user: User }) {
  const { t } = useT();
  const app = useTranslation().t;
  const client = useQueryClient();
  const [name, setName] = useState(user.display_name);
  const [language, setLanguage] = useState<Language>(user.preferred_language);
  const [form, setForm] = useState(user.address_form);
  const [emails, setEmails] = useState(user.email_notices);
  const [state, setState] = useState<'' | 'saving' | 'saved'>('');
  const [error, setError] = useState<unknown>(null);
  const changed = () => { setState(''); setError(null); };
  const save = async () => {
    setState('saving'); setError(null);
    try {
      const saved = await api<User>('/auth/me/', { method: 'PATCH',
        json: { display_name: name, preferred_language: language, address_form: form, email_notices: emails } });
      client.setQueryData(ME_KEY, saved);
      if (saved.preferred_language !== user.preferred_language) void applyLanguage(saved.preferred_language);
      setState('saved');
    } catch (e) {
      setError(e);
      setState('');
    }
  };
  return (
    <Part id="settings" title={t('me2.settingsTitle')}>
      <form noValidate className="ac-form" onSubmit={(e) => { e.preventDefault(); void save(); }}>
        <TextField label={app('pages:account.displayName')} hint={app('pages:auth.displayNameHint')} error={fieldError(app, error, 'display_name')}
                   value={name} onChange={(e) => { setName(e.target.value); changed(); }} autoComplete="nickname" dir="auto" />
        <fieldset className="m-0 border-0 p-0">
          <legend className="ac-legend">{app('pages:account.language')}</legend>
          <div className="ac-seg">
            {(['ar', 'fr'] as const).map((lang) => (
              <label key={lang} lang={lang}>
                <input type="radio" name="language" className="sr-only" checked={language === lang} onChange={() => { setLanguage(lang); changed(); }} />
                {app(`languages.${lang}`)}
              </label>
            ))}
          </div>
        </fieldset>
        <fieldset className="m-0 border-0 p-0">
          <legend className="ac-legend">{t('account.form')}</legend>
          <div className="ac-seg">
            {(['', 'm', 'f'] as const).map((f) => (
              <label key={f}>
                <input type="radio" name="form" className="sr-only" checked={form === f} onChange={() => { setForm(f); changed(); }} />
                {t(`account.forms.${f}`)}
              </label>
            ))}
          </div>
        </fieldset>
        <label className="ac-check">
          <input type="checkbox" checked={emails} onChange={(e) => { setEmails(e.target.checked); changed(); }} />
          <span>{t('account.emails')}</span>
        </label>
        <div className="ac-save">
          <Button variant="primary" type="submit" disabled={state === 'saving'}>{state === 'saving' ? app('pages:account.saving') : app('pages:account.save')}</Button>
          <p role="status" className="m-0 text-body text-in-force">{state === 'saved' ? app('pages:account.saved') : ''}</p>
          {formError(app, error, ['display_name']) ? <p role="alert" className="m-0 text-body text-repealed">{formError(app, error, ['display_name'])}</p> : null}
        </div>
      </form>
    </Part>
  );
}

/** How one signs in (3 Nov 2026, as sign-up opened with real letters): the username, the address and whether it is
 *  proven, a new address (asked with the password; unproven until its code comes back; a misspelt provider answered with
 *  its fix), a new password (the other devices are signed out, this one stays). */
function SignIn({ user }: { user: User }) {
  const { t } = useT();
  const app = useTranslation().t;
  const client = useQueryClient();
  const setTokens = useSession((s) => s.setTokens);
  const [email, setEmail] = useState('');
  const [emailPassword, setEmailPassword] = useState('');
  const [emailState, setEmailState] = useState<'' | 'saving' | 'sent' | 'unsent'>('');
  const [emailError, setEmailError] = useState<unknown>(null);
  const [password, setPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [passwordState, setPasswordState] = useState<'' | 'saving' | 'saved'>('');
  const [passwordError, setPasswordError] = useState<unknown>(null);

  const changeEmail = async (to: string, confirmed = false) => {
    setEmailState('saving'); setEmailError(null);
    try {
      const done = await accountsApi.changeEmail(to, emailPassword, confirmed);
      client.setQueryData(ME_KEY, done.user);
      setEmail(''); setEmailPassword('');
      setEmailState(done.code_sent ? 'sent' : 'unsent');
    } catch (e) { setEmailError(e); setEmailState(''); }
  };
  const fix = errorFor(emailError, 'email');
  const suggestion = fix?.code === 'typo' ? fix.suggestion : undefined;

  return (
    <Part id="signin" title={app('pages:account.signinTitle')}>
      <p className="m-0 text-body">
        {app('pages:account.signinAs')} <bdi className="font-semibold">{user.username}</bdi>
        {' · '}<bdi dir="ltr">{user.email}</bdi>{' '}
        <span className={user.email_proven ? 'text-in-force' : 'text-repealed'}>
          ({user.email_proven ? app('pages:account.proven') : app('pages:account.unproven')})
        </span>
      </p>
      {emailState === 'sent' || emailState === 'unsent' ? (
        <p role="status" className="m-0 text-body text-in-force">
          {app(emailState === 'sent' ? 'pages:account.emailChanged' : 'pages:account.emailChangedNoCode',
               { email: `\u2068${user.email}\u2069` })} {!user.email_proven ? <Link to="/account#prove">{t('me2.secProve')}</Link> : null}
        </p>
      ) : null}

      <details className="ac-fold">
        <summary>{app('pages:account.changeEmail')}</summary>
        <form noValidate className="ac-form" onSubmit={(e) => { e.preventDefault(); void changeEmail(email); }}>
          <TextField label={app('pages:account.newEmail')} type="email" dir="ltr" autoComplete="email" value={email}
                     error={fieldError(app, emailError, 'email')}
                     onChange={(e) => { setEmail(e.target.value); setEmailError(null); setEmailState(''); }}
                     after={suggestion ? (
                       <div className="flex flex-col gap-2.5 rounded-control bg-wash px-3 py-3">
                         <p className="m-0 text-body">{app('pages:auth.didYouMean')} <bdi dir="ltr" className="font-semibold">{suggestion}</bdi></p>
                         <div className="flex flex-wrap gap-2">
                           <Button onClick={() => { setEmail(suggestion); void changeEmail(suggestion); }}>{app('pages:auth.fixIt')}</Button>
                           <Button onClick={() => void changeEmail(email, true)}>{app('pages:auth.keepMine')}</Button>
                         </div>
                       </div>
                     ) : null} />
          <PasswordField label={app('pages:account.currentPassword')} autoComplete="current-password" value={emailPassword}
                         error={fieldError(app, emailError, 'password')}
                         onChange={(e) => { setEmailPassword(e.target.value); setEmailError(null); }} />
          <div className="ac-save">
            <Button variant="primary" type="submit" disabled={emailState === 'saving' || !email.trim() || !emailPassword}>
              {emailState === 'saving' ? app('pages:account.saving') : app('pages:account.changeEmail')}
            </Button>
            {formError(app, emailError, ['email', 'password']) ? (
              <p role="alert" className="m-0 text-body text-repealed">{formError(app, emailError, ['email', 'password'])}</p>
            ) : null}
          </div>
        </form>
      </details>

      <details className="ac-fold">
        <summary>{app('pages:account.changePassword')}</summary>
        {user.has_password === false ? (
          // An account Google opened has no password to change (9 Nov 2026): the reset's letter sets one.
          <p className="m-0 text-body">
            {app('pages:account.noPassword')}{' '}
            <Link to={`/forgot?login=${encodeURIComponent(user.username)}`} className="font-medium">{app('pages:account.setPassword')}</Link>
          </p>
        ) : (
        <form noValidate className="ac-form" onSubmit={async (e) => {
          e.preventDefault(); setPasswordState('saving'); setPasswordError(null);
          try {
            setTokens(await accountsApi.changePassword(password, newPassword));
            setPassword(''); setNewPassword(''); setPasswordState('saved');
          } catch (err) { setPasswordError(err); setPasswordState(''); }
        }}>
          <input type="text" name="username" autoComplete="username" value={user.username} readOnly hidden />
          <PasswordField label={app('pages:account.currentPassword')} autoComplete="current-password" value={password}
                         error={fieldError(app, passwordError, 'password')}
                         onChange={(e) => { setPassword(e.target.value); setPasswordError(null); setPasswordState(''); }}
                         after={<Link to={`/forgot?login=${encodeURIComponent(user.username)}`} className="self-start text-meta">{app('pages:auth.forgot')}</Link>} />
          <PasswordField label={app('pages:account.newPassword')} hint={app('pages:auth.passwordHint')} autoComplete="new-password"
                         value={newPassword} error={fieldError(app, passwordError, 'new_password')}
                         onChange={(e) => { setNewPassword(e.target.value); setPasswordError(null); setPasswordState(''); }} />
          <div className="ac-save">
            <Button variant="primary" type="submit" disabled={passwordState === 'saving' || !password || !newPassword}>
              {passwordState === 'saving' ? app('pages:account.saving') : app('pages:account.changePassword')}
            </Button>
            <p role="status" className="m-0 text-body text-in-force">{passwordState === 'saved' ? app('pages:account.passwordChanged') : ''}</p>
            {formError(app, passwordError, ['password', 'new_password']) ? (
              <p role="alert" className="m-0 text-body text-repealed">{formError(app, passwordError, ['password', 'new_password'])}</p>
            ) : null}
          </div>
        </form>
        )}
      </details>
    </Part>
  );
}

type Connection = { id: number; name: string; known: boolean; domain: string; since: string; used_at: string | null;
  calls_this_month: number };

/** «التطبيقات المتصلة»: the assistants that read the site with this account, and «فصل». None is one line. */
function Connections() {
  const app = useTranslation().t;
  const { i18n } = useT();
  const [rows, setRows] = useState<Connection[] | null>(null);
  const [error, setError] = useState<unknown>(null);
  useEffect(() => {
    let live = true;
    api<Connection[]>('/oauth/connections/').then((r) => { if (live) setRows(r); }).catch((e) => { if (live) setError(e); });
    return () => { live = false; };
  }, []);
  const failed = error ? <p role="alert" className="m-0 text-meta text-repealed">{formError(app, error, [])}</p> : null;
  if (rows && !rows.length) {
    return (
      <Line id="apps" title={app('pages:account.appsTitle')}>
        {app('pages:account.appsNone')} <Link to="/ai" className="ac-inline">{app('pages:account.appsHow')}</Link>
      </Line>
    );
  }
  return (
    <Part id="apps" title={app('pages:account.appsTitle')}>
      {rows === null && !error ? <LinesSkeleton lines={1} /> : null}
      {rows ? (
        <ul className="ac-rows">
          {rows.map((c) => (
            <li key={c.id}>
              <div className="ac-row-head">
                <span className="font-semibold">{c.name || c.domain}</span>
                <span dir="ltr" className="text-meta text-ink-soft">{c.domain}</span>
                <time dateTime={c.since}>{shortDate(c.since, i18n.language)}</time>
              </div>
              <div className="ac-row-head">
                <span className="text-meta text-ink-soft">
                  {app('pages:account.appsUse', { count: c.calls_this_month })}
                  {c.used_at ? ` · ${app('pages:account.appsLast', { date: shortDate(c.used_at, i18n.language) })}` : ''}
                </span>
                <Button onClick={async () => {
                  try {
                    await api(`/oauth/connections/${c.id}/`, { method: 'DELETE' });
                    setRows((all) => (all ?? []).filter((x) => x.id !== c.id));
                  } catch (e) { setError(e); }
                }}>{app('pages:account.appsEnd')}</Button>
              </div>
            </li>
          ))}
        </ul>
      ) : null}
      {failed}
    </Part>
  );
}

/** «معطياتك الشخصية» (law 09-08): a copy of them, or deleting the account. */
function Data({ user }: { user: User }) {
  const { t } = useT();
  const navigate = useNavigate();
  const client = useQueryClient();
  const clear = useSession((s) => s.clear);
  const [password, setPassword] = useState('');
  const [error, setError] = useState<unknown>(null);
  const download = async () => {
    const data = await api<object>('/auth/me/export/');
    const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' }));
    const a = Object.assign(document.createElement('a'), { href: url, download: fileName(`${user.username}.json`) });
    a.click();
    URL.revokeObjectURL(url);
  };
  return (
    <Part id="data" title={t('account.dataTitle')} lead={t('account.dataLead')}>
      <Button onClick={() => void download()} className="self-start">{t('account.export')}</Button>
      <details className="ac-fold danger">
        <summary>{t('account.deleteTitle')}</summary>
        <p className="m-0 text-meta text-ink-soft">{t('account.deleteLede')}</p>
        <form className="mt-3 flex flex-wrap items-end gap-3" onSubmit={async (e) => {
          e.preventDefault(); setError(null);
          try {
            await api('/auth/me/delete/', { method: 'POST', json: { password } });
            clear();
            client.clear();
            navigate('/', { replace: true });
          } catch (err) { setError(err); }
        }}>
          <label className="flex flex-col gap-1 text-meta">{t('account.deletePassword')}
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} dir="ltr" autoComplete="current-password" className={field} />
          </label>
          <button type="submit" disabled={!password} className="h-11 rounded-control border border-repealed bg-sheet px-4 text-body font-semibold text-repealed hover:bg-paper">
            {t('account.deleteConfirm')}
          </button>
        </form>
        {error ? <p role="alert" className="m-0 mt-2 text-meta text-repealed">{errorText(t, error)}</p> : null}
      </details>
    </Part>
  );
}

/** Leaving this device: the server forgets its refresh token; the other devices stay signed in. */
function Leave() {
  const app = useTranslation().t;
  const navigate = useNavigate();
  const client = useQueryClient();
  const { tokens, clear } = useSession();
  const [busy, setBusy] = useState(false);
  return (
    <Part id="leave" title={app('pages:account.signOutTitle')} lead={app('pages:account.signOutHint')}>
      <Button disabled={busy} className="self-start" onClick={async () => {
        setBusy(true);
        if (tokens) await accountsApi.signOut(tokens.refresh).catch(() => undefined);
        clear();
        client.clear();
        navigate('/login', { replace: true });
      }}>{app('pages:account.signOut')}</Button>
    </Part>
  );
}
