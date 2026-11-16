import { Link } from 'react-router-dom';
import { AR } from '@/features/corpus/format';
import { topicColour } from '@/features/topics/colour';
import { Who } from './ContributionCard';
import type { Contribution, Label } from './discussion.api';
import { Answers, Initial, TopicTag } from './TalkParts';
import { ago, labelName, pageOf, slugOf, useT } from './strings';

/** A post as a list shows it (29 Oct 2026; drawn again on 30 Oct 2026): its topic when the list mixes them, its title
 *  in its own direction, the start of its words, the articles it cites (and whether one changed since, D14), who wrote
 *  it with their karma, its last sign of life, and its answers as a bubble at its end. The whole card opens the post;
 *  the author and the articles keep their own links. */
export function PostCard({ c, label, held, besides, by = true }: { c: Contribution; label?: Label; held?: boolean;
                                                    /** The article the page is about: not said again. */ besides?: string;
                                                    /** Who wrote it: not said again on their own page. */ by?: boolean }) {
  const { t, i18n } = useT();
  const to = pageOf(c.path ?? '');
  const name = c.anonymous || !c.author || 'deleted' in c.author ? null : c.author.name;
  const cites = c.cites?.filter((x) => x.path !== besides) ?? [];
  return (
    <article className={`tk tk-post ${held || c.held ? 'held' : ''}`} style={topicColour(slugOf(c.place ?? label?.place ?? ''))}>
      <div className="tk-post-main">
        <div className="tk-post-top">
          {label?.place ? <TopicTag place={label.place} name={label.name} /> : null}
          {c.kind === 'post' ? <span className="tk-post-kind">{t('kinds.post')}</span> : null}
          {c.held ? <span className="tk-post-held">{t('talk2.waits')}</span> : null}
        </div>
        <h3 className="tk-post-title"><Link to={to} dir="auto">{c.title || c.body.slice(0, 120)}</Link></h3>
        {c.body && c.title && !repeats(c.title, c.body) ? <p className="tk-post-excerpt" dir="auto">{c.body}</p> : null}
        {cites.length ? (
          <ul className="tk-post-cites">
            {cites.slice(0, 3).map((x) => (
              <li key={x.path}>
                <Link to={x.path}>
                  <bdi {...AR} className="font-semibold">{x.label.article}</bdi>
                  <span dir="auto" className="text-ink-soft">{labelName(x.label, i18n.language)}</span>
                  {x.changed ? <span className="text-amended">{t('talk2.changed')}</span> : null}
                </Link>
              </li>
            ))}
          </ul>
        ) : null}
        <div className="tk-post-by">
          {by ? <><Initial name={name} /><Who author={c.author} anonymous={c.anonymous} mine={c.mine} /></> : null}
          <time dateTime={c.active_at ?? c.created_at}>{ago(c.active_at ?? c.created_at, i18n.language)}</time>
          {c.useful ? <span>{t('usefulCount', { count: c.useful })}</span> : null}
        </div>
      </div>
      <Answers c={c} />
    </article>
  );
}

/** The words only say again what the title says (a title made of a post's first sentence): shown once. */
const repeats = (title: string, body: string) => {
  const plain = (x: string) => x.replace(/[…؟?.!،,\s]+/g, ' ').trim();
  const words = plain(body);
  return words === plain(title) || (plain(title).length > 20 && words.startsWith(plain(title)) && words.length - plain(title).length < 40);
};
