import { useSyncExternalStore } from 'react';

/** What the reader follows on this device (R13 of the for-everyone review): a law, an article or a life topic, with no
 *  account. Each keeps the changes the reader has seen, by their keys, so «جديد» means new to them, not recent.
 *  localStorage: a private window keeps them for the visit only. */
export type Followed = {
  path: string;
  kind: 'text' | 'article' | 'topic' | 'reform' | 'place' | 'where';
  name: { ar: string; fr: string };
  article?: string;
  since: string;
  seen: string[];
};

export const KEY = 'law.follows';
const NONE: Followed[] = [];
let items: Followed[] | null = null;
const listeners = new Set<() => void>();

function read(): Followed[] {
  if (items) return items;
  try {
    const kept: unknown = JSON.parse(localStorage.getItem(KEY) ?? '[]');
    items = Array.isArray(kept) ? (kept as Followed[]) : [];
  } catch {
    items = [];
  }
  return items;
}

function write(next: Followed[]) {
  items = next;
  try {
    localStorage.setItem(KEY, JSON.stringify(next));
  } catch {
    // Storage refused: followed for this visit only.
  }
  listeners.forEach((l) => l());
}

export const follow = (f: Followed) => write([f, ...read().filter((x) => x.path !== f.path)]);
export const unfollow = (path: string) => write(read().filter((x) => x.path !== path));
export function markSeen(seen: Record<string, string[]>) {
  write(read().map((f) => (seen[f.path] ? { ...f, seen: [...new Set([...f.seen, ...seen[f.path]])] } : f)));
}

const subscribe = (l: () => void) => {
  listeners.add(l);
  return () => listeners.delete(l);
};

export function useFollows(): Followed[] {
  return useSyncExternalStore(subscribe, read, () => NONE);
}
