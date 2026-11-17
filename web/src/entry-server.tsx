import { QueryClient, QueryClientProvider, type QueryKey } from '@tanstack/react-query';
import { renderToString } from 'react-dom/server';
import { prerenderToNodeStream } from 'react-dom/static';
import { StaticRouter } from 'react-router-dom';
import App from '@/app/App';
import { drawn } from '@/shared/services/title';
import '@/shared/locales/i18n';

/** The prerender's renderer (scripts/prerender.mjs): a page of the app at `url`, its queries answered from
 *  `seed` ([query key, data] pairs), as HTML. The browser then mounts the app afresh over it (main.tsx uses
 *  createRoot, not hydrate): the HTML is for the first paint, search engines and link previews. */
export function render(url: string, seed: [unknown[], unknown][]): string {
  const client = new QueryClient({ defaultOptions: { queries: { staleTime: Infinity, retry: false } } });
  for (const [key, data] of seed) client.setQueryData(key, data);
  return renderToString(
    <QueryClientProvider client={client}>
      <StaticRouter location={url}>
        <App />
      </StaticRouter>
    </QueryClientProvider>,
  );
}

/** A landing page's first screen (HM2 and C1 «landing» of the hard-moment review: the home, the topics, their
 *  journeys, tools and pages, the blog): rendered again until it stops asking, each pass fetching the answers the last
 *  one asked for (through the page's own query functions, `fetch` pointed at the API by the caller); React's prerender
 *  waits for the pages that load apart. Returns the HTML, the answers it used (the page carries them so the browser
 *  starts from them, main.tsx), what failed, and the name the page gave itself (usePageTitle), which heads the pages
 *  the caller knows no name for. Only the queries a page asks for while rendering, never a disabled one. */
export async function renderLanding(url: string): Promise<{ html: string; seed: [QueryKey, unknown][]; errors: string[]; title: string }> {
  const client = new QueryClient({ defaultOptions: { queries: { staleTime: Infinity, retry: false } } });
  const tried = new Set<string>();
  drawn.title = '';
  let html = '';
  let errors: string[] = [];
  for (let pass = 0; pass < 8; pass++) {
    errors = [];
    const { prelude } = await prerenderToNodeStream(
      <QueryClientProvider client={client}>
        <StaticRouter location={url}>
          <App />
        </StaticRouter>
      </QueryClientProvider>,
      { onError: (e) => { errors.push(e instanceof Error ? `${e.message} ${e.stack?.split('\n')[1]?.trim() ?? ''}` : String(e)); } },
    );
    html = '';
    for await (const chunk of prelude as unknown as AsyncIterable<string | Uint8Array>) html += typeof chunk === 'string' ? chunk : new TextDecoder().decode(chunk as Uint8Array);
    const asked = client.getQueryCache().getAll().filter((q) => {
      const on = (q.options as { enabled?: unknown }).enabled;
      return q.state.status === 'pending' && !tried.has(q.queryHash) && q.options.queryFn && on !== false && typeof on !== 'function';
    });
    if (!asked.length) break;
    for (const q of asked) tried.add(q.queryHash);
    await Promise.all(asked.map((q) => client.prefetchQuery({ queryKey: q.queryKey, queryFn: q.options.queryFn as () => Promise<unknown> })));
  }
  // An answer that failed would be drawn as its error into the page: the page is then left to the browser.
  for (const q of client.getQueryCache().getAll()) if (q.state.status === 'error') errors.push(`${JSON.stringify(q.queryKey)}: ${String(q.state.error)}`);
  const seed = client.getQueryCache().getAll().filter((q) => q.state.status === 'success')
    .map((q) => [q.queryKey, q.state.data] as [QueryKey, unknown]);
  return { html, seed, errors, title: drawn.title };
}
