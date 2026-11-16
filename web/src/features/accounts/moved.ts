/* The account's two addresses (16 Nov 2026): /account («أنا», the person) and /account/settings («الإعدادات»); the
   access left the account for /data/access. The old addresses keep leading somewhere: letters already sent and pages
   outside the app link to /account#<section>. No imports, so tests/account.moved.test.ts runs it as it is. */

/** The sections that moved to /account/settings, by their id there. */
export const SETTINGS_PARTS = ['settings', 'signin', 'apps', 'data', 'leave'];

/** Where an old address of the account leads now, or null when the address is right as it is. */
export function movedTo(pathname: string, hash: string): string | null {
  const path = pathname.replace(/\/+$/, '');
  const part = hash.replace(/^#/, '');
  if (path === '/account') {
    if (part === 'access') return '/data/access';
    if (SETTINGS_PARTS.includes(part)) return `/account/settings#${part}`;
    // «أسئلتي ومساهماتي» linked to a section of that name before it was called `mine`.
    if (part === 'discussion') return '/account#mine';
    return null;
  }
  if (path === '/account/settings') return null;
  // An address under /account the site does not know.
  return '/account';
}

/** Which of the two pages an address shows. */
export const tabOf = (pathname: string): 'me' | 'settings' =>
  pathname.replace(/\/+$/, '') === '/account/settings' ? 'settings' : 'me';
