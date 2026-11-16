// The site in an assistant, end to end in a real browser (the MCP review, 3 Nov 2026): the MCP server answers without
// an account; an assistant that signs in anyway registers, the person signs in on /connect, sees who asks and approves;
// the code comes back to the assistant's loopback address and is exchanged for a token the server reads; the person ends
// the connection from the account's settings and its refresh token stops working.
// Needs Django (with REGISTRATION_OPEN), law-mcp and Vite proxying /api, /oauth, /.well-known and /mcp:
//   LAW_E2E_USER=<username> LAW_E2E_PASSWORD=<password> BASE_URL=http://localhost:5190 npm run e2e:connect   (SHOTS=<dir> for screenshots)
// The account must have a proven email.
import assert from 'node:assert/strict';
import { createHash, randomBytes } from 'node:crypto';
import { chromium } from 'playwright';

const base = process.env.BASE_URL ?? 'http://localhost:5190';
const username = process.env.LAW_E2E_USER;
const password = process.env.LAW_E2E_PASSWORD;
assert.ok(username && password, 'LAW_E2E_USER and LAW_E2E_PASSWORD: an account with a proven email');
const shots = process.env.SHOTS;
const shot = async (page, name, fullPage = false) => {
  if (shots) await page.screenshot({ path: `${shots}/${name}.png`, fullPage });
};
const b64url = (buf) => buf.toString('base64').replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
const callback = 'http://127.0.0.1:33418/callback';

async function json(path, init) {
  const r = await fetch(`${base}${path}`, init);
  return { status: r.status, headers: r.headers, body: r.status === 204 ? null : await r.json().catch(() => null) };
}

async function mcp(token, method, params = {}) {
  const r = await fetch(`${base}/mcp`, {
    method: 'POST',
    headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}), 'Content-Type': 'application/json',
               Accept: 'application/json, text/event-stream', 'MCP-Protocol-Version': '2025-06-18' },
    body: JSON.stringify({ jsonrpc: '2.0', id: 1, method, params }),
  });
  return { status: r.status, body: r.status === 200 ? await r.json() : await r.text() };
}

// Open to everyone (MCP_AUTH 'open', since 3 Nov 2026): a call without an account is answered.
const anonymous = await mcp('', 'tools/list');
assert.equal(anonymous.status, 200);
// The sign-in stays advertised, for an assistant that signs in anyway.
const resource = (await json('/.well-known/oauth-protected-resource/mcp')).body;
const server = (await json('/.well-known/oauth-authorization-server')).body;
assert.equal(server.client_id_metadata_document_supported, true);

// A client that registers (the MCP Inspector's way), with PKCE.
const reg = await json('/oauth/register', { method: 'POST', headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ client_name: 'Law e2e', redirect_uris: [callback], token_endpoint_auth_method: 'none' }) });
assert.equal(reg.status, 201);
const clientId = reg.body.client_id;
const verifier = b64url(randomBytes(40));
const challenge = b64url(createHash('sha256').update(verifier).digest());
const authorize = `${base}/oauth/authorize?` + new URLSearchParams({
  response_type: 'code', client_id: clientId, redirect_uri: callback, code_challenge: challenge,
  code_challenge_method: 'S256', state: 'e2e-state', scope: 'law:read', resource: resource.resource,
});

const browser = await chromium.launch();
const errors = [];
try {
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await ctx.newPage();
  page.on('pageerror', (e) => errors.push(String(e)));
  let landed = '';
  await page.route('http://127.0.0.1:33418/**', (route) => { landed = route.request().url(); return route.fulfill({ body: 'ok' }); });

  // Not signed in: who asks, then sign in, and back to the same request.
  await page.goto(authorize);
  await page.waitForURL('**/connect');
  await page.getByText('Law e2e يطلب قراءة «قانون» باسم حسابك').waitFor();
  await page.getByText('برنامج يعمل على هذا الحاسوب').waitFor();          // a loopback redirect is warned about
  await shot(page, '1-connect-signed-out-ar');
  await page.getByRole('link', { name: 'دخول' }).last().click();
  await page.waitForURL('**/login');
  await page.getByLabel('اسم المستخدم أو البريد الإلكتروني', { exact: true }).fill(username);
  await page.getByLabel('كلمة السر', { exact: true }).fill(password);
  await page.getByRole('button', { name: 'دخول' }).last().click();
  await page.waitForURL('**/connect');
  await page.getByRole('button', { name: 'سماح' }).waitFor();
  await shot(page, '2-connect-consent-ar');
  await page.getByRole('button', { name: 'سماح' }).click();
  for (let i = 0; i < 50 && !landed; i += 1) await page.waitForTimeout(100);
  const back = new URL(landed);
  assert.equal(back.searchParams.get('state'), 'e2e-state');
  assert.equal(back.searchParams.get('iss'), server.issuer);

  // The code for a pair, then the MCP server answers with it.
  const pair = await json('/oauth/token', { method: 'POST', headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({ grant_type: 'authorization_code', code: back.searchParams.get('code'), client_id: clientId,
                                redirect_uri: callback, code_verifier: verifier, resource: resource.resource }) });
  assert.equal(pair.status, 200);
  const token = pair.body.access_token;
  const init = await mcp(token, 'initialize', { protocolVersion: '2025-06-18', capabilities: {},
                                                clientInfo: { name: 'e2e', version: '1' } });
  assert.equal(init.status, 200);
  assert.match(init.body.result.instructions, /Bulletin officiel/);
  const listed = await mcp(token, 'tools/list');
  assert.deepEqual(listed.body.result.tools.map((t) => t.name), ['search', 'fetch', 'read_articles', 'check_references', 'get_bulletin']);
  const fetched = await mcp(token, 'tools/call', { name: 'fetch', arguments: { id: '/ma/loi/65-99/art_51' } });
  const item = JSON.parse(fetched.body.result.content[0].text);
  assert.equal(item.id, '/ma/loi/65-99/art_51');
  console.log('fetch:', item.title, '·', item.metadata.status, '·', item.metadata.version?.source);
  const found = await mcp(token, 'tools/call', { name: 'search', arguments: { query: 'التعويض عن الإخطار' } });
  const results = JSON.parse(found.body.result.content[0].text).results;
  assert.ok(results.length > 0);
  console.log('search:', results.slice(0, 3).map((r) => r.title).join(' | '));

  // The account's settings list the connection; ending it ends the token (the server, open, then answers it as anyone).
  // /ai links to /account/settings#apps; the old /account#apps leads there.
  await page.goto(`${base}/account#apps`);
  await page.waitForURL('**/account/settings#apps');
  await page.locator('#apps').getByText('Law e2e').waitFor();
  await page.locator('#apps').scrollIntoViewIfNeeded();
  await shot(page, '3-account-apps-ar');
  await page.locator('#apps').getByRole('button', { name: 'فصل' }).first().click();
  await page.locator('#apps').getByText('لا مساعد متصل بحسابك.').waitFor();
  const refreshed = await json('/oauth/token', { method: 'POST', headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({ grant_type: 'refresh_token', refresh_token: pair.body.refresh_token, client_id: clientId }) });
  assert.equal(refreshed.body.error, 'invalid_grant');

  // /ai on a phone, in French.
  const phone = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const p = await phone.newPage();
  p.on('pageerror', (e) => errors.push(String(e)));
  await p.goto(`${base}/login`);
  await p.evaluate(() => localStorage.setItem('law.lang', 'fr'));
  await p.goto(`${base}/ai`);
  await p.getByRole('heading', { name: '3adala dans ChatGPT, Claude et Gemini' }).waitFor();
  assert.equal(await p.evaluate(() => document.documentElement.scrollWidth), 390);
  await shot(p, '4-ai-phone-fr', true);
  await p.goto(`${base}/connect#error=redirect`);
  await p.getByText("L'adresse de retour de cette demande").waitFor();
  await shot(p, '5-connect-refused-phone-fr');
  assert.deepEqual(errors, []);
  console.log('connect e2e: ok');
} finally {
  await browser.close();
}
