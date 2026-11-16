import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { longDate } from '@/features/corpus/format';
import { Page, PageSkeleton } from '@/shared/components/ui';
import { usePageTitle } from '@/shared/services/title';
import { usePosts } from './blog.api';
import './i18n';
import './blog.css';

/** /blog: «قانون بالأرقام», the posts, the newest first, each as a poster (HM41 of the hard-moment review: the index
 *  was 11,904 px of grey paragraphs and none of the posts' pictures): its own picture as a still miniature
 *  (public/blog/posters, `npm run blog:posters`), its number and day, its headline and two lines of its lead. Two
 *  columns from 640 px. A post with no poster yet shows its number in the frame. */
export default function BlogIndex() {
  const { t, i18n } = useTranslation('blog');
  const lang = i18n.language === 'fr' ? 'fr' : 'ar';
  usePageTitle([t('name')]);
  const posts = usePosts();
  return (
    <Page width="wide" className="bi">
      <header className="bi-head">
        <h1>{t('name')}</h1>
        <p>{t('index.lead')}</p>
      </header>
      {posts.data ? (
        <ol className="bi-list">
          {posts.data.posts.map((p) => (
            <li key={p.slug}>
              <Link to={`/blog/${p.slug}`}>
                <span className="bi-poster" aria-hidden="true">
                  <span>{p.number}</span>
                  <img src={`/blog/posters/${p.slug}.webp`} alt="" width={120} height={150} loading="lazy" decoding="async"
                       onError={(e) => { e.currentTarget.hidden = true; }} />
                </span>
                <span className="bi-words">
                  <span className="bi-meta">
                    {t('number', { n: p.number })}
                    <span>{longDate(p.date ?? p.counted_on, i18n.language)}</span>
                    {p.status === 'draft' ? <span className="bi-draft">{t('draftShort')}</span> : null}
                  </span>
                  <h2>{p.title[lang]}</h2>
                  <p>{p.lead[lang]}</p>
                </span>
              </Link>
            </li>
          ))}
        </ol>
      ) : <PageSkeleton />}
    </Page>
  );
}
