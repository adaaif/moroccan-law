import { useTranslation } from 'react-i18next';
import { longDate } from '@/features/corpus/format';
import type { PostSummary } from './blog.api';

/** A post's head, as the Bulletin's masthead: the blog's name and the post's number over a double rule, its day; the
 *  headline in the law's type, the lead, and while it is a draft, who still has to check and sign it. */
export function Head({ post }: { post: PostSummary }) {
  const { t, i18n } = useTranslation('blog');
  const lang = i18n.language;
  const side = lang === 'fr' ? 'fr' : 'ar';
  return (
    <header className="bp-head">
      <div className="bp-running">
        <span><b>{t('name')}</b> {t('number', { n: post.number })}</span>
        <span>{longDate(post.date ?? post.counted_on, lang)}</span>
      </div>
      <h1>{post.title[side]}</h1>
      <p className="bp-lead">{post.lead[side]}</p>
      {post.status === 'draft' ? <p className="bp-draft">{t('draft', { date: longDate(post.counted_on, lang) })}</p> : null}
    </header>
  );
}
