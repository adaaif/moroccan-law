import { test } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';

// The app's API wrapper (src/shared/services/api.ts) when the access token has expired and the refresh is answered:
// only the server refusing the token itself ends the session.
const src = new URL('../src/', import.meta.url).href;
register('data:text/javascript,' + encodeURIComponent(`
export async function resolve(specifier, context, next) {
  return next(specifier.startsWith('@/') ? ${JSON.stringify(src)} + specifier.slice(2) + '.ts' : specifier, context);
}`));

const { api, ApiError } = await import('../src/shared/services/api.ts');
const { useSession } = await import('../src/shared/stores/session.ts');

/** The server: every signed-in call says the access token expired; the refresh answers `refresh`. */
function serve(refresh: number) {
  globalThis.fetch = (async (input: string) => (input.endsWith('/auth/token/refresh/')
    ? new Response(refresh === 200 ? JSON.stringify({ access: 'new', refresh: 'next' }) : '{}', { status: refresh })
    : new Response('{}', { status: 401 }))) as typeof fetch;
}

for (const status of [429, 502, 503]) {
  test(`a refresh answered ${status} keeps the session; this call fails`, async () => {
    useSession.getState().setTokens({ access: 'old', refresh: 'r1' });
    serve(status);
    await assert.rejects(api('/auth/me/'), ApiError);
    assert.deepEqual(useSession.getState().tokens, { access: 'old', refresh: 'r1' });
    assert.equal(useSession.getState().ended, false);
  });
}

test('a refresh refused (401) ends the session and says so', async () => {
  useSession.getState().setTokens({ access: 'old', refresh: 'r1' });
  serve(401);
  await assert.rejects(api('/auth/me/'), ApiError);
  assert.equal(useSession.getState().tokens, null);
  assert.equal(useSession.getState().ended, true);
});
