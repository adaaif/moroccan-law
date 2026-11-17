import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import App from '@/app/App';
import { landingCode } from '@/app/landing';
import { languageReady } from '@/shared/locales/i18n';
import { splitAddress } from '@/features/corpus/format';
import { ApiError } from '@/shared/services/api';
import '@/shared/design/app.css';
import '@/shared/stores/reading';
import { measurePageTiming } from '@/shared/services/timing';
import { watchInstall } from '@/shared/services/install';
import { moveOldKeys } from '@/shared/services/oldKeys';
import { hand } from '@/shared/analytics/note';

const queryClient = new QueryClient({
  defaultOptions: {
    // The server's answers are final; only a dropped connection is worth another try.
    // Offline, at once: the page says so instead of a skeleton for the retries' seconds (PX14 of the where-it-trips review).
    queries: { retry: (count, error) => navigator.onLine && !(error instanceof ApiError) && count < 2 },
  },
});

// What this device kept under the project's first name moves to today's names, before anything reads it.
moveOldKeys();

// Android's offer to install, caught as the page loads; the days this phone came (U8).
watchInstall();

// A deploy replaced the build an open tab or the installed app still runs: a page's file is gone, so the new build is
// loaded, once a minute at most (PX5 of the where-it-trips review: the page went blank). Offline, the routes' boundary
// says so instead.
window.addEventListener('vite:preloadError', (e) => {
  try {
    if (Date.now() - Number(sessionStorage.getItem('law.reloaded') ?? 0) < 60_000) return;
    sessionStorage.setItem('law.reloaded', String(Date.now()));
  } catch { return; }
  e.preventDefault();
  window.location.reload();
});

// A prerendered law (scripts/prerender.mjs) already shows its words: the app fetches the same law before it mounts
// over them, so the page goes from the words to the app with no skeleton between (N5 of the read-and-trusted review);
// four seconds at most, then it mounts anyway.
const root = document.getElementById('root')!;
// A prerendered landing page (the home, a topic, a journey, a tool, a post: HM2 of the hard-moment review) carries
// the answers it was drawn from: the app starts from them, and mounts once its page's code has come.
const seed = document.getElementById('seed');
try {
  for (const [key, data] of JSON.parse(seed?.textContent || '[]') as [unknown[], unknown][]) queryClient.setQueryData(key, data);
  // What is open, carried by a page Django or the deploy wrote (HM17): not asked again.
  const flags = document.getElementById('flags')?.textContent;
  if (flags) queryClient.setQueryData(['registration'], JSON.parse(flags));
} catch { /* drawn by the app, as before */ }
// Whether the app may mount: offline, a drawn page whose answer or code could not come keeps its words, and the app
// mounts when the connection comes back (HM27 of the hard-moment review: offline, it replaced them with an error).
const later = new Promise<boolean>((resolve) => setTimeout(() => resolve(true), 4000));
const ready: Promise<boolean> = seed ? Promise.race([landingCode(window.location.pathname).then(() => true, () => navigator.onLine), later])
  : root.hasAttribute('data-prerendered') && window.location.pathname.startsWith('/ma/')
  ? Promise.race([
    import('@/features/corpus/corpus.api').then(({ corpusApi }) => {
      const { textPath, focus } = splitAddress(window.location.pathname);
      const on = new URLSearchParams(window.location.search).get('on') ?? '';
      const key = ['textAt', textPath, on];
      return queryClient.prefetchQuery({ queryKey: key, queryFn: () => corpusApi.textAt(focus ? `${textPath}/${focus}` : textPath, on) })
        .then(() => queryClient.getQueryData(key) !== undefined || navigator.onLine);
    }, () => navigator.onLine),
    later,
  ])
  : Promise.resolve(true);

const mount = () => createRoot(root).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
);
void Promise.all([languageReady, ready]).then(([, ok]) => {
  if (ok || navigator.onLine) mount();
  else window.addEventListener('online', mount, { once: true });
});

// The app opens without a connection, for the articles kept on the device (row 14). Not while developing: a
// worker would serve yesterday's files.
if (import.meta.env.PROD) measurePageTiming();
// What the site counts, never who (shared/analytics): its engine loads when the browser is idle, never in the first load.
if (import.meta.env.PROD) (window.requestIdleCallback ?? setTimeout)(() => void import('@/shared/analytics/engine').then((m) => m.start(hand)));

if (import.meta.env.PROD && 'serviceWorker' in navigator) {
  window.addEventListener('load', () => { void navigator.serviceWorker.register('/sw.js'); });
}
