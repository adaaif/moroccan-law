import { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useSession } from '@/shared/stores/session';
import { usePageTitle } from '@/shared/services/title';
import { LoadError } from '@/features/corpus/NotFound';
import { ArchWindow } from '@/features/topics/Arch';
import { topicColour } from '@/features/topics/colour';
import { PageSkeleton } from '@/shared/components/ui';
import { Closed, Composer } from './Composer';
import { HelpNearby } from './HelpNearby';
import { PostCard } from './PostCard';
import { FeedSorts, Initial, TalkArch } from './TalkParts';
import { TalkShell } from './TalkShell';
import { useTopics } from '@/features/topics/topics.api';
import { discussionApi, useFeed, useQuestions, useRefreshTalk, type Contribution, type Period, type Place, type Sort } from './discussion.api';
import { useNoIndex } from './noindex';
import { isSensitive } from './sensitive';
import { ago, errorText, placeName, slugOf, useT } from './strings';

/**
 * A topic's place (29 Oct 2026): /talk/family. Its room (30 Oct 2026): the topic's scene through its arch,
 * its name, how many posts and how many questions wait, who looks after it. The form for a new post (opened on the
 * question the hub's box sent here), the posts sorted by life, newness, use over a period or waiting, a page at a time.
 * The rules and how a post is checked beside.
 */
export default function PlacePage() {
  const { t, i18n } = useT();
  // /talk/family: the app's one route for the discussion (/talk/*) leaves the address to read here.
  const place = useLocation().pathname.replace(/\/$/, '');
  const navigate = useNavigate();
  const [sort, setSort] = useState<Sort>('active');
  const [period, setPeriod] = useState<Period>('month');
  const feed = useFeed(place, sort, period);
  const refresh = useRefreshTalk();
  useNoIndex();
  const first = feed.data?.pages[0];
  usePageTitle(first?.place ? [placeName(first.place.name, i18n.language), t('title')] : [t('title')]);

  if (feed.isLoading) return <TalkShell where={slugOf(place)}><PageSkeleton /></TalkShell>;
  if (!first?.place) {
    return <TalkShell where={slugOf(place)}>{feed.error ? <LoadError error={feed.error} retry={() => void feed.refetch()} /> : <PageSkeleton />}</TalkShell>;
  }
  const { writing, review } = first;
  const p = first.place;
  const posts = feed.data!.pages.flatMap((page) => page.posts);
  const quiet = writing.why === 'discussion.closed' && p.count === 0;
  const sent = (made: Contribution) => {
    refresh();
    navigate(made.path ?? place);
  };

  return (
    <TalkShell where={p.slug} side={<PlaceSide p={p} />}>
          <header className="tk-room" style={topicColour(slugOf(p.path))}>
            <div className="tk-room-window">
              {p.slug === 'general' ? <TalkArch /> : <ArchWindow slug={p.slug} className="w-full" />}
            </div>
            <div className="tk-room-text">
              <Link to="/talk" className="tk-room-back">{t('title')}</Link>
              <h1>{placeName(p.name, i18n.language)}</h1>
              <p className="tk-room-facts">
                <span>{t('talk2.posts', { count: p.count })}</span>
                {p.open_questions ? <span className="open">{t('open', { count: p.open_questions })}</span> : null}
              </p>
            </div>
            <div className="tk-room-foot">
              <Moderators place={p} />
              <div className="tk-room-acts">
                {p.slug !== 'general' ? <Link to={`/topics/${p.slug}`}>{t('talk2.topicPage')}</Link> : null}
                {review.can ? (
                  <button type="button" onClick={async () => { await discussionApi.lock(p.path, !p.locked); refresh(); }}
                          className="h-10 rounded-full border border-dashed border-amended px-4 text-meta text-amended hover:bg-amended-wash">
                    {p.locked ? t('mod.unlock') : t('mod.lock')}
                  </button>
                ) : null}
                <Follow path={p.path} following={p.following} onChanged={refresh} />
              </div>
            </div>
          </header>

          {isSensitive(place) ? <HelpNearby /> : null}

          {quiet ? <p className="m-0 rounded-control bg-sheet px-4 py-3 text-body">{t('notYet')}</p>
            : p.locked ? <p className="m-0 rounded-control bg-sheet px-4 py-3 text-body text-ink-soft">{t('locked')}</p>
            : writing.can || writing.why === 'email.not_proven' ? (
              <Composer place={place} writing={writing} onDone={sent} />
            ) : <Closed why={writing.why} />}

          {quiet ? null : (
            <>
              <FeedSorts sort={sort} period={period} onSort={setSort} onPeriod={setPeriod} waiting={p.open_questions} />
              {posts.length ? (
                <ol className="tk-posts">
                  {posts.map((c) => <li key={c.id}><PostCard c={c} /></li>)}
                </ol>
              ) : (
                <p className="m-0 rounded-control bg-sheet px-4 py-3 text-body text-ink-soft">
                  {sort === 'open' ? t('emptyOpen') : t('talk2.empty')}
                </p>
              )}
              {feed.hasNextPage ? (
                <button type="button" onClick={() => void feed.fetchNextPage()} disabled={feed.isFetchingNextPage}
                        className="h-11 rounded-control bg-sheet px-5 text-body font-medium text-stamp hover:bg-wash">
                  {feed.isFetchingNextPage ? t('loading') : t('talk2.morePosts')}
                </button>
              ) : null}
            </>
          )}
          {feed.error ? <p role="alert" className="text-repealed">{errorText(t, feed.error)}</p> : null}
          <p className="m-0 px-1 text-meta text-ink-soft">{t('disclaimer')}</p>
    </TalkShell>
  );
}

/** Beside a topic's feed and its posts on a wide desk: what the topic is (its lead, its counts, the law's page), what
 *  waits for an answer in it, and the rules with how a post is checked. */
export function PlaceSide({ p }: { p: Place }) {
  const { t, i18n } = useT();
  const lang = i18n.language === 'fr' ? 'fr' : 'ar';
  const topic = useTopics().data?.find((x) => x.slug === p.slug);
  const waiting = useQuestions(p.path).data?.pages[0]?.questions.slice(0, 4) ?? [];
  return (
    <>
      <section className="tk-card" aria-labelledby="place-about" style={topicColour(slugOf(p.path))}>
        <h2 id="place-about">{t('hub.topicAbout')}</h2>
        {topic ? <p lang={lang}>{topic.lead[lang]}</p> : null}
        <span className="facts">
          <span>{t('talk2.posts', { count: p.count })}</span>
          {p.open_questions ? <span className="open">{t('open', { count: p.open_questions })}</span> : null}
        </span>
        {p.slug !== 'general' ? <span className="links"><Link to={`/topics/${p.slug}`}>{t('talk2.topicPage')}</Link></span> : null}
      </section>
      {waiting.length ? (
        <section className="tk-card" aria-labelledby="place-waiting">
          <h2 id="place-waiting">{t('hub.waitingHere')}</h2>
          <ol className="tk-wlist">
            {waiting.map((q) => (
              <li key={q.id}>
                <Link to={q.path} dir="auto" className="tk-wq">{q.title || q.body}</Link>
                <span className="tk-wmeta"><time dateTime={q.created_at}>{ago(q.created_at, i18n.language)}</time></span>
              </li>
            ))}
          </ol>
        </section>
      ) : null}
      <section className="tk-card" aria-labelledby="place-rules">
        <h2 id="place-rules">{t('aside.rulesTitle')}</h2>
        <ul className="rules"><li>{t('aside.rule1')}</li><li>{t('aside.rule2')}</li><li>{t('aside.rule3')}</li></ul>
        <p>{t('check.aside')}</p>
        <span className="links"><Link to="/rules">{t('rulesLink')}</Link><Link to="/privacy">{t('privacyLink')}</Link></span>
      </section>
    </>
  );
}

/** Who moderates the topic, by name and karma: people of its community whom staff appointed. */
export function Moderators({ place }: { place: Place }) {
  const { t } = useT();
  if (!place.moderators.length) return <p className="tk-mods">{t('talk2.moderatorsStaff')}</p>;
  return (
    <p className="tk-mods">
      <span>{t('talk2.moderators')}</span>
      {place.moderators.map((m) => (
        <Link key={m.username} to={`/people/${encodeURIComponent(m.username)}`}>
          <Initial name={m.name} />
          <span dir="auto">{m.name}</span>
          {m.karma ? <span className="k">✦ {m.karma}</span> : null}
        </Link>
      ))}
    </p>
  );
}

/** The rules in three lines, how a post is checked, and the two pages that say it all. */
export function Aside() {
  const { t } = useT();
  return (
    <aside className="flex min-w-[240px] flex-[1_1_260px] flex-col gap-6 pt-2 text-body">
      <section className="flex flex-col gap-2.5">
        <h2 className="m-0 text-body font-semibold">{t('aside.rulesTitle')}</h2>
        <ul className="m-0 flex list-none flex-col gap-2 p-0 text-ink-soft">
          <li>{t('aside.rule1')}</li>
          <li>{t('aside.rule2')}</li>
          <li>{t('aside.rule3')}</li>
        </ul>
        <span className="flex flex-wrap gap-x-4 gap-y-1 text-meta">
          <Link to="/rules" className="no-underline">{t('rulesLink')}</Link>
          <Link to="/privacy" className="no-underline">{t('privacyLink')}</Link>
        </span>
      </section>
      <section className="flex flex-col gap-2">
        <h2 className="m-0 text-body font-semibold">{t('check.asideTitle')}</h2>
        <p className="m-0 text-ink-soft">{t('check.aside')}</p>
      </section>
      <section className="flex flex-col gap-2">
        <h2 className="m-0 text-body font-semibold">{t('karma.title')}</h2>
        <p className="m-0 text-ink-soft">{t('karma.hint')}</p>
      </section>
    </aside>
  );
}

export function Follow({ path, following, onChanged }: { path: string; following: boolean; onChanged: () => void }) {
  const { t } = useT();
  const signedIn = useSession((s) => s.tokens !== null);
  const [on, setOn] = useState(following);
  if (!signedIn) return null;
  return (
    <button type="button" aria-pressed={on} title={t('followHint')}
            onClick={async () => {
              try {
                setOn((await discussionApi.follow(path, !on)).following);
                onChanged();
              } catch {
                // A refused follow (closed, paused) leaves the button as it was.
              }
            }}
            className={`ms-auto h-10 rounded-full border px-4 text-meta ${on ? 'border-stamp bg-wash text-stamp' : 'border-rule text-ink hover:border-stamp'}`}>
      {on ? `✓ ${t('following')}` : t('follow')}
    </button>
  );
}
