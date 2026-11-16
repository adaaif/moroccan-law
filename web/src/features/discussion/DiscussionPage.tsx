import { useEffect, useRef, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { LawBody } from '@/features/corpus/LawBody';
import { Stamp } from '@/features/corpus/article/Stamp';
import { AR, issueNo, splitLabel } from '@/features/corpus/format';
import { usePageTitle } from '@/shared/services/title';
import { textName } from '@/features/corpus/names';
import { Closed, Composer } from './Composer';
import { HelpNearby } from './HelpNearby';
import { Aside } from './PlacePage';
import { PostCard } from './PostCard';
import { isSensitive } from './sensitive';
import { useCited, useRefreshTalk, type Contribution } from './discussion.api';
import { useNoIndex } from './noindex';
import { errorText, useT } from './strings';
import { PageSkeleton } from '@/shared/components/ui';
import { LoadError } from '@/features/corpus/NotFound';

/**
 * An article and what people wrote about it (C3 of 29 Oct 2026): the article as the text prints it, its margin number
 * and stamp; the posts in the topics that cite it or started from it; and «اسأل على هاد المادة», a post in its text's
 * topic, the article and the words selected in it going with the question. /discussion/ma/loi/67-12/art_34.
 */
export default function DiscussionPage() {
  const { t, i18n } = useT();
  const location = useLocation();
  const navigate = useNavigate();
  const path = location.pathname.replace(/^\/discussion/, '');
  const cited = useCited(path);
  const [tapping, setTapping] = useState(false);
  const refresh = useRefreshTalk();
  const [quote, setQuote] = useState('');
  const [picked, setPicked] = useState('');
  const body = useRef<HTMLDivElement>(null);
  useNoIndex();

  // Words selected inside the article are offered as a quote.
  useEffect(() => {
    const change = () => {
      const s = document.getSelection();
      const words = s?.toString().replace(/\s+/g, ' ').trim() ?? '';
      const inside = s && s.rangeCount > 0 && body.current?.contains(s.getRangeAt(0).commonAncestorContainer);
      setPicked(inside && words.length >= 3 && words.length <= 500 ? words : '');
    };
    document.addEventListener('selectionchange', change);
    return () => document.removeEventListener('selectionchange', change);
  }, []);

  const first = cited.data?.pages[0];

  // A French page names the article in French: «Discussion sur l’article 34», never the Arabic label inside it.
  const heading = first ? (i18n.language === 'fr' ? t('aboutArticle', { number: first.article.number }) : t('about', { label: first.article.label })) : '';
  usePageTitle(first ? [heading, textName(first.text, i18n.language)] : []);

  if (cited.isLoading) return <Shell><PageSkeleton kind="text" /></Shell>;
  if (!first) return <Shell>{cited.error ? <LoadError error={cited.error} retry={() => void cited.refetch()} /> : <PageSkeleton kind="text" />}</Shell>;

  const { article: a, text, writing, version, places } = first;
  const posts = cited.data!.pages.flatMap((p) => p.posts);
  const consolidated = version.consolidation !== 'as_published';
  const [word, number] = splitLabel(a.label);
  const pad = 'px-5 sm:px-10';
  /** After asking: the new post's page. */
  const sent = (made: Contribution) => {
    refresh();
    navigate(made.path ?? places[0].path);
  };
  const canQuote = writing.can || writing.why === 'email.not_proven';
  const quiet = writing.why === 'discussion.closed' && !posts.length;

  return (
    <Shell>
      <div className="-mx-4 bg-sheet sm:mx-0 sm:rounded-card">
        <header className={`flex flex-col gap-2 border-b border-rule-soft pb-5 pt-6 sm:pt-8 ${pad}`}>
          {/* The text by the name people know (P6 of the polish review), its formal title on hover and on its page. */}
          <Link to={`${text.path}/${a.eid}`} title={text.title} dir="auto"
                className="inline-flex min-h-11 max-w-[60ch] items-center self-start text-lead font-medium leading-snug text-ink-soft no-underline hover:text-stamp">
            {textName(text, i18n.language)}
          </Link>
          <h1 className="m-0 text-h1 font-bold leading-tight">{heading}</h1>
        </header>

        <div className={`flex flex-wrap items-start gap-x-12 gap-y-8 pb-10 pt-2 ${pad}`}>
          <div className="flex min-w-0 flex-[999_1_560px] flex-col gap-6">
            {/* The article as a post (R5): its number as a pill, its source, the law's words under the violet rule. */}
            <article className="py-5">
              <div className="mb-3 flex flex-wrap items-center gap-2">
                <span {...AR} data-vt="article-talk" style={{ viewTransitionName: 'article-talk' }} className="inline-flex items-baseline gap-1.5 rounded-full bg-paper px-3.5 py-1.5">
                  {word ? <span className="text-body font-medium">{word}</span> : null}
                  <span className="text-lead font-bold leading-none">{number}</span>
                </span>
                <span>
                  <Stamp issue={text.issue ? issueNo(text.issue, (k) => t(k, { ns: 'translation' })) : null} page={a.page}
                         consolidated={consolidated}
                         to={a.page && a.document_id !== null && a.page_index !== null ? `/pages/${a.document_id}/${a.page_index}?a=${encodeURIComponent(a.label)}` : null} />
                </span>
              </div>
              <div ref={body} className="min-w-0">
                {tapping ? <TapQuote body={a.body} onQuote={setQuote} /> : (
                  <div className="border-s-[3px] border-stamp-line ps-4 sm:ps-5">
                    <LawBody text={a.body} textPath={text.path} className="max-w-[64ch] font-law text-law leading-[1.8]" />
                  </div>
                )}
                <div className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-2 text-meta">
                  <Link to={`${text.path}/${a.eid}`} className="no-underline">{t('readWhole')}</Link>
                  {canQuote ? (
                    <button type="button" onClick={() => setTapping((on) => !on)} aria-pressed={tapping}
                            className={`h-10 rounded-full border px-4 ${tapping ? 'border-stamp bg-wash font-semibold text-stamp' : 'border-rule text-ink hover:border-stamp'}`}>
                      {tapping ? t('composer2.quoteDone') : t('composer2.quoteTap')}
                    </button>
                  ) : null}
                  {picked && canQuote ? (
                    <button type="button" onClick={() => { setQuote(picked); setPicked(''); document.getSelection()?.removeAllRanges(); }}
                            className="inline-flex h-10 items-center gap-2 rounded-full bg-stamp px-4 font-semibold text-on-stamp hover:bg-stamp-deep">
                      {t('composer.quoteThis')}
                    </button>
                  ) : null}
                </div>
              </div>
            </article>

            {isSensitive(path) ? <HelpNearby /> : null}

            <section aria-labelledby="ask-title" className="flex flex-col gap-4 border-t border-rule pt-6">
              <h2 id="ask-title" className="m-0 text-lead font-semibold">{t('talk2.askTitle')}</h2>
              {quiet ? <p className="m-0 rounded-control bg-paper px-4 py-3 text-body">{t('notYet')}</p>
                : canQuote ? (
                  <Composer place={places[0].path} places={places} about={path} label={a.label} writing={writing} quote={quote}
                            onQuote={setQuote} onDone={sent} />
                ) : <Closed why={writing.why} />}
            </section>

            {posts.length ? (
              <section aria-labelledby="cited-title" className="flex flex-col gap-3">
                <h2 id="cited-title" className="m-0 text-lead font-semibold">
                  {t('talk2.citedTitle')} <span className="font-normal text-ink-soft">({t('talk2.posts', { count: first.total })})</span>
                </h2>
                <ol className="m-0 flex list-none flex-col gap-3 p-0">
                  {posts.map((c) => <li key={c.id}><PostCard c={c} label={c.label} besides={path} /></li>)}
                </ol>
                {cited.hasNextPage ? (
                  <button type="button" onClick={() => void cited.fetchNextPage()} disabled={cited.isFetchingNextPage}
                          className="h-11 rounded-control border border-rule px-5 text-body font-medium text-stamp hover:bg-paper">
                    {cited.isFetchingNextPage ? t('loading') : t('talk2.morePosts')}
                  </button>
                ) : null}
              </section>
            ) : null}
            <p className="m-0 border-t border-rule-soft pt-4 text-meta text-ink-soft">{t('disclaimer')}</p>
            {cited.error ? <p role="alert" className="text-repealed">{errorText(t, cited.error)}</p> : null}
          </div>
          <Aside />
        </div>
      </div>
    </Shell>
  );
}

/** Quoting with a thumb (W5): the article's sentences become buttons; a tap quotes one, a tap on the next or the
 *  one before widens the quote. The quote stays the article's own words, in their order. */
function TapQuote({ body, onQuote }: { body: string; onQuote: (q: string) => void }) {
  const { t } = useT();
  const sentences = body.replace(/\s+/g, ' ').split(/(?<=[.؛:!?…])\s+/).filter((s) => s.trim());
  const [range, setRange] = useState<[number, number] | null>(null);
  const tap = (k: number) => {
    const next: [number, number] = !range ? [k, k] : k === range[1] + 1 ? [range[0], k] : k === range[0] - 1 ? [k, range[1]]
      : [k, k];
    setRange(next);
    onQuote(sentences.slice(next[0], next[1] + 1).join(' '));
  };
  return (
    <div className="flex flex-col gap-2">
      <p className="m-0 text-meta text-ink-soft">{t('composer2.quoteTapHint')}</p>
      <div lang="ar" dir="rtl" className="flex flex-col gap-1.5">
        {sentences.map((s, k) => {
          const on = range !== null && k >= range[0] && k <= range[1];
          return (
            <button key={k} type="button" onClick={() => tap(k)} aria-pressed={on}
                    className={`rounded-control border px-3 py-2 text-start font-law text-law leading-[1.7] ${on ? 'border-stamp bg-wash text-ink' : 'border-rule-soft text-ink hover:border-stamp'}`}>
              {s}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function Shell({ children }: { children: React.ReactNode }) {
  return <main className="mx-auto flex w-full max-w-6xl flex-col gap-5 px-4 pb-10 pt-0 sm:px-6 sm:pt-8">{children}</main>;
}
