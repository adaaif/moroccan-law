import { Link } from 'react-router-dom';
import { TopicTag } from '../TalkParts';
import type { Person } from '../discussion.api';
import { ago, homeColour, useT } from '../strings';
import { Face } from './Face';

export type Who = Pick<Person['person'], 'name' | 'username' | 'joined' | 'karma' | 'posts' | 'answers' | 'accepted' | 'last_at'
  | 'places' | 'moderates'>;

/** A person's card on their public page (30 Oct 2026): their face in their topic's colour, their name, when they came and
 *  last wrote, what they did said in four figures, the topics they moderate. Their own account draws a shorter head. */
export function PersonHero({ who }: { who: Who }) {
  const { t, i18n } = useT();
  const joined = new Intl.DateTimeFormat(i18n.language === 'fr' ? 'fr-MA' : 'ar-MA', { month: 'long', year: 'numeric' })
    .format(new Date(who.joined));
  return (
    <header className="ac-hero" style={homeColour(who.places)}>
      <Face name={who.name || t('member')} />
      <div className="ac-hero-text">
        <h1 dir="auto">{who.name || t('member')}</h1>
        <p className="ac-hero-handle"><bdi dir="ltr">@{who.username}</bdi></p>
        <p className="ac-hero-facts">
          <span>{t('me2.joined', { date: joined })}</span>
          {who.last_at ? <span>{t('me2.lastActive', { ago: ago(who.last_at, i18n.language) })}</span> : null}
        </p>
      </div>
      {who.karma || who.posts || who.answers ? (
        <dl className="ac-stats">
          <div><dt title={t('karma.hint')}>{t('me2.statKarma')}</dt><dd>✦ {who.karma}</dd></div>
          <div><dt>{t('me2.statPosts')}</dt><dd>{who.posts}</dd></div>
          <div><dt>{t('me2.statAnswers')}</dt><dd>{who.answers}</dd></div>
          <div><dt>{t('me2.statAccepted')}</dt><dd>{who.accepted}</dd></div>
        </dl>
      ) : (
        // Four zeros say nothing.
        <p className="ac-hero-row ac-stats"><span>{t('me2.firstOther')}</span></p>
      )}
      {who.moderates.length ? (
        <div className="ac-hero-row">
          <span>{t('me2.moderates')}</span>
          {who.moderates.map((m) => <Link key={m.path} to={m.path} className="no-underline"><TopicTag place={m.path} name={m.name} /></Link>)}
        </div>
      ) : null}
    </header>
  );
}
