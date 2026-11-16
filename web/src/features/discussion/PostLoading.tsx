import { useMemo } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { topicColour } from '@/features/topics/colour';
import { TopicIcon } from '@/features/topics/TopicIcon';
import { Body, Who } from './ContributionCard';
import { PlaceSide } from './PlacePage';
import { ChatIcon, Initial } from './TalkParts';
import { TalkShell } from './TalkShell';
import { type Contribution, type Place, usePlaces } from './discussion.api';
import { ago, placeName, useT } from './strings';

/**
 * A post's page while its answer comes (31 Oct 2026: the page used to change shape as the post arrived): the page as
 * it will stand, so nothing moves when it arrives. What is known is shown: the
 * topic (its way back, its card beside on a desk) and, when the reader came from a list that held it, the question
 * itself. What is not yet is drawn in the topic's ink at the size it will take, a bar to a line of text, and the
 * thread's rails rule down once.
 */
export function PostLoading({ where, id }: { where: string; id: number }) {
  const { t, i18n } = useT();
  const summary = usePlaces().data?.places.find((p) => p.slug === where);
  const known = useKnownPost(id);
  const place: Place | null = summary ? {
    path: summary.path, slug: summary.slug, name: summary.name, count: summary.count, open_questions: summary.open_questions,
    locked: false, following: false, moderators: [],
  } : null;
  return (
    <TalkShell where={where} strip={false} side={place ? <PlaceSide p={place} /> : <SideGhost />}>
      <div className="tk-pp tk-ld" style={topicColour(where)} aria-busy="true">
        <p role="status" className="tk-sr">{t('talk5.loading')}</p>
        <div className="tk-crumb">
          {place ? (
            <Link to={place.path}>
              <span aria-hidden="true">‹</span>
              {place.slug === 'general' ? <ChatIcon size={18} /> : <TopicIcon slug={place.slug} size={18} />}
              {placeName(place.name, i18n.language)}
            </Link>
          ) : <span className="tk-ld-crumb" aria-hidden="true"><Bar w="7em" /></span>}
        </div>
        <div className="tk-q">{known ? <KnownQuestion c={known} /> : <GhostQuestion />}</div>
        <section className="tk-comments tk-ld-sheet" aria-hidden="true">
          <div className="tk-chead">
            <span className="tk-ld-h"><Line w="7.5em" /></span>
            <Bar w="5.5em" />
            <span className="tk-seg tk-ld-seg"><i /><i /><i /></span>
          </div>
          <span className="tk-ld-box" />
          <div className="tk-thread">
            <GhostNode lines={[100, 74]}><GhostNode lines={[86]} /></GhostNode>
            <GhostNode lines={[96, 91, 38]} />
            <GhostNode lines={[62]} />
          </div>
        </section>
      </div>
    </TalkShell>
  );
}

/** The post as a list already showed it (a topic's feed, the questions waiting or answered, a person's page): read from
 *  what those lists keep, so the question opens with its words while its comments come. */
function useKnownPost(id: number): Contribution | null {
  const client = useQueryClient();
  return useMemo(() => {
    for (const [, data] of client.getQueriesData({ queryKey: ['discussion'] })) {
      const found = findPost(data, id, 0);
      if (found) return found;
    }
    return null;
  }, [client, id]);
}

const LISTS = ['pages', 'posts', 'questions', 'contributions', 'places', 'post'] as const;

function findPost(data: unknown, id: number, depth: number): Contribution | null {
  if (!data || typeof data !== 'object' || depth > 4) return null;
  if (Array.isArray(data)) {
    for (const x of data) {
      const found = findPost(x, id, depth + 1);
      if (found) return found;
    }
    return null;
  }
  const o = data as Record<string, unknown>;
  if (o.id === id && o.parent === null && typeof o.created_at === 'string' && typeof o.title === 'string') return o as Contribution;
  for (const key of LISTS) {
    const found = key in o ? findPost(o[key], id, depth + 1) : null;
    if (found) return found;
  }
  return null;
}

/** The question as its page will draw it: its asker, its kind and age, its title and words in the bubble. */
function KnownQuestion({ c }: { c: Contribution }) {
  const { t, i18n } = useT();
  const named = c.anonymous || !c.author || 'deleted' in c.author ? null : c.author.name;
  return (
    <div className="tk-msg">
      <div className="tk-msg-who">
        <Initial name={named} />
        <Who author={c.author} anonymous={c.anonymous} mine={c.mine} />
        {c.kind !== 'comment' ? <span className="tk-kind">{t(`kinds.${c.kind}`)}</span> : null}
        <span className="tk-msg-when"><time dateTime={c.created_at}>{ago(c.created_at, i18n.language)}</time></span>
      </div>
      <div className="tk-msg-row">
        <div className="tk-msg-b">
          {c.title ? <h1 dir="auto">{c.title}</h1> : null}
          {c.body ? <Body body={c.body} links={c.links} /> : null}
        </div>
        <span className="tk-ld-acts"><Bar w="3.5em" /><Bar w="3em" /></span>
      </div>
    </div>
  );
}

function GhostQuestion() {
  return (
    <div className="tk-msg" aria-hidden="true">
      <div className="tk-msg-who"><span className="tk-initial" /><Bar w="8em" /><Bar w="3em" /></div>
      <div className="tk-msg-row">
        <div className="tk-msg-b">
          <span className="tk-ld-title"><Line w="78%" /><Line w="44%" /></span>
          <span className="tk-ld-lead"><Line w="100%" /><Line w="93%" /><Line w="57%" /></span>
        </div>
        <span className="tk-ld-acts"><Bar w="3.5em" /><Bar w="3em" /></span>
      </div>
    </div>
  );
}

/** A comment in the thread: its handle and rail, its byline, its lines; and what answers it. */
function GhostNode({ lines, children }: { lines: number[]; children?: React.ReactNode }) {
  return (
    <div className="tk-node">
      <span className="tk-handle"><span className="tk-khatam" /><span className="tk-line" /></span>
      <div className="tk-main">
        <div className="tk-msg-who"><span className="tk-initial" /><Bar w="6em" /><Bar w="3.5em" /></div>
        <span className="tk-ld-said">{lines.map((w, i) => <Line key={i} w={`${w}%`} />)}</span>
        {children ? <div className="tk-kids">{children}</div> : null}
      </div>
    </div>
  );
}

/** The topic's card beside, while not even the topics are known (a link opened cold). */
function SideGhost() {
  return (
    <div className="tk-card tk-ld-card" aria-hidden="true">
      <span className="tk-ld-h"><Line w="6em" /></span>
      <span className="tk-ld-said"><Line w="100%" /><Line w="82%" /></span>
      <Bar w="9em" />
    </div>
  );
}

/** One line of text to come, a line box tall: the bar sits where the words will. */
function Line({ w }: { w: string }) {
  return <span className="tk-ld-l" style={{ width: w }} />;
}

/** A word or two to come, in a line of text. */
function Bar({ w }: { w: string }) {
  return <span className="tk-ld-b" style={{ ['--w' as string]: w }} />;
}
