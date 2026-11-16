import { Component, lazy, Suspense, useEffect, useLayoutEffect, type ReactNode } from 'react';
import { Route, Routes, useLocation, useNavigationType } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import HomePage from '@/features/corpus/HomePage';
import TextPage, { TextRedirect } from '@/features/corpus/TextPage';
import { BottomBar } from './BottomBar';
import { Header } from './Header';
import { PageSkeleton } from '@/shared/components/ui';
import { loaders } from '@/features/search/loaders';
import { useInstallOffer } from '@/shared/services/install';
import i18n from '@/shared/locales/i18n';
import { blogIndex, blogPost, issuePage, topicArea, topicPage, topicsPage } from './landing';

// The home and a text load with the app (the pages people land on, and the prerendered ones); every other
// screen loads when it is first opened.
const AccountPage = lazy(() => import('@/features/accounts/AccountPage'));
const LoginPage = lazy(() => import('@/features/accounts/LoginPage'));
const RegisterPage = lazy(() => import('@/features/accounts/RegisterPage'));
const GooglePage = lazy(() => import('@/features/accounts/GooglePage'));
const AccountDoors = lazy(() => import('@/features/accounts/AccountDoors'));
const BudgetIndex = lazy(() => import('@/features/budget/BudgetIndex'));
const BudgetPage = lazy(() => import('@/features/budget/BudgetPage'));
const IssuePage = lazy(issuePage);
const IssueQualityPage = lazy(() => import('@/features/corpus/IssueQualityPage'));
const PageViewer = lazy(() => import('@/features/corpus/PageViewer'));
const CheckPage = lazy(() => import('@/features/search/CheckPage'));
const searchPage = () => import('@/features/search/SearchPage');
loaders.searchPage = searchPage;
const SearchPage = lazy(searchPage);
const DataPage = lazy(() => import('@/features/opendata/DataPage'));
const EmbedPage = lazy(() => import('@/features/opendata/EmbedPage'));
const WordsPage = lazy(() => import('@/features/words/WordsPage'));
const SavedPage = lazy(() => import('@/features/saved/SavedPage'));
const CodesPage = lazy(() => import('@/features/shelf/CodesPage'));
const NewPage = lazy(() => import('@/features/corpus/NewPage'));
const IssuesPage = lazy(() => import('@/features/corpus/IssuesPage'));
const SituationsPage = lazy(() => import('@/features/situations/SituationsPage'));
const Discussion = lazy(() => import('@/features/discussion/Routes'));
const TopicsPage = lazy(topicsPage);
const TopicPage = lazy(topicPage);
const TopicArea = lazy(topicArea);
const LibraryPage = lazy(() => import('@/features/corpus/LibraryPage'));
const Places = lazy(() => import('@/features/places/Routes'));
const MePage = lazy(() => import('@/features/me/MePage'));
const FollowingPage = lazy(() => import('@/features/follows/FollowingPage'));
const CorrectionsPage = lazy(() => import('@/features/corrections/CorrectionsPage'));
const AboutPage = lazy(() => import('@/features/opendata/AboutPage'));
const OpenSourcePage = lazy(() => import('@/features/opensource/OpenSourcePage'));
const BlogIndex = lazy(blogIndex);
const BlogPost = lazy(blogPost);
const Footer = lazy(() => import('./Footer'));
const ExplainPage = lazy(() => import('@/features/explain/ExplainPage'));
const WordPage = lazy(() => import('@/features/words/WordPage'));
const NotFound = lazy(() => import('@/features/corpus/NotFound'));
const Constitution = lazy(() => import('@/features/corpus/constitution/ConstitutionRoute'));
// The one offer to install the app (U8), when it is due.
const InstallOffer = lazy(() => import('./InstallOffer'));

/** The bottom bar's places, fetched while the phone has nothing else to do (P17 of the polish review): a tap on a tab
 *  then shows its page at once instead of a skeleton. After the first page, never before it (the first-load budget). */
function useTabsSoon() {
  useEffect(() => {
    // Not on a phone saving data (U16 of the Moroccan-design review), nor on a slow connection, nor while a law is
    // read (N14 of the read-and-trusted review: an article's page fetched search's, the topics' and their covers' code):
    // a tab's page comes when it is opened.
    const link = (navigator as Navigator & { connection?: { saveData?: boolean; effectiveType?: string } }).connection;
    if (link?.saveData || /(^|-)[23]g$/.test(link?.effectiveType ?? '') || window.location.pathname.startsWith('/ma/')) return;
    const go = () => {
      void import('@/features/topics/TopicsPage');
      // The home's twelve doors open a topic's page: its code waits here, its answer comes as the finger lands.
      void topicPage();
      void searchPage();
      void import('@/features/discussion/Routes');
      void import('@/features/me/MePage');
    };
    const idle = (window as Window & { requestIdleCallback?: (f: () => void) => number }).requestIdleCallback;
    const id = idle ? idle(go) : window.setTimeout(go, 2500);
    return () => { if (!idle) window.clearTimeout(id); };
  }, []);
}

/** A page opened by a link starts at its top (the library's tools opened where the library had been scrolled to, at its
 *  bottom). The back button keeps the browser's own place, and an address with a #anchor its article. Only a new path
 *  counts: a tool that keeps its inputs in the address stays where it is. Before the page's own effects (a layout
 *  effect), so a law sent to one of its articles (the outline, ‹ › of a search's marks, a link in the law) scrolls there
 *  after it: it landed back at the law's top. */
function useTopOnNewPage() {
  const { pathname, hash } = useLocation();
  const how = useNavigationType();
  useLayoutEffect(() => {
    if (how !== 'POP' && !hash) window.scrollTo(0, 0);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pathname]);
}

export default function App() {
  const { t } = useTranslation();
  useTabsSoon();
  useTopOnNewPage();
  const offer = useInstallOffer();
  const { pathname } = useLocation();
  // An embedded article (another site's iframe) is the article alone.
  if (pathname.startsWith('/embed/')) {
    return (
      <Suspense fallback={null}>
        <EmbedPage />
      </Suspense>
    );
  }
  return (
    <div className="flex min-h-screen flex-col bg-paper">
      <a href="#content" className="sr-only focus:not-sr-only focus:absolute focus:start-3 focus:top-3 focus:z-50 focus:rounded-lg focus:bg-sheet focus:px-4 focus:py-2">
        {t('nav.skip')}
      </a>
      <Header />
      <div id="content" tabIndex={-1} className="outline-none" />
      {/* The page holds a screen: the footer's code often arrives before a page's answer, and the footer was painted on
          the first screen, then thrown down when the content came (layout shift 0.3 to 0.6 on /bo, /codes, /places,
          /corrections and /talk: RD16 of the readers review, 9 Nov 2026). */}
      <div className="flex min-h-svh flex-col">
      <Failed path={pathname}>
      <Suspense fallback={<div className="mx-auto w-full max-w-6xl px-4 pb-14 pt-6 sm:px-6 sm:pt-10"><PageSkeleton /></div>}>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/bo/:edition/:number" element={<IssuePage />} />
          <Route path="/bo/:edition/:number/quality" element={<IssueQualityPage />} />
          <Route path="/ma/*" element={<TextPage />} />
          <Route path="/constitution/*" element={<Constitution />} />
          <Route path="/texts/:id" element={<TextRedirect />} />
          <Route path="/check" element={<CheckPage />} />
          <Route path="/pages/:documentId/:index" element={<PageViewer />} />
          <Route path="/search" element={<SearchPage />} />
          <Route path="/words" element={<WordsPage />} />
          <Route path="/words/:slug" element={<WordPage />} />
          <Route path="/explain/*" element={<ExplainPage />} />
          <Route path="/saved" element={<SavedPage />} />
          <Route path="/codes" element={<CodesPage />} />
          <Route path="/new" element={<NewPage />} />
          <Route path="/bo" element={<IssuesPage />} />
          <Route path="/situations" element={<SituationsPage />} />
          <Route path="/situations/:slug" element={<SituationsPage />} />
          <Route path="/topics" element={<TopicsPage />} />
          <Route path="/topics/:slug" element={<TopicPage />} />
          <Route path="/topics/:slug/*" element={<TopicArea />} />
          {/* A followed commune (the land review, M10) opens the land's finder on it. */}
          <Route path="/places" element={<Places />} />
          <Route path="/places/:place" element={<Places />} />
          <Route path="/library" element={<LibraryPage />} />
          <Route path="/me" element={<MePage />} />
          <Route path="/me/following" element={<FollowingPage />} />
          <Route path="/corrections" element={<CorrectionsPage />} />
          <Route path="/data/*" element={<DataPage />} />
          <Route path="/about" element={<AboutPage />} />
          <Route path="/open-source" element={<OpenSourcePage />} />
          <Route path="/blog" element={<BlogIndex />} />
          <Route path="/blog/:slug" element={<BlogPost />} />
          {['/discussion/*', '/talk/*', '/questions', '/people/:username', '/rules', '/privacy', '/review', '/letters/stop'].map((path) => (
            <Route key={path} path={path} element={<Discussion />} />
          ))}
          <Route path="/budget" element={<BudgetIndex />} />
          <Route path="/budget/:year" element={<BudgetPage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route path="/auth/google" element={<GooglePage />} />
          {['/forgot', '/reset', '/connect', '/ai'].map((path) => <Route key={path} path={path} element={<AccountDoors />} />)}
          <Route path="/account/*" element={<AccountPage />} />
          {/* An address the site does not know says so (P1 of the polish review); it used to go home without a word. */}
          <Route path="*" element={<NotFound />} />
        </Routes>
      </Suspense>
      </Failed>
      </div>
      {/* Below the page, after it: the footer's code comes with the page's other parts, not before them. */}
      <Suspense fallback={null}><Footer /></Suspense>
      {offer ? <Suspense fallback={null}><InstallOffer /></Suspense> : null}
      <BottomBar />
    </div>
  );
}

/** A page whose file could not load (offline, or a build replaced twice in a minute): said, with a way to load it again,
 *  where React had left a blank page (PX5 of the where-it-trips review). */
class Failed extends Component<{ children: ReactNode; path: string }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  // A page that broke is what the measures' app.error is for: React keeps an error a boundary caught from the window, so
  // it is reported there as one no one caught.
  componentDidCatch(error: unknown) { window.reportError?.(error); }
  // Another address is another page: it is tried.
  componentDidUpdate(before: { path: string }) { if (before.path !== this.props.path && this.state.failed) this.setState({ failed: false }); }
  render() {
    if (!this.state.failed) return this.props.children;
    return (
      <div className="mx-auto flex w-full max-w-6xl flex-col items-start gap-3 px-4 py-10 sm:px-6">
        <p className="m-0 text-lead font-semibold">{i18n.t('app.failed')}</p>
        <button type="button" onClick={() => window.location.reload()} className="min-h-11 rounded-control bg-stamp px-5 font-medium text-on-stamp">
          {i18n.t('app.reload')}
        </button>
      </div>
    );
  }
}

