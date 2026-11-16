import { test } from 'node:test';
import assert from 'node:assert/strict';

// /connect leaves for the assistant's address only when the browser's own reading of it names the host the page showed
// (src/features/accounts/pendingConnect.ts). The server reads the host with Python; these are the browser's readings.
const { sameHost } = await import('../src/features/accounts/pendingConnect.ts');

test('the answer leaves for the host shown', () => {
  assert.equal(sameHost('https://claude.ai/api/mcp/auth_callback?code=x&state=y', 'claude.ai'), true);
  assert.equal(sameHost('http://localhost:3118/callback?code=x', 'localhost'), true);
  assert.equal(sameHost('http://[::1]:5000/cb?code=x', '[::1]'), true);
});

test('an address the browser reads as another host stays here', () => {
  assert.equal(sameHost('https://claude.ai\\@evil.example/cb?code=x', 'evil.example'), false);   // a browser: claude.ai
  assert.equal(sameHost('https://evil.example\\@claude.ai/cb?code=x', 'claude.ai'), false);      // a browser: evil.example
  assert.equal(sameHost('https://claude%2Eai/cb', 'claude%2eai'), false);
  assert.equal(sameHost('https://evil.example/cb', 'claude.ai'), false);
  assert.equal(sameHost('http://evil.example/cb', 'evil.example'), false);                        // http only to this computer
  assert.equal(sameHost('javascript:alert(1)', ''), false);
  assert.equal(sameHost('not an address', 'claude.ai'), false);
});
