import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { NavLink, useLocation } from 'react-router-dom';
import { useTalkInBar } from '@/features/accounts/registration';

/** While a law is read (its address starts «/ma/»), scrolling down slides the bar away and scrolling up, the top or
 *  the end bring it back (N8 of the read-and-trusted review: with the reading bar it held 110 of a phone's 844 px). */
function useAway(reading: boolean): [boolean, (away: boolean) => void] {
  const [away, setAway] = useState(false);
  useEffect(() => {
    setAway(false);
    if (!reading) return;
    let last = window.scrollY;
    let frame = 0;
    const check = () => {
      frame = 0;
      const y = window.scrollY;
      const end = window.innerHeight + y >= document.documentElement.scrollHeight - 80;
      if (end || y < 120) setAway(false);
      else if (y > last + 12) setAway(true);
      else if (y < last - 12) setAway(false);
      if (Math.abs(y - last) > 12) last = y;
    };
    const soon = () => { if (!frame) frame = requestAnimationFrame(check); };
    window.addEventListener('scroll', soon, { passive: true });
    return () => {
      window.removeEventListener('scroll', soon);
      if (frame) cancelAnimationFrame(frame);
    };
  }, [reading]);
  return [away, setAway];
}

/** A phone's way around (R1 of the for-everyone review), as the apps people use every day: home (where one asks: the
 *  home's box since 25 Oct 2026, with no «اسأل» page, which was the same search), the parts of life, the blog
 *  «قانون بالأرقام» (6 Nov 2026: a tab of its own, or people would miss it), the
 *  library (UX6 of the phone-test review: the shelf, the issues and the words were a footer away), and what the
 *  reader kept, or the conversation once people can write in it. «أنا» and the search are in the header. */
export function BottomBar() {
  const { t } = useTranslation();
  // The fifth place is the conversation once people can write in it and it holds its first hundred posts; until then
  // what the reader kept (C3 of the read-and-trusted review: the discussion held only the demo; C2 of
  // the readers review: open, it held no post in any topic).
  const talking = useTalkInBar();
  const [away, setAway] = useAway(useLocation().pathname.startsWith('/ma/'));
  // Without sliding under reduced motion (and in the prerender, which has no window).
  const still = typeof window === 'undefined' || window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const items: [string, string, React.ReactNode, boolean][] = [
    ['/', t('nav.home'), <HomeIcon key="i" />, true],
    ['/topics', t('nav.topics'), <TopicsIcon key="i" />, false],
    ['/blog', t('nav.numbers'), <NumbersIcon key="i" />, false],
    ['/library', t('nav.library'), <LibraryIcon key="i" />, false],
    talking ? ['/talk', t('nav.talk'), <TalkIcon key="i" />, false] : ['/saved', t('nav.saved'), <SavedIcon key="i" />, false],
  ];
  return (
    <nav aria-label={t('nav.main')} data-noprint
         onFocusCapture={() => setAway(false)}
         style={{ transform: away ? 'translateY(100%)' : 'none', transition: still ? 'none' : 'transform 200ms ease' }}
         className="fixed inset-x-0 bottom-0 z-30 border-t border-rule bg-sheet/95 pb-[env(safe-area-inset-bottom)] backdrop-blur lg:hidden">
      {/* Each place as wide as its word, the rest shared: five French names need 330 of a 360 px phone's width,
          «Bibliothèque» alone 83 px of an even fifth's 72. */}
      <ul className="m-0 flex list-none p-0">
        {items.map(([to, label, icon, end]) => (
          <li key={to} className="flex-auto">
            <NavLink to={to} end={end} className={({ isActive }) =>
              `relative flex h-14 flex-col items-center justify-center gap-0.5 whitespace-nowrap text-meta no-underline ${isActive ? 'font-semibold text-stamp' : 'text-ink-soft hover:text-ink'}`}>
              {icon}
              {label}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  );
}

const icon = { width: 22, height: 22, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 1.8,
               strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const, 'aria-hidden': true };
const HomeIcon = () => <svg {...icon}><path d="M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6h-6v6H4a1 1 0 0 1-1-1z" /></svg>;
// The topics are doors (U1 of the Moroccan-design review): the horseshoe arch, its opening narrower than its curve.
const TopicsIcon = () => <svg {...icon}><path d="M5.5 21v-8.3a7.5 7.5 0 1 1 13 0V21M3.5 21h17" /></svg>;
const TalkIcon = () => <svg {...icon}><path d="M4 5h11a2 2 0 0 1 2 2v6a2 2 0 0 1-2 2H9l-4 3v-3H4a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2z" /><path d="M19 9a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2v2l-3-2h-3" /></svg>;
// The blog's numbers: three bars on their baseline, the way its posts draw a count.
const NumbersIcon = () => <svg {...icon}><path d="M3.5 20.5h17M5 18v-6h3.4v6zm5.3 0V5h3.4v13zm5.3 0V9h3.4v9z" /></svg>;
const SavedIcon = () => <svg {...icon}><path d="M6 4h12v16l-6-4-6 4V4Z" /></svg>;
// The library as books on a shelf (the shelf of «/codes» is spines).
const LibraryIcon = () => <svg {...icon}><path d="M4 4h4v16H4zM10 4h4v16h-4z" /><path d="m16.2 4.6 3.8-1 3.1 15.4-3.8 1z" transform="translate(-1.6 .6)" /></svg>;
