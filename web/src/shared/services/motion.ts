import { flushSync } from 'react-dom';

/** Motion that shows where you went (U7 of the Moroccan-design review): three moments only, a door that grows into
 *  its topic's window, an article's number that becomes its discussion's, a result's label that becomes its article's.
 *  The browser's view transitions; nothing under reduced motion or where the browser has none. The topic tools' kit
 *  (topics/kit/motion.ts) builds on the same two helpers. */

export const reducedMotion = (): boolean =>
  typeof window !== 'undefined' && Boolean(window.matchMedia?.('(prefers-reduced-motion: reduce)').matches);

const HAPTICS = 'law.haptics';

/** A short tick under the finger on Android (K5 of the road tools review: on unless the reader turns it off, never under
 *  reduced motion). Other phones have no vibration API and feel nothing. */
export function tick(ms = 6) {
  if (typeof navigator === 'undefined' || !('vibrate' in navigator) || reducedMotion()) return;
  try { if (localStorage.getItem(HAPTICS) === 'off') return; } catch { /* private window: on */ }
  try { navigator.vibrate(ms); } catch { /* refused */ }
}

type Transition = { finished: Promise<void> };
type ViewTransitionDoc = Document & { startViewTransition?: (update: () => Promise<void> | void) => Transition };

/** The element of the page being opened that `name` lands on: `data-vt={name}` and that view-transition-name. */
export const landing = (name: string) => ({ 'data-vt': name, style: { viewTransitionName: name } });

/** Opens `to` from `from`: `from` takes `name`, the new page is drawn, and the browser moves one into the other once
 *  the element marked `landing(name)` is there (a third of a second at most: a page still loading crossfades). The
 *  wait is a timer: the screen is frozen while the browser waits, and a frozen screen runs no animation frame, so a
 *  page without its landing yet held the old page for the browser's 4 seconds, then cut to the new one. */
export function go(navigate: (to: string) => void, to: string, from: HTMLElement | null | undefined, name: string) {
  const doc = typeof document === 'undefined' ? null : (document as ViewTransitionDoc);
  if (!doc?.startViewTransition || reducedMotion() || !from) { navigate(to); return; }
  from.style.viewTransitionName = name;
  doc.startViewTransition(async () => {
    flushSync(() => navigate(to));
    const until = performance.now() + 350;
    while (!document.querySelector(`[data-vt="${name}"]`) && performance.now() < until)
      await new Promise((r) => window.setTimeout(r, 16));
  });
}
