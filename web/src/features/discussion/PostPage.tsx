import { useMemo, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Stamp } from '@/features/corpus/article/Stamp';
import { AR, issueNo } from '@/features/corpus/format';
import { textName } from '@/features/corpus/names';
import { LoadError } from '@/features/corpus/NotFound';
import { topicColour } from '@/features/topics/colour';
import { TopicIcon } from '@/features/topics/TopicIcon';
import { usePageTitle } from '@/shared/services/title';
import { Comments } from './Comments';
import { Closed, Composer } from './Composer';
import { ContributionCard, type Moderation } from './ContributionCard';
import { HelpNearby } from './HelpNearby';
import { PostLoading } from './PostLoading';
import { Follow, PlaceSide } from './PlacePage';
import { ChatIcon } from './TalkParts';
import { TalkShell } from './TalkShell';
import { type CommentSort, usePost, useRefreshTalk } from './discussion.api';
import { useNoIndex } from './noindex';
import { isSensitive } from './sensitive';
import { labelName, placeName, slugOf, useT } from './strings';

/**
 * A post (29 Oct 2026): /talk/family/12, #c34 for one comment. Drawn as the conversation it is (30 Oct 2026, drawn
 * again): the question as its asker's message, their title, words and the article
 * they started from in one bubble; then the comments, a page of conversations at a time in the reader's order, the form
 * above them. The answer its asker marked «أفادني» has no box of its own (31 Oct 2026): it is marked where it
 * stands, and «الأنفع» puts it first with its replies. The topics' rail beside it on a desk, its topic and the rules on a
 * wide one.
 */
export default function PostPage() {
  const { t, i18n } = useT();
  const location = useLocation();
  const [sort, setSort] = useState<CommentSort>('best');
  const id = Number(location.pathname.match(/\/(\d+)\/?$/)?.[1]);
  const page = usePost(id, sort);
  const refresh = useRefreshTalk();
  useNoIndex();
  // The first page holds the post and its answer; each page adds its conversations.
  const pages = page.data?.pages;
  const data = useMemo(() => (pages?.[0]
    ? { ...pages[0], post: { ...pages[0].post, replies: pages.flatMap((p) => p.post.replies ?? []) } } : undefined), [pages]);
  usePageTitle(data ? [data.post.title, placeName(data.place.name, i18n.language)] : []);
  const where = slugOf(location.pathname.split('/').slice(0, 3).join('/'));

  if (!data && !page.error) return <PostLoading where={where} id={id} />;
  if (!data) {
    return (
      <TalkShell where={where} strip={false}>
        <LoadError error={page.error} retry={() => void page.refetch()} />
      </TalkShell>
    );
  }
  const { place, post, about, writing, review } = data;
  const path = post.path ?? `${place.path}/${post.id}`;
  const mod: Moderation = { can: review.can, questions: [] };
  const open = writing.can || writing.why === 'email.not_proven';
  const changed = post.cites?.filter((x) => x.changed) ?? [];
  const article = about ? (
    // The article it started from, clipped in the question as a messaging app shows a link.
    <section className="tk-law" aria-label={about.article.label}>
      <div className="tk-law-head">
        <Link to={about.article.path}><bdi {...AR}>{about.article.label}</bdi></Link>
        <span dir="auto">{textName(about.text, i18n.language)}</span>
        <Stamp issue={about.text.issue ? issueNo(about.text.issue, (k) => t(k, { ns: 'translation' })) : null} page={about.article.page}
               consolidated={about.version.consolidation !== 'as_published'}
               to={about.article.page && about.article.document_id !== null && about.article.page_index !== null
                 ? `/pages/${about.article.document_id}/${about.article.page_index}?a=${encodeURIComponent(about.article.label)}` : null} />
      </div>
      {post.quote ? <q {...AR} className="tk-law-text">{post.quote}</q> : <p {...AR} className="tk-law-text">{about.article.body}</p>}
    </section>
  ) : null;

  return (
    <TalkShell where={place.slug} strip={false} side={<PlaceSide p={place} />}>
      <div className="tk-pp" style={topicColour(place.slug)}>
        <div className="tk-crumb">
          <Link to={place.path}>
            <span aria-hidden="true">‹</span>
            {place.slug === 'general' ? <ChatIcon size={18} /> : <TopicIcon slug={place.slug} size={18} />}
            {placeName(place.name, i18n.language)}
          </Link>
          <Follow path={path} following={data.following} onChanged={refresh} />
        </div>

        <div className="tk-q">
          {/* The post is its asker's message: the title, the words and the article in one bubble. Its comments are
              written in the form below, not under it. */}
          <ContributionCard c={{ ...post, quote: '' }} path={path} label={post.title} writing={{ ...writing, can: false }}
                            onChanged={refresh} mod={mod} bare after={article}
                            lead={post.title ? <h1 dir="auto">{post.title}</h1> : null} />
          {changed.length ? (
            <p className="tk-changed">
              {t('talk2.citedChanged', { list: changed.map((x) => `${x.label.article} ${labelName(x.label, i18n.language)}`).join('، ') })}
            </p>
          ) : null}
        </div>

        <Comments post={post} path={path} writing={place.locked ? { ...writing, can: false } : writing} mod={mod} onChanged={refresh}
                  sort={sort} onSort={setSort} conversations={data.conversations} people={data.people ?? 0}
                  more={page.hasNextPage ? { loading: page.isFetchingNextPage, next: () => void page.fetchNextPage() } : null}>
          <div className="tk-write">
            {place.locked ? <p className="m-0 rounded-control bg-paper px-4 py-3 text-body text-ink-soft">{t('locked')}</p>
              : open ? <Composer place={path} writing={writing} parent={post} onDone={refresh} />
              : <Closed why={writing.why} />}
          </div>
        </Comments>

        {isSensitive(place.path) ? <HelpNearby /> : null}
        <p className="m-0 px-1 text-meta text-ink-soft">{t('disclaimer')}</p>
      </div>
    </TalkShell>
  );
}
