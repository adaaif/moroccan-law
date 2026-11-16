/**
 * «المتابعة بحساب Google» without Google's script (9 Nov 2026): no request to Google leaves a page of
 * ours. A tap sends the whole tab to Google's own sign-in page; Google sends it back to `/auth/google` with the ID
 * token in the address's FRAGMENT (never sent to any server, ours included), and that page trades it at
 * `/api/auth/google/` like a password (back/apps/accounts/services/google.py).
 *
 * `state` proves the return answers a tap made in THIS tab (nobody can sign a visitor into their own account by sending
 * them a link), and `nonce` rides inside the signed token, which the server compares. Both wait in sessionStorage, this
 * tab only, for the round trip. The scope is `openid email`: the address, not the name, not the picture.
 */
const KEY = 'law.google';
export const GOOGLE_RETURN = '/auth/google';

function random(): string {
  return Array.from(crypto.getRandomValues(new Uint8Array(16)), (b) => b.toString(16).padStart(2, '0')).join('');
}

/** A place on this site to land on (never another site's address). */
function onSite(path: unknown): path is string {
  return typeof path === 'string' && path.startsWith('/') && !path.startsWith('//') && !path.startsWith('/\\');
}

/** Leave for Google. `next` is where the reader goes once in. */
export function startGoogle(clientId: string, next: string) {
  const state = random();
  const nonce = random();
  try {
    sessionStorage.setItem(KEY, JSON.stringify({ state, nonce, next }));
  } catch {
    /* a private window without storage: the return will say so */
  }
  const url = new URL('https://accounts.google.com/o/oauth2/v2/auth');
  url.search = new URLSearchParams({
    client_id: clientId,
    redirect_uri: `${window.location.origin}${GOOGLE_RETURN}`,
    response_type: 'id_token',
    scope: 'openid email',
    nonce,
    state,
    prompt: 'select_account',
  }).toString();
  window.location.assign(url.toString());
}

export type GoogleReturn =
  | { ok: true; credential: string; nonce: string; next: string }
  | { ok: false; reason: 'cancelled' | 'stale' };

/** What Google sent back in `hash`, checked against this tab's tap. */
export function readGoogleReturn(hash: string): GoogleReturn {
  const answer = new URLSearchParams(hash.replace(/^#/, ''));
  let saved: { state?: string; nonce?: string; next?: string } = {};
  try {
    saved = JSON.parse(sessionStorage.getItem(KEY) ?? '{}') as typeof saved;
  } catch {
    /* nothing saved */
  }
  if (answer.get('error')) return { ok: false, reason: 'cancelled' };
  const credential = answer.get('id_token');
  if (!credential || !saved.state || answer.get('state') !== saved.state) return { ok: false, reason: 'stale' };
  return { ok: true, credential, nonce: saved.nonce ?? '', next: onSite(saved.next) ? saved.next : '/account' };
}

/** The token leaves the address bar and the tap's secrets leave the tab. */
export function forgetGoogle() {
  try {
    sessionStorage.removeItem(KEY);
  } catch {
    /* nothing to forget */
  }
  window.history.replaceState(null, '', window.location.pathname);
}
