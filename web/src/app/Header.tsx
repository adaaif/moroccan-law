import { useQueryClient } from '@tanstack/react-query';
import { lazy, Suspense, useCallback, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, NavLink, useLocation } from 'react-router-dom';
import { useCanTalk, useRegistrationOpen } from '@/features/accounts/registration';
import { applyLanguage } from '@/shared/locales/i18n';
import { ThemeToggle } from './ThemeToggle';
import { useSession } from '@/shared/stores/session';

// A signed-in reader's menu (30 Oct 2026: its face, what is new, a moderator's count) comes after the page (R2, M10).
const UserMenu = lazy(() => import('@/features/discussion/account/UserMenu'));
// The search sheet's code (the home's box and its suggestions) comes on the first tap (UX5).
const SearchSheet = lazy(() => import('./SearchSheet'));
const FollowsDot = lazy(() => import('@/features/follows/FollowsDot'));

/** Whether this device follows anything (R13): only then is the dot's code fetched. */
function following(): boolean {
  try {
    return (localStorage.getItem('law.follows') ?? '[]').length > 2;
  } catch {
    return false;
  }
}

const navLink = ({ isActive }: { isActive: boolean }) =>
  `flex h-11 items-center whitespace-nowrap rounded-control px-2 hover:bg-paper xl:px-3 ${isActive ? 'font-semibold text-stamp' : 'text-ink hover:text-ink'}`;

export function Header() {
  const { t, i18n } = useTranslation();
  const queryClient = useQueryClient();
  const signedIn = useSession((s) => s.tokens !== null);
  // While sign-up is closed nobody new can come in: no «دخول» offered; staff keep /login (N17).
  const registrationOpen = useRegistrationOpen();
  const talking = useCanTalk();
  const other = i18n.language === 'fr' ? 'ar' : 'fr';
  const [searching, setSearching] = useState(false);
  const closeSearch = useCallback(() => setSearching(false), []);
  // The home and the search page have their own box.
  const path = useLocation().pathname;
  const ownBox = path === '/' || path === '/search';
  // The search's box where the row has room for it beside the five places: French names them longer, and «Connexion»
  // takes a box's width (measured 6 Nov 2026: 1,060 px of a 1,024 px row in French).
  const [glass, box] = i18n.language !== 'fr' ? ['lg:hidden', 'lg:flex'] : registrationOpen && !signedIn ? ['', ''] : ['xl:hidden', 'xl:flex'];

  const switchLanguage = () => {
    void applyLanguage(other);
    // A signed-in reader keeps the choice on every device. The accounts' code (19 KB with the password rules) comes
    // only then: a visitor never needs it on the first load (UX5 made room for the search in it).
    if (signedIn) {
      void import('@/features/accounts/accounts.service')
        .then(({ accountsApi, ME_KEY }) => accountsApi.updateMe({ preferred_language: other })
          .then((user) => queryClient.setQueryData(ME_KEY, user)))
        .catch(() => undefined);
    }
  };

  return (
    <header className="border-b border-rule bg-sheet">
      <div className="mx-auto flex max-w-6xl items-center gap-2 px-4 py-2.5 sm:gap-6 sm:px-6">
        {/* The logo: the wordmark «قانون المغرب» on the site's violet (9 Nov 2026, drawn with Gemini, mended and traced:
            public/brand/wordmark.svg), in place of the arch and «ق» beside the name (4 Nov 2026). */}
        <Link to="/" className="inline-flex min-h-11 shrink-0 items-center rounded-control px-1 text-stamp no-underline hover:text-stamp-deep">
          <span className="wordmark h-12" role="img" aria-label="قانون المغرب" />
        </Link>
        {/* The places of the bottom bar (R1 of the for-everyone review), and what is new; below 1,024 px, the bar (6 Nov
            2026: with «بالأرقام» the five places, the search, «أنا» and the language did not fit a tablet's row, and
            the row already ran over at 768 px). Asking is the home's box (25 Oct 2026: the «اسأل» page
            was the same search). */}
        <nav aria-label={t('nav.main')} className="hidden items-center gap-1 text-body lg:flex">
          <NavLink to="/topics" className={navLink}>{t('nav.topics')}</NavLink>
          {/* «قانون بالأرقام» in view (6 Nov 2026: in the header, where people see it). */}
          <NavLink to="/blog" className={navLink}>{t('nav.numbers')}</NavLink>
          {talking ? <NavLink to="/talk" className={navLink}>{t('nav.talk')}</NavLink> : <NavLink to="/saved" className={navLink}>{t('nav.saved')}</NavLink>}
          <NavLink to="/new" className={navLink}>{t('nav.new')}</NavLink>
          <NavLink to="/library" className={navLink}>{t('nav.library')}</NavLink>
        </nav>
        <div className="ms-auto flex items-center gap-0.5 text-body sm:gap-1">
          {/* Search from every page (UX5): a magnifier on a phone, a box's look on a desk. */}
          {ownBox ? null : (
            <>
              <button type="button" onClick={() => setSearching(true)} aria-label={t('nav.search')} aria-haspopup="dialog"
                      className={`flex size-11 items-center justify-center rounded-control text-ink hover:bg-paper ${glass}`}>
                <SearchIcon />
              </button>
              <button type="button" onClick={() => setSearching(true)} aria-haspopup="dialog"
                      className={`hidden h-11 w-48 items-center gap-2 rounded-control border border-field bg-paper px-3 text-ink-soft ${box}`}>
                <SearchIcon />
                <span className="truncate">{t('corpus.searchPlaceholder')}</span>
              </button>
            </>
          )}
          {/* «أنا» in the header on a phone too: the bar's places are the home, the topics, the numbers, the library and
              the conversation (UX6, C1); a signed-in reader's menu holds it. */}
          {signedIn ? null : <NavLink to="/me" aria-label={t('nav.me')} title={t('nav.me')}
                   className={({ isActive }) => `relative flex size-11 items-center justify-center rounded-control hover:bg-paper ${isActive ? 'text-stamp' : 'text-ink hover:text-ink'}`}>
            <svg aria-hidden="true" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
              <circle cx="12" cy="8" r="4" /><path d="M4 21a8 8 0 0 1 16 0" />
            </svg>
            {following() ? <Suspense fallback={null}><FollowsDot /></Suspense> : null}
          </NavLink>}
          <ThemeToggle />
          <button
            type="button"
            lang={other}
            onClick={switchLanguage}
            aria-label={t('nav.switchLanguageLabel')}
            className="h-11 whitespace-nowrap rounded-control px-2 text-ink hover:bg-paper sm:px-3"
            style={{ fontFamily: 'system-ui, sans-serif' }}
          >
            {t('nav.switchLanguage')}
          </button>
          {signedIn ? (
            // The face's room while the menu's code comes (it never holds the first paint).
            <Suspense fallback={<span className="size-11" />}>
              <UserMenu />
            </Suspense>
          ) : registrationOpen ? (
            <Link
              to="/login"
              className="flex h-11 items-center whitespace-nowrap rounded-control px-2 font-semibold text-stamp hover:bg-wash sm:px-3"
            >
              {t('nav.signIn')}
            </Link>
          ) : null}
        </div>
      </div>
      {searching ? <Suspense fallback={null}><SearchSheet onClose={closeSearch} /></Suspense> : null}
    </header>
  );
}

function SearchIcon() {
  return (
    <svg aria-hidden="true" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
      <circle cx="11" cy="11" r="6.5" /><path d="m16 16 4.5 4.5" />
    </svg>
  );
}
