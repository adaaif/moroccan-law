/** A connection request waiting on this tab (the MCP review): /connect keeps it while the person signs in, so the
 *  sign-in and the sign-up come back to it whichever «دخول» was used. Ten minutes, as the request itself. */
const KEY = 'law.connect';
const LIVES = 10 * 60 * 1000;

export function keepRequest(r: string | null): void {
  try {
    if (r) sessionStorage.setItem(KEY, JSON.stringify({ r, at: Date.now() }));
    else sessionStorage.removeItem(KEY);
  } catch {
    // A private window without storage: the request lives in the page only.
  }
}

export function waitingRequest(): string {
  try {
    const kept = JSON.parse(sessionStorage.getItem(KEY) ?? 'null') as { r: string; at: number } | null;
    return kept && Date.now() - kept.at < LIVES ? kept.r : '';
  } catch {
    return '';
  }
}

/** Where a sign-in goes when nothing asked: a waiting request first, else the account. */
export const afterSignIn = (): string => (waitingRequest() ? '/connect' : '/account');

/** Whether the browser reads the answer's `address` as going, over https (or http to this computer), to the `host`
 *  /connect showed: the server read that host with another parser, and the two must agree before the page leaves. */
export function sameHost(address: string, host: string): boolean {
  try {
    const url = new URL(address);
    const loopback = ['localhost', '127.0.0.1', '[::1]'].includes(url.hostname);
    return Boolean(host) && url.hostname === host && (url.protocol === 'https:' || (url.protocol === 'http:' && loopback));
  } catch {
    return false;
  }
}
