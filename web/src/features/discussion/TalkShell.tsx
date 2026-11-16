import { Link } from 'react-router-dom';
import { ARCH } from '@/features/topics/Arch';
import { topicColour } from '@/features/topics/colour';
import { TopicIcon } from '@/features/topics/TopicIcon';
import { useSession } from '@/shared/stores/session';
import { ChatIcon } from './TalkParts';
import { usePlaces, type PlaceSummary } from './discussion.api';
import { placeName, useT } from './strings';
import './talk.css';

/** Which feed the shell shows: every topic, what one follows, what waits for an answer, or one topic by its slug. */
export type Where = 'all' | 'following' | 'open' | string;

const DAY = 86_400_000;

/** A topic's face: its arch in its tint with its line icon (the general place's, a message in the conversation's teal);
 *  a dot when it lived today. */
export function TopicFace({ p, width = 34 }: { p: PlaceSummary; width?: number }) {
  const { t } = useT();
  const live = p.last_at ? Date.now() - Date.parse(p.last_at) < DAY : false;
  return (
    <span className="tk-av" style={{ ...topicColour(p.slug), ['--w' as string]: `${width}px` }}>
      <svg aria-hidden="true" viewBox="-2 -2 124 136" className="arch"><path d={ARCH} /></svg>
      <span className="ic" aria-hidden="true">
        {p.slug === 'general' ? <ChatIcon size={Math.round(width * 0.44)} /> : <TopicIcon slug={p.slug} size={Math.round(width * 0.44)} />}
      </span>
      {live ? <span className="live" role="img" aria-label={t('hub.liveToday')} /> : null}
    </span>
  );
}

/**
 * The conversation's shell (30 Oct 2026: topics as a forum's boards, adapted to the law): the topics as a rail at the start, each its arch for a face, its door's name, how many questions wait in it
 * and a dot when it lived today, after the three feeds (every topic, what one follows, what waits); on a phone the same
 * arches in one row to swipe, over the feed (not over a post, which names its topic itself: `strip`). The page's feed
 * in the middle; beside it on a wide desk, `side`.
 */
export function TalkShell({ where, side, strip = true, children }: {
  where: Where; side?: React.ReactNode; strip?: boolean; children: React.ReactNode;
}) {
  const { t, i18n } = useT();
  const signedIn = useSession((s) => s.tokens !== null);
  const places = usePlaces().data?.places ?? [];
  const feeds: [Where, string, string, React.ReactNode][] = [
    ['all', '/talk', t('hub.all'), <ChatIcon key="a" size={18} />],
    ...(signedIn ? [['following', '/talk?feed=following', t('hub.following'), <Bell key="f" />] as [Where, string, string, React.ReactNode]] : []),
    ['open', '/talk?sort=open', t('hub.open'), <Dots key="o" />],
  ];
  const name = (p: PlaceSummary) => placeName(p.short ?? p.name, i18n.language);
  return (
    <main className="tk tk-shell">
      <nav className="tk-rail" aria-label={t('hub.topics')}>
        {feeds.map(([key, to, label, icon]) => (
          <Link key={key} to={to} aria-current={where === key ? 'page' : undefined}>
            <span className="ico" aria-hidden="true">{icon}</span><span className="nm">{label}</span>
          </Link>
        ))}
        <h2>{t('hub.topics')}</h2>
        {places.map((p) => (
          <Link key={p.slug} to={p.path} aria-current={where === p.slug ? 'page' : undefined} style={topicColour(p.slug)}>
            <TopicFace p={p} />
            <span className="nm">{name(p)}</span>
            {p.open_questions ? <span className="tk-badge" title={t('open', { count: p.open_questions })}>{p.open_questions}</span> : null}
          </Link>
        ))}
        <p className="foot"><Link to="/rules">{t('rulesLink')}</Link><Link to="/privacy">{t('privacyLink')}</Link></p>
      </nav>
      <div className="tk-feedcol">
        {strip ? <ul className="tk-strip" aria-label={t('hub.topics')}>
          {feeds.map(([key, to, label, icon]) => (
            <li key={key}>
              <Link to={to} aria-current={where === key ? 'page' : undefined}>
                <span className="ico" aria-hidden="true">{icon}</span><span className="nm">{label}</span>
              </Link>
            </li>
          ))}
          {places.map((p) => (
            <li key={p.slug}>
              <Link to={p.path} aria-current={where === p.slug ? 'page' : undefined} style={topicColour(p.slug)}
                    aria-label={p.open_questions ? `${name(p)}، ${t('open', { count: p.open_questions })}` : undefined}>
                <span className="relative">
                  <TopicFace p={p} width={52} />
                  {p.open_questions ? <span className="tk-badge" aria-hidden="true">{p.open_questions}</span> : null}
                </span>
                <span className="nm">{name(p)}</span>
              </Link>
            </li>
          ))}
        </ul> : null}
        {children}
      </div>
      {side ? <aside className="tk-side">{side}</aside> : null}
    </main>
  );
}

const Bell = () => (
  <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <path d="M6 9a6 6 0 1 1 12 0c0 5 2 6.5 2 6.5H4S6 14 6 9ZM10 19a2 2 0 0 0 4 0" />
  </svg>
);

const Dots = () => (
  <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><circle cx="6" cy="12" r="1.8" /><circle cx="12" cy="12" r="1.8" /><circle cx="18" cy="12" r="1.8" /></svg>
);
