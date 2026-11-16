import { lazy } from 'react';
import { useLocation } from 'react-router-dom';

const DiscussionPage = lazy(() => import('./DiscussionPage'));
const QuestionsPage = lazy(() => import('./QuestionsPage'));
const TalkPage = lazy(() => import('./TalkPage'));
const PlacePage = lazy(() => import('./PlacePage'));
const PostPage = lazy(() => import('./PostPage'));
const PersonPage = lazy(() => import('./PersonPage'));
const ReviewPage = lazy(() => import('./ReviewPage'));
const RulesPage = lazy(() => import('./RulesPage'));
const PrivacyPage = lazy(() => import('./PrivacyPage'));
const LettersStopPage = lazy(() => import('./LettersStopPage'));

/** The discussion's pages behind one entry in the app's routes: the app's first load carries one import, not eight.
 *  /talk, /talk/<topic>, /talk/<topic>/<post>, /discussion/<article address>, /questions, /people/:username, /rules,
 *  /privacy, /review, /letters/stop. */
export default function DiscussionRoutes() {
  const { pathname } = useLocation();
  if (pathname.startsWith('/discussion/')) return <DiscussionPage />;
  if (pathname.startsWith('/people/')) return <PersonPage />;
  if (pathname === '/questions') return <QuestionsPage />;
  if (pathname === '/talk') return <TalkPage />;
  if (/^\/talk\/[^/]+\/\d+\/?$/.test(pathname)) return <PostPage />;
  if (pathname.startsWith('/talk/')) return <PlacePage />;
  if (pathname === '/review') return <ReviewPage />;
  if (pathname === '/privacy') return <PrivacyPage />;
  if (pathname === '/letters/stop') return <LettersStopPage />;
  return <RulesPage />;
}
