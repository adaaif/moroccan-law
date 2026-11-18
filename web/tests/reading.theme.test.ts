import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import { runInNewContext } from 'node:vm';

const html = readFileSync(new URL('../index.html', import.meta.url), 'utf8');
const bootstrap = html.match(/<script>([\s\S]*?)<\/script>/)?.[1];

test('saved theme applies in the head before the app loads', () => {
  assert.ok(bootstrap, 'an early theme bootstrap is required');
  assert.ok(html.indexOf('<script>') < html.indexOf('</head>'));
  for (const theme of ['light', 'dark']) {
    const dataset: Record<string, string> = {};
    runInNewContext(bootstrap, { document: { documentElement: { dataset } }, localStorage: { getItem: () => JSON.stringify({ theme }) } });
    assert.equal(dataset.theme, theme);
  }
});

test('early theme bootstrap tolerates missing, invalid and inaccessible storage', () => {
  assert.ok(bootstrap);
  for (const value of [null, 'null', '{', '{"theme":"invalid"}', '{"theme":"auto"}']) {
    const dataset = {};
    assert.doesNotThrow(() => runInNewContext(bootstrap, { document: { documentElement: { dataset } }, localStorage: { getItem: () => value } }));
    assert.deepEqual(dataset, {});
  }
  assert.doesNotThrow(() => runInNewContext(bootstrap, { localStorage: { getItem() { throw new Error('blocked'); } } }));
});
