/** «محفوظاتي» and the kept families lived in a database named after the project's first name. Once per device they are
 *  copied into today's database and the old one is deleted, so a rename loses nobody's articles. A device that never
 *  had the old database gets an empty one for a moment, deleted the same way. Remove this file, and its call in
 *  saved.ts, after 15 May 2027. */
const OLD = 'matn';
const DONE = 'law.saved.moved';

function settled<T>(req: IDBRequest<T>): Promise<T> {
  return new Promise((resolve, reject) => {
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

export async function moveSaved(open: () => Promise<IDBDatabase>): Promise<void> {
  if (localStorage.getItem(DONE) !== null) return;
  const old = await settled(indexedDB.open(OLD));
  try {
    const target = await open();
    for (const name of Array.from(old.objectStoreNames)) {
      if (!target.objectStoreNames.contains(name)) continue;
      const rows = await settled(old.transaction(name, 'readonly').objectStore(name).getAll() as IDBRequest<Record<string, unknown>[]>);
      if (!rows.length) continue;
      const tx = target.transaction(name, 'readwrite');
      const store = tx.objectStore(name);
      const done = new Promise<void>((resolve, reject) => {
        tx.oncomplete = () => resolve();
        tx.onerror = tx.onabort = () => reject(tx.error);
      });
      // What the device kept since the rename wins over the old copy of the same article.
      const have = new Set((await settled(store.getAllKeys())).map(String));
      for (const row of rows) if (!have.has(String(row[store.keyPath as string]))) store.put(row);
      await done;
    }
  } finally {
    old.close();
  }
  localStorage.setItem(DONE, '1');
  // Not waited for: another tab still holding the old database would keep this one from showing what it has.
  indexedDB.deleteDatabase(OLD);
}
