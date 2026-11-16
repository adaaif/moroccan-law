import { lazy, Suspense, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { SearchBox } from '@/features/search/SearchBox';
import { Button, Card, Page } from '@/shared/components/ui';
import { chipClass } from '@/shared/components/buttons';
import { note } from '@/shared/analytics/note';
import { ApiError } from '@/shared/services/api';
import { usePageTitle } from '@/shared/services/title';
import '@/shared/locales/pages';

const ReadingLimit = lazy(() => import('./ReadingLimit'));

/** «لم نجد هذه الصفحة» (P1, P17 of the polish review): what may have happened, the search box, and the ways in. An
 *  address the site does not know used to send the reader home without a word; a missing text was one red line. */
export default function NotFound({ inPage = false }: { inPage?: boolean }) {
  const { t } = useTranslation();
  usePageTitle([t('pages:missing.title')]);
  // A crawler is told too (IX2 of the search-engines review): nginx answers an address it does not know with the app and a 200,
  // and Google reads this once the app has run (a law's address that leads nowhere is a 404 from Django already).
  useEffect(() => {
    const tag = document.createElement('meta');
    tag.name = 'robots';
    tag.content = 'noindex';
    document.head.appendChild(tag);
    return () => tag.remove();
  }, []);
  // A link that leads nowhere, counted by this address (the analytics review): the engine says whether it was on this
  // site or which site it was on.
  useEffect(() => note('page.missing'), []);
  const card = (
    <Card className="flex max-w-[45rem] flex-col gap-4">
      <MissingArt />
      <h1 className="m-0 text-h2 font-bold">{t('pages:missing.title')}</h1>
      <p className="m-0 max-w-[52ch] text-lead text-ink-soft">{t('pages:missing.lead')}</p>
      <SearchBox />
      <p className="m-0 text-body text-ink-soft">{t('pages:missing.start')}</p>
      <div className="flex flex-wrap gap-2">
        <Link to="/topics" className={chipClass()}>{t('nav.topics')}</Link>
        <Link to="/library" className={chipClass()}>{t('nav.library')}</Link>
        <Link to="/" className={chipClass()}>{t('pages:missing.home')}</Link>
      </div>
    </Card>
  );
  return inPage ? card : <Page width="reading">{card}</Page>;
}

/** Whether an error is the day's reading reached (429 `reading.check` or `reading.limit`), and which. */
function readingCode(error: unknown): 'check' | 'limit' | null {
  if (!(error instanceof ApiError) || error.status !== 429) return null;
  const code = error.errors.find((x) => x.field === 'reading')?.code;
  return code === 'check' || code === 'limit' ? code : null;
}

/** A page that could not load: the not-found page for a 404, else the connection lost, with a way to try again. */
export function LoadError({ error, retry }: { error: unknown; retry: () => void }) {
  const { t } = useTranslation();
  if (error instanceof ApiError && error.status === 404) return <NotFound inPage />;
  const code = readingCode(error);
  if (code) return <Suspense fallback={null}><ReadingLimit code={code} retry={retry} /></Suspense>;
  // A server's answer that failed (5xx) is ours to say, not the reader's connection (HM15 of the hard-moment review).
  const ours = error instanceof ApiError && error.status >= 500;
  return (
    <Card className="flex max-w-[45rem] flex-col items-start gap-3">
      <h1 className="m-0 text-h3 font-bold">{t(ours ? 'pages:missing.serverDown' : 'pages:missing.offline')}</h1>
      <p className="m-0 max-w-[52ch] text-body text-ink-soft">{t(ours ? 'pages:missing.serverDownLead' : 'pages:missing.offlineLead')}</p>
      <Button variant="primary" onClick={retry}>{t('pages:missing.retry')}</Button>
      <Link to="/saved" className="inline-flex min-h-11 items-center text-body font-medium no-underline">{t('nav.saved')}</Link>
    </Card>
  );
}

/** A page torn from a book, drawn small (P19): an empty state's picture, in the stamp's colours. */
function MissingArt() {
  return (
    <svg aria-hidden="true" width="96" height="72" viewBox="0 0 96 72" className="text-stamp">
      <rect x="18" y="8" width="52" height="60" rx="6" className="fill-wash" />
      <path d="M26 22h32M26 31h26M26 40h30" stroke="currentColor" strokeWidth="3" strokeLinecap="round" opacity="0.45" />
      <path d="M70 8v38l-9 6 9 6v10H18" fill="none" stroke="currentColor" strokeWidth="3" strokeLinejoin="round" />
      <circle cx="74" cy="56" r="11" className="fill-sheet" stroke="currentColor" strokeWidth="3" />
      <path d="m82 64 8 8" stroke="currentColor" strokeWidth="3.5" strokeLinecap="round" />
    </svg>
  );
}
