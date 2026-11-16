import { Link } from 'react-router-dom';
import { Answers, TopicTag } from './TalkParts';
import { useFeed, usePlaces } from './discussion.api';
import { ago, useT } from './strings';

/** «دابا فالنقاش» on the home (30 Oct 2026): the conversation's liveliest posts as the feed shows them, each its answers'
 *  bubble (dots while nobody answered), its topic and its title, and the way in; nothing when there is none. */
export default function HomeTalk() {
  const { t, i18n } = useT();
  const feed = useFeed('', 'active');
  const names = new Map((usePlaces().data?.places ?? []).map((p) => [p.path, p.name]));
  const posts = feed.data?.pages[0]?.posts.slice(0, 4) ?? [];
  if (!posts.length) return null;
  return (
    <section className="tk tk-pulse" aria-labelledby="home-talk">
      <div className="tk-pulse-head">
        <h2 id="home-talk"><span className="dot" aria-hidden="true" />{t('homeTalk.title')}</h2>
        <Link to="/talk">{t('homeTalk.all')}</Link>
      </div>
      <ol>
        {posts.map((c) => (
          <li key={c.id}>
            <Answers c={c} />
            <span className="body">
              <span className="meta">
                {c.place ? <TopicTag place={c.place} name={names.get(c.place)} /> : null}
                <time dateTime={c.active_at ?? c.created_at}>{ago(c.active_at ?? c.created_at, i18n.language)}</time>
              </span>
              <Link to={c.path ?? '/talk'} dir="auto" className="ttl">{c.title || c.body}</Link>
            </span>
          </li>
        ))}
      </ol>
      <Link to="/talk" className="tk-pulse-ask">{t('homeTalk.ask')}</Link>
    </section>
  );
}
