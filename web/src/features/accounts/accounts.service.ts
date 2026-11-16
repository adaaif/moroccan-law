import { useQuery } from '@tanstack/react-query';
import type { Language } from '@/shared/locales/i18n';
import { api } from '@/shared/services/api';
import { useSession, type Tokens } from '@/shared/stores/session';

export type User = {
  id: number;
  /** Whether the account may open the access desk (/data/desk): the server checks again on every call there. */
  desk?: boolean;
  username: string;
  email: string;
  display_name: string;
  preferred_language: Language;
  date_joined: string;
  /** The discussion (D3): a proven address writes; the form of address sets titles and badges. */
  email_proven: boolean;
  address_form: '' | 'm' | 'f';
  email_notices: boolean;
  /** Bound to a Google account; an account Google opened has no password until «نسيت كلمة السر» sets one. */
  google?: boolean;
  has_password?: boolean;
};

/** «المتابعة بحساب Google» (google.ts): signed in, or, for a newcomer, the address Google proved and a username to
 *  choose (the same call again with `username`). */
export type GoogleAnswer = (Tokens & { user: User; created: boolean }) | { code: 'google_signup'; email: string };

export type RegisterBody = {
  username: string;
  email: string;
  password: string;
  display_name?: string;
  preferred_language: Language;
  /** The person saw the suggested fix of a misspelt address and kept theirs. */
  email_confirmed?: boolean;
};

export const accountsApi = {
  /** `code_sent`: whether the six-digit code that proves the address went. */
  register: (body: RegisterBody) =>
    api<Tokens & { user: User; code_sent: boolean }>('/auth/register/', { method: 'POST', json: body }),
  google: (body: { credential: string; nonce: string; username?: string; preferred_language?: Language }) =>
    api<GoogleAnswer>('/auth/google/', { method: 'POST', json: body }),
  /** `login` is a username or an email address. `check`: the Turnstile token, when the brake asked for it. */
  signIn: (login: string, password: string, check = '') =>
    api<Tokens>('/auth/token/', { method: 'POST', json: { username: login, password, ...(check ? { check } : {}) } }),
  me: () => api<User>('/auth/me/'),
  updateMe: (patch: Partial<Pick<User, 'display_name' | 'preferred_language'>>) =>
    api<User>('/auth/me/', { method: 'PATCH', json: patch }),
  signOut: (refresh: string) => api<void>('/auth/logout/', { method: 'POST', json: { refresh } }),
  /** A reset link to the account a username or an address names; answers the address masked when one was typed,
   *  nothing about it for a username. */
  forgot: (login: string) => api<{ to?: string }>('/auth/password/reset/', { method: 'POST', json: { login } }),
  resetCheck: (uid: string, token: string) =>
    api<{ username: string }>('/auth/password/reset/check/', { method: 'POST', json: { uid, token } }),
  /** The new password from the link: signs in. */
  reset: (uid: string, token: string, password: string) =>
    api<Tokens & { user: User }>('/auth/password/reset/confirm/', { method: 'POST', json: { uid, token, password } }),
  /** The other devices are signed out; this one gets a fresh pair. */
  changePassword: (password: string, new_password: string) =>
    api<Tokens>('/auth/password/', { method: 'POST', json: { password, new_password } }),
  /** A new address, unproven until the code sent to it comes back. */
  changeEmail: (email: string, password: string, email_confirmed = false) =>
    api<{ user: User; code_sent: boolean }>('/auth/email/', { method: 'POST', json: { email, password, email_confirmed } }),
};

export const ME_KEY = ['me'] as const;

export function useMe() {
  const signedIn = useSession((s) => s.tokens !== null);
  return useQuery({ queryKey: ME_KEY, queryFn: accountsApi.me, enabled: signedIn, staleTime: 60_000 });
}
