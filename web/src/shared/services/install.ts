import { useSyncExternalStore } from 'react';
import { todayIso } from '@/shared/services/today';

/** «قانون» on the phone's home screen (U8 of the Moroccan-design review): offered once, never on a first visit, after
 *  a reader keeps an article or comes back on a third day. Android hands over its own install prompt
 *  (`beforeinstallprompt`, caught as the page loads); an iPhone gets a line on how. Dismissed or installed, never
 *  again. Nothing here is sent anywhere. */

type Prompt = Event & { prompt: () => Promise<void>; userChoice: Promise<{ outcome: string }> };

const SEEN = 'law.install';
const DAYS = 'law.days';
let prompt: Prompt | null = null;
let due = false;
const listeners = new Set<() => void>();
const changed = () => listeners.forEach((f) => f());

const get = (k: string) => { try { return localStorage.getItem(k); } catch { return null; } };
const set = (k: string, v: string) => { try { localStorage.setItem(k, v); } catch { /* private window */ } };

const installed = () => typeof window !== 'undefined'
  && (window.matchMedia?.('(display-mode: standalone)').matches || (navigator as Navigator & { standalone?: boolean }).standalone === true);
export const iPhone = () => typeof navigator !== 'undefined' && /iphone|ipad|ipod/i.test(navigator.userAgent);

/** Called once at start: catches Android's prompt, and counts the days this phone opened «قانون». */
export function watchInstall() {
  if (typeof window === 'undefined' || installed() || get(SEEN)) return;
  window.addEventListener('beforeinstallprompt', (e) => { e.preventDefault(); prompt = e as Prompt; changed(); });
  window.addEventListener('appinstalled', () => { set(SEEN, 'installed'); due = false; changed(); });
  const today = todayIso();
  const days = (get(DAYS) ?? '').split(',').filter(Boolean);
  if (!days.includes(today)) set(DAYS, [...days, today].slice(-3).join(','));
  if (days.length >= 2 && !days.includes(today)) due = true;
}

/** A reader just kept an article: a good moment to offer. */
export function offerInstall() {
  if (installed() || get(SEEN)) return;
  due = true;
  changed();
}

/** Whether to show the offer now: due, not dismissed, and the phone can take it. */
export function useInstallOffer(): boolean {
  return useSyncExternalStore((f) => { listeners.add(f); return () => listeners.delete(f); },
    () => due && !get(SEEN) && !installed() && (Boolean(prompt) || iPhone()), () => false);
}

export async function install() {
  if (!prompt) return;
  await prompt.prompt();
  const choice = await prompt.userChoice.catch(() => ({ outcome: 'dismissed' }));
  set(SEEN, choice.outcome === 'accepted' ? 'installed' : 'no');
  prompt = null;
  due = false;
  changed();
}

export function dismissInstall() {
  set(SEEN, 'no');
  due = false;
  changed();
}
