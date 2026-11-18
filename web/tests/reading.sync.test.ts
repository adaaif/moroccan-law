import assert from 'node:assert/strict';
import { test } from 'node:test';

// A second tab changes shared storage and sends a storage event to this tab.
const values = new Map<string, string>();
const storage = { getItem: (key: string) => values.get(key) ?? null,
  setItem: (key: string, value: string) => { values.set(key, value); } };
const events = new EventTarget();
const dataset: Record<string, string> = {};
Object.defineProperty(globalThis, 'localStorage', { value: storage, configurable: true });
Object.defineProperty(globalThis, 'document', { value: { documentElement: { dataset } }, configurable: true });
Object.defineProperty(globalThis, 'window', { value: Object.assign(events, { localStorage: storage }), configurable: true });
const { useReading } = await import('../src/shared/stores/reading.ts');
function notify(key: string | null, storageArea: unknown = storage) {
  const event = new Event('storage');
  Object.assign(event, { key, storageArea });
  events.dispatchEvent(event);
}

test('another tab updates theme and size, without writing preferences back', () => {
  values.set('law.reading', '{"theme":"dark","size":2}');
  notify('law.reading');
  assert.equal(useReading.getState().theme, 'dark');
  assert.equal(useReading.getState().size, 2);
  assert.equal(dataset.theme, 'dark');
  assert.equal(values.get('law.reading'), '{"theme":"dark","size":2}');
});

test('unrelated keys and session storage do not change reading preferences', () => {
  values.set('law.reading', '{"theme":"light","size":0}');
  notify('another.key');
  notify('law.reading', {});
  assert.equal(useReading.getState().theme, 'dark');
});

test('removal, clear, and malformed values restore automatic defaults', () => {
  for (const value of [undefined, 'null', '{', '{"theme":"invalid","size":9}']) {
    if (value === undefined) values.delete('law.reading');
    else values.set('law.reading', value);
    notify(value === undefined ? null : 'law.reading');
    assert.equal(useReading.getState().theme, 'auto');
    assert.equal(useReading.getState().size, 1);
    assert.equal(dataset.theme, undefined);
  }
});
