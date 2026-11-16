import { useEffect, useRef, useState } from 'react';
import { reducedMotion } from '@/shared/services/motion';

/** The topic tools' one motion kit (F5 of the road tools review): three durations and one easing, a number that
 *  counts to its new value, a view transition for a step that changes, a light tick under the finger. Every effect
 *  asks the reader's reduced-motion setting first and is instant under it. No library. */
export const MOTION = { fast: 120, base: 220, slow: 480 } as const;
export const EASE = 'cubic-bezier(.2,.7,.2,1)';

export { reducedMotion, tick } from '@/shared/services/motion';

/** The value, counted from the one before over `ms` (eased out); the value itself under reduced motion. */
export function useTween(value: number, ms = 360): number {
  const [shown, setShown] = useState(value);
  const from = useRef(value);
  useEffect(() => {
    if (reducedMotion() || from.current === value) { from.current = value; setShown(value); return; }
    const start = from.current, t0 = performance.now();
    let raf = 0;
    const step = (t: number) => {
      const f = Math.min(1, (t - t0) / ms), e = 1 - Math.pow(1 - f, 3);
      const now = Math.round(start + (value - start) * e);
      from.current = now;
      setShown(now);
      if (f < 1) raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [value, ms]);
  return shown;
}

type ViewTransitionDoc = Document & { startViewTransition?: (update: () => void) => unknown };

/** Runs `update` inside a view transition where the browser has one, so a step or a tab changes as one movement. */
export function transition(update: () => void) {
  const doc = typeof document === 'undefined' ? null : (document as ViewTransitionDoc);
  if (!doc?.startViewTransition || reducedMotion()) { update(); return; }
  doc.startViewTransition(update);
}
