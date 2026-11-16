import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { topicColour } from '@/features/topics/colour';
import { usePageTitle } from '@/shared/services/title';
import { Page, PageSkeleton } from '@/shared/components/ui';
import { PersonHero } from './account/PersonHero';
import { PostCard } from './PostCard';
import { TopicTag } from './TalkParts';
import { usePerson, type Labelled, type PersonKind } from './discussion.api';
import { useNoIndex } from './noindex';
import { ago, pageOf, slugOf, useT } from './strings';

/** /people/:username (drawn again on 30 Oct 2026): a person's card, then what they wrote under their name, all of it,
 *  their questions and posts, or their answers, the answers shown as the answers they were; beside it, the topics they
 *  write in. Never what they wrote «بدون اسم». */
export default function PersonPage() {
  const { t } = useT();
  const { username = '' } = useParams();
  const [kind, setKind] = useState<PersonKind>('');
  const head = usePerson(username);
  const list = usePerson(username, kind);
  useNoIndex();
  const p = head.data?.pages[0]?.person;
  usePageTitle([p?.name]);
  if (head.isLoading) return <Page width="wide"><PageSkeleton /></Page>;
  if (!p) return <Page width="wide"><p className="text-repealed">{t('personPage.notFound')}</p></Page>;
  const items = list.data?.pages.flatMap((page) => page.contributions) ?? [];
  const tabs: [PersonKind, string, number][] = [['', t('me2.tabAll'), p.contributions], ['posts', t('me2.tabPosts'), p.posts],
    ['answers', t('me2.tabAnswers'), p.answers]];

  return (
    <Page width="wide" className="ac tk">
      <PersonHero who={p} />
      <div className="ac-person">
        <section aria-label={t('me2.tabAll')} className="flex min-w-0 flex-col gap-4">
          <div role="tablist" aria-label={t('me2.tabsLabel')} className="tk-tabs">
            {tabs.map(([k, label, n]) => (
              <button key={k} type="button" role="tab" aria-selected={kind === k} onClick={() => setKind(k)}
                      className={`h-10 rounded-full border px-4 text-meta ${kind === k ? 'border-stamp bg-stamp text-on-stamp' : 'border-rule bg-sheet text-ink hover:border-stamp'}`}>
                {label} ({n})
              </button>
            ))}
          </div>
          {list.isLoading ? <PageSkeleton /> : items.length ? (
            <ol className="tk-posts">
              {items.map((c) => <li key={c.id}>{c.kind === 'comment' ? <AnswerCard c={c} /> : <PostCard c={c} label={c.label} by={false} />}</li>)}
            </ol>
          ) : <p className="ac-quiet">{t('me2.empty')}</p>}
          {list.hasNextPage ? (
            <button type="button" onClick={() => void list.fetchNextPage()} disabled={list.isFetchingNextPage}
                    className="h-11 rounded-control bg-sheet px-5 text-body font-medium text-stamp hover:bg-wash">
              {list.isFetchingNextPage ? t('loading') : t('me2.more')}
            </button>
          ) : null}
        </section>
        <aside className="ac-side">
          {p.places.length ? (
            <>
              <h2>{t('me2.whereTitle')}</h2>
              <ul className="ac-where">
                {p.places.map((x) => (
                  <li key={x.path}>
                    <Link to={x.path}><TopicTag place={x.path} name={x.name} /></Link>
                    <span className="n">{x.count}</span>
                  </li>
                ))}
              </ul>
            </>
          ) : null}
          <p className="ac-quiet text-meta">{t('karma.hint')}</p>
          <p className="ac-quiet text-meta">{t('personPage.anonymousNote')}</p>
        </aside>
      </div>
    </Page>
  );
}

/** An answer as the answer it was: to which question, in which topic, its words in the conversation's bubble, and
 *  whether it helped the one who asked. The whole card opens it in its post. */
function AnswerCard({ c }: { c: Labelled }) {
  const { t, i18n } = useT();
  return (
    <article className="tk tk-post ac-answer" style={topicColour(slugOf(c.place || c.label.place || ''))}>
      <p className="ac-answer-to">
        <span>{t('me2.answerTo')}</span>
        {/* A post readers can no longer read keeps its title to itself: «a post» stands for it. */}
        <Link to={`${pageOf(c.path)}#c${c.id}`} dir="auto">{c.post_title || c.label.title || c.label.article || t('review.post')}</Link>
        {c.label.place ? <TopicTag place={c.label.place} name={c.label.name} /> : null}
      </p>
      {c.body ? <p className="ac-answer-body" dir="auto">{c.body}</p> : null}
      <p className="ac-answer-meta">
        {c.accepted ? <span className="yes">✓ {t('accepted')}</span> : null}
        {c.useful ? <span>{t('usefulCount', { count: c.useful })}</span> : null}
        <time dateTime={c.created_at}>{ago(c.created_at, i18n.language)}</time>
      </p>
    </article>
  );
}
