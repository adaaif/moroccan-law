import { useSyncExternalStore } from 'react';
import { moveSaved } from './savedMove';

/** «محفوظاتي» (row 14, call C3): articles kept on this device, whole, to read without a connection and without an
 *  account. IndexedDB, one record per article address; nothing leaves the device. */
export type SavedArticle = {
  path: string;
  label: string;
  body: string;
  /** The text it belongs to, named short, and its address. */
  text: string;
  textPath: string;
  /** Where it was printed, as the folio says it. */
  source: string;
  citation: string;
  french: { label: string; body: string } | null;
  savedAt: string;
};

const DB = 'law';
const STORE = 'saved';
let items: SavedArticle[] = [];
let loaded = false;
const listeners = new Set<() => void>();

/** A family kept from the inheritance calculator (IR16 of the inheritance review): its code, which holds the whole
 *  case, under the name the reader gave it. On this device only, like the articles. */
export type SavedFamily = { code: string; name: string; savedAt: string };
const FAMILIES = 'families';

function open(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    // Version 2 adds the families' store beside the articles'.
    const req = indexedDB.open(DB, 2);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains(STORE)) db.createObjectStore(STORE, { keyPath: 'path' });
      if (!db.objectStoreNames.contains(FAMILIES)) db.createObjectStore(FAMILIES, { keyPath: 'code' });
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

async function run<T>(mode: IDBTransactionMode, work: (s: IDBObjectStore) => IDBRequest<T>, store = STORE): Promise<T> {
  const db = await open();
  return new Promise((resolve, reject) => {
    const req = work(db.transaction(store, mode).objectStore(store));
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

/** Once per device, what was kept under the database's first name is brought over before the first read. */
let moving: Promise<void> | null = null;
const brought = () => (moving ??= moveSaved(open).catch(() => { /* the next visit tries again */ }));

function publish(next: SavedArticle[]) {
  items = [...next].sort((a, b) => b.savedAt.localeCompare(a.savedAt));
  listeners.forEach((l) => l());
}

async function load() {
  if (loaded || typeof indexedDB === 'undefined') return;
  loaded = true;
  try {
    await brought();
    publish(await run('readonly', (s) => s.getAll() as IDBRequest<SavedArticle[]>));
  } catch {
    // A private window may refuse IndexedDB: nothing is kept, the page says nothing saved.
  }
}

export async function saveArticle(a: Omit<SavedArticle, 'savedAt'>) {
  const item = { ...a, savedAt: new Date().toISOString() };
  await run('readwrite', (s) => s.put(item));
  publish([item, ...items.filter((x) => x.path !== a.path)]);
}

export async function forgetArticle(path: string) {
  await run('readwrite', (s) => s.delete(path));
  publish(items.filter((x) => x.path !== path));
}

const subscribe = (l: () => void) => {
  listeners.add(l);
  void load();
  return () => listeners.delete(l);
};
const NONE: SavedArticle[] = [];

export function useSaved(): SavedArticle[] {
  return useSyncExternalStore(subscribe, () => items, () => NONE);
}

let families: SavedFamily[] = [];
let familiesLoaded = false;
const familyListeners = new Set<() => void>();
function publishFamilies(next: SavedFamily[]) {
  families = [...next].sort((a, b) => b.savedAt.localeCompare(a.savedAt));
  familyListeners.forEach((l) => l());
}
async function loadFamilies() {
  if (familiesLoaded || typeof indexedDB === 'undefined') return;
  familiesLoaded = true;
  try {
    await brought();
    publishFamilies(await run('readonly', (s) => s.getAll() as IDBRequest<SavedFamily[]>, FAMILIES));
  } catch {
    // A private window may refuse IndexedDB: nothing is kept.
  }
}
export async function saveFamily(code: string, name: string) {
  const record: SavedFamily = { code, name, savedAt: new Date().toISOString() };
  await run('readwrite', (s) => s.put(record), FAMILIES);
  publishFamilies([record, ...families.filter((x) => x.code !== code)]);
}
export async function forgetFamily(code: string) {
  await run('readwrite', (s) => s.delete(code), FAMILIES);
  publishFamilies(families.filter((x) => x.code !== code));
}
/** The families kept on this device, the latest first. */
export function useFamilies(): SavedFamily[] {
  return useSyncExternalStore(
    (l) => { familyListeners.add(l); void loadFamilies(); return () => familyListeners.delete(l); },
    () => families, () => families,
  );
}
