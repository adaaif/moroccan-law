import { useEffect, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useSession } from '@/shared/stores/session';
import { usePageTitle } from '@/shared/services/title';
import { LinesSkeleton } from '@/shared/components/ui';
import { PostCard } from './PostCard';
import { AskBox, ChatIcon, Exchange, FeedSorts, TopicTag } from './TalkParts';
import { TalkShell } from './TalkShell';
import { PERIODS, SORTS, useAnswered, useFeed, usePlaces, useQuestions, type Feed, type Period, type Sort } from './discussion.api';
import { useNoIndex } from './noindex';
import { ago, useT } from './strings';
import type { InfiniteData, UseInfiniteQueryResult } from '@tanstack/react-query';

/**
 * «النقاش» (29 Oct 2026; drawn again on 30 Oct 2026, and as a feed the same day: the welcome felt static and the posts
 * were a scroll away; now topics as a forum's boards, adapted to the law). The topics are the
 * rail (a phone's row of arches), each with what waits in it; the page is the feed itself, every topic's posts, or what
 * one follows, or what waits for an answer, in four orders («الأنفع» over a period: ?period=week|year|all, a month
 * without), more as one scrolls; one line above it opens the question box. Beside it on a wide desk: what the conversation is, its rules, what waits, a question a neighbour answered.
 */
export default function TalkPage() {
  const { t } = useT();
  usePageTitle([t('talk.title')]);
  useNoIndex();
  const signedIn = useSession((s) => s.tokens !== null);
  const [params, setParams] = useSearchParams();
  const asked = params.get('sort') as Sort | null;
  const sort: Sort = asked && SORTS.includes(asked) ? asked : 'active';
  const span = params.get('period') as Period | null;
  const period: Period = span && PERIODS.includes(span) ? span : 'month';
  const following = signedIn && params.get('feed') === 'following';
  const feed = useFeed(following ? 'following' : '', sort, period);
  const posts = feed.data?.pages.flatMap((page) => page.posts) ?? [];
  const places = usePlaces().data?.places ?? [];
  const where = following ? 'following' : sort === 'open' ? 'open' : 'all';
  const order = (s: Sort, p: Period = 'month') => {
    const next = new URLSearchParams(params);
    if (s === 'active') next.delete('sort'); else next.set('sort', s);
    if (s === 'top' && p !== 'month') next.set('period', p); else next.delete('period');
    setParams(next, { replace: true });
  };
  return (
    <TalkShell where={where} side={<HubSide />}>
      <header className="tk-feedhead">
        <h1>{following ? t('hub.following') : t('talk.title')}</h1>
        <p>{following ? t('hub.followingLead') : t('talk3.lead')}</p>
      </header>
      <AskBar places={places} />
      <FeedSorts sort={sort} period={period} onSort={(s) => order(s, period)} onPeriod={(p) => order('top', p)} />
      {feed.isLoading ? <LinesSkeleton lines={8} /> : posts.length ? (
        <ol className="tk-posts">
          {posts.map((c) => <li key={c.id}><PostCard c={c} label={c.place ? { article: '', text: '', place: c.place, name: places.find((p) => p.path === c.place)?.name } : undefined} /></li>)}
        </ol>
      ) : (
        <p className="tk-none">
          {following ? <>{t('hub.followingNone')} <Link to="/talk">{t('hub.all')}</Link></> : sort === 'open' ? t('emptyOpen') : t('talk2.empty')}
        </p>
      )}
      <More feed={feed} />
    </TalkShell>
  );
}

/** The next page comes as the reader reaches the feed's end; a button for whoever gets there first. */
function More({ feed }: { feed: UseInfiniteQueryResult<InfiniteData<Feed>> }) {
  const { t } = useT();
  const end = useRef<HTMLDivElement>(null);
  const { hasNextPage, isFetchingNextPage, fetchNextPage } = feed;
  useEffect(() => {
    const el = end.current;
    if (!el || !hasNextPage) return;
    const seen = new IntersectionObserver((entries) => {
      if (entries.some((e) => e.isIntersecting) && !isFetchingNextPage) void fetchNextPage();
    }, { rootMargin: '600px 0px' });
    seen.observe(el);
    return () => seen.disconnect();
  }, [hasNextPage, isFetchingNextPage, fetchNextPage]);
  if (!hasNextPage) return null;
  return (
    <div ref={end} className="tk-more">
      <button type="button" onClick={() => void fetchNextPage()} disabled={isFetchingNextPage}
              className="h-11 rounded-control bg-sheet px-5 text-body font-medium text-stamp hover:bg-wash">
        {isFetchingNextPage ? t('loading') : t('talk2.morePosts')}
      </button>
    </div>
  );
}

/** One line to ask, as a feed opens on one: tapped, the question box (the topic guessed from the words, the questions
 *  already asked there), closed again when the reader changes their mind. */
function AskBar({ places }: { places: Parameters<typeof AskBox>[0]['places'] }) {
  const { t } = useT();
  const [open, setOpen] = useState(false);
  if (open) {
    return (
      <div className="tk-askcard">
        <button type="button" className="x" onClick={() => setOpen(false)} aria-label={t('hub.close')}>×</button>
        <AskBox places={places} autoFocus />
      </div>
    );
  }
  return (
    <div className="tk-askbar">
      <button type="button" className="fake" onClick={() => setOpen(true)} aria-haspopup="true">{t('talk3.askLabel')}</button>
      <span className="go" aria-hidden="true"><ChatIcon size={20} /></span>
    </div>
  );
}

/** Beside the feed: what the conversation is and its rules, what waits for an answer, a question a neighbour answered. */
function HubSide() {
  const { t, i18n } = useT();
  const places = usePlaces().data?.places ?? [];
  const waiting = useQuestions('').data?.pages[0]?.questions.slice(0, 4) ?? [];
  const exchange = useAnswered().data?.pages[0]?.questions.find((q) => q.answer && q.answer.body);
  const count = places.reduce((n, p) => n + p.count, 0);
  const open = places.reduce((n, p) => n + p.open_questions, 0);
  return (
    <>
      <section className="tk-card" aria-labelledby="hub-about">
        <h2 id="hub-about">{t('hub.about')}</h2>
        <p>{t('talk2.lead')}</p>
        <span className="facts"><span>{t('talk2.posts', { count })}</span>{open ? <span className="open">{t('open', { count: open })}</span> : null}</span>
        <ul className="rules"><li>{t('aside.rule1')}</li><li>{t('aside.rule2')}</li><li>{t('aside.rule3')}</li></ul>
        <span className="links"><Link to="/rules">{t('rulesLink')}</Link><Link to="/privacy">{t('privacyLink')}</Link></span>
      </section>
      {waiting.length ? (
        <section className="tk-card" aria-labelledby="hub-waiting">
          <h2 id="hub-waiting">{t('talk3.waitingTitle')}</h2>
          <ol className="tk-wlist">
            {waiting.map((q) => (
              <li key={q.id}>
                <Link to={q.path} dir="auto" className="tk-wq">{q.title || q.body}</Link>
                <span className="tk-wmeta">
                  {q.label.place ? <TopicTag place={q.label.place} name={q.label.name} /> : null}
                  <time dateTime={q.created_at}>{ago(q.created_at, i18n.language)}</time>
                </span>
              </li>
            ))}
          </ol>
          <span className="links"><Link to="/talk?sort=open">{t('talk3.allQuestions')}</Link></span>
        </section>
      ) : null}
      {exchange ? <section className="tk-card"><Exchange q={exchange} /></section> : null}
    </>
  );
}
