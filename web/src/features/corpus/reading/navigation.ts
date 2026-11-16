import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { leaveSheet } from '@/shared/components/dismiss';

/** Goes to an article of the text: there at once when it is on the page, its address kept for sharing; `query` a
 *  search's words to light there (`?hl=`, HM33). */
export function useGoTo(textPath: string) {
  const navigate = useNavigate();
  return (eid: string, query = '') => {
    document.getElementById(eid)?.scrollIntoView({ block: 'start' });
    // From the phone's outline drawer, its history entry goes first (PX15); then focus lands on the article itself, not
    // back on «الفهرس» (PX25).
    leaveSheet(() => {
      navigate(`${textPath}/${eid}${query}`, { replace: true });
      let tries = 0;
      const focus = () => {
        const b = document.getElementById(eid)?.querySelector<HTMLElement>('h2 button, h3 button');
        if (b) b.focus({ preventScroll: true });
        else if (tries++ < 30) window.setTimeout(focus, 100); // loaded around it first when it was not on the page
      };
      window.setTimeout(focus, 80);
    });
  };
}

/** Whether the screen matches a media query, kept current: `useMedia('(min-width: 64rem)')` is a desk. */
export function useMedia(query: string): boolean {
  const [on, setOn] = useState(() => typeof window !== 'undefined' && window.matchMedia(query).matches);
  useEffect(() => {
    const m = window.matchMedia(query);
    const change = () => setOn(m.matches);
    m.addEventListener('change', change);
    return () => m.removeEventListener('change', change);
  }, [query]);
  return on;
}

export const icon = { width: 18, height: 18, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 1.8,
                      strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const, 'aria-hidden': true };
