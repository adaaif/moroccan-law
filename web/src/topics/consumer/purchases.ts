import type { Purchase } from './rules/receipt';

/** «مشترياتي»: the purchases a reader kept from the receipt tool, on the phone only (nothing is sent), newest first, at
 *  most twelve; the topic's page shows the soonest day among them. */
export type Kept = { id: string; item: string; purchase: Purchase; saved: string };
const KEY = 'law.topic.consumer.purchases';
const MOST = 12;

export function readPurchases(): Kept[] {
  try {
    const v = JSON.parse(localStorage.getItem(KEY) ?? '[]');
    return Array.isArray(v) ? v.filter((x) => x && x.purchase && typeof x.purchase.day === 'string') : [];
  } catch { return []; }
}

export function keepPurchase(item: string, purchase: Purchase, saved: string): Kept[] {
  const next = [{ id: `${Date.now()}`, item, purchase, saved }, ...readPurchases()].slice(0, MOST);
  try { localStorage.setItem(KEY, JSON.stringify(next)); } catch { /* private window */ }
  return next;
}

export function forgetPurchase(id: string): Kept[] {
  const next = readPurchases().filter((x) => x.id !== id);
  try { localStorage.setItem(KEY, JSON.stringify(next)); } catch { /* private window */ }
  return next;
}
