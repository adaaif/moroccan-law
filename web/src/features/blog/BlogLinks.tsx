import { useId } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import '@/shared/locales/pages';
import '@/shared/design/french.css';
import { usePosts, type PostSummary } from './blog.api';
import './links.css';

/**
 * «قانون بالأرقام» where a reader already is (1 Nov 2026: without links from the pages people read, nobody would find
 * the posts): the posts a page is about (`slugs`, in that order), or the newest; on the home (`big`) with the
 * blog's lead. At the end of a post (`around`), under «مقالات أخرى», the newest, never itself. A draft says so, as on the blog. Nothing is drawn until the list comes,
 * or if it fails.
 */
export function BlogLinks({ slugs, around, most = 3, big = false }: {
  slugs?: string[];
  around?: string;
  most?: number;
  big?: boolean;
}) {
  const { t, i18n } = useTranslation();
  const lang = i18n.language === 'fr' ? 'fr' : 'ar';
  const id = useId();
  const posts = usePosts().data?.posts;
  if (!posts?.length) return null;
  const bySlug = new Map(posts.map((p) => [p.slug, p]));
  let rows: PostSummary[];
  if (slugs) rows = slugs.map((s) => bySlug.get(s)).filter((p): p is PostSummary => !!p);
  else if (around) rows = posts.filter((p) => p.slug !== around);
  else rows = posts;
  rows = rows.slice(0, most);
  if (!rows.length) return null;

  return (
    <section className={`bl${big ? ' big' : ''}${around ? ' after' : ''}`} aria-labelledby={id}>
      <header className="bl-head">
        <h2 id={id}>{t(around ? 'pages:blogLinks.more' : 'pages:blogLinks.name')}</h2>
        <Link to="/blog" className="bl-all">{t('pages:blogLinks.all')}</Link>
        {big ? <p>{t('pages:blogLinks.lead')}</p> : null}
      </header>
      <ol className="bl-list">
        {rows.map((p) => (
          <li key={p.slug}>
            <Link to={`/blog/${p.slug}`} lang={lang}>
              <span className="bl-meta">
                {t('pages:blogLinks.number', { n: p.number })}
                {p.status === 'draft' ? <span className="bl-draft">{t('pages:blogLinks.draft')}</span> : null}
              </span>
              <b>{p.title[lang]}</b>
              <span className="bl-lead">{p.lead[lang]}</span>
            </Link>
          </li>
        ))}
      </ol>
    </section>
  );
}
