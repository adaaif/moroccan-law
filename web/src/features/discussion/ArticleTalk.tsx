import { Link, useNavigate } from 'react-router-dom';
import { go } from '@/shared/services/motion';
import { useCounts } from './discussion.api';
import { useT } from './strings';

/** Under an article (R5, R12 of the for-everyone review): «النقاش», the bottom bar's own word for it (P7 of
 *  the polish review), with how many posts and comments in the topics cite it (29 Oct 2026); it opens the article's page, where
 *  one asks about it. Loaded after the text (a text's page never waits for it); one request for all its articles. */
export default function ArticleTalk({ textPath, eid, path, label }: { textPath: string; eid: string; path: string; label: string }) {
  const { t } = useT();
  const counts = useCounts(textPath);
  const here = counts.data?.articles[eid];
  const navigate = useNavigate();
  return (
    <Link to={`/discussion${path}`}
          onClick={(e) => {
            if (e.metaKey || e.ctrlKey || e.shiftKey) return;
            e.preventDefault();
            // The article's number becomes its discussion's (U7 of the Moroccan-design review).
            go(navigate, `/discussion${path}`, document.getElementById(eid)?.querySelector<HTMLElement>('[data-pill]'), 'article-talk');
          }}
          aria-label={here ? t('talkLabel', { label, count: here.count }) : undefined}
          className="inline-flex h-11 items-center gap-2 rounded-control px-3 text-body text-ink no-underline hover:bg-talk-wash hover:text-talk"
          data-noprint>
      <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" aria-hidden="true">
        <path d="M4 5h16v11H9l-5 4z" />
      </svg>
      {t('talkTab')}
      {here ? <span className="rounded-full bg-talk-wash px-2 py-0.5 text-meta font-semibold text-talk">{here.count}</span> : null}
    </Link>
  );
}
