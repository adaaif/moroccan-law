import { lazy, Suspense, useState } from 'react';
import { useTranslation } from 'react-i18next';
import type { ArticleItem, TextDetail } from '../corpus.api';
import '@/shared/locales/pages';

const FrenchArticle = lazy(() => import('../history/FrenchArticle').then((m) => ({ default: m.FrenchArticle })));
const ArticleHistory = lazy(() => import('../history/Lazy').then((m) => ({ default: m.ArticleHistory })));
const ArticleLinks = lazy(() => import('../history/Lazy').then((m) => ({ default: m.ArticleLinks })));

type Extra = 'french' | 'diff' | 'history' | 'applied' | 'cited';

/** What else an article has, in one quiet line of words under it (N7 of the read-and-trusted review): «بالفرنسية ·
 *  تاريخها · 3 نصوص تحيل إليها», each opening its panel below. They were four outlined chips under every article. */
export default function Extras({ a, d, frenchFirst }: { a: ArticleItem; d: TextDetail; frenchFirst: boolean }) {
  const { t, i18n } = useTranslation();
  // An article people know by a name (F10 of the famous-articles review): the name said as the public's, under the law's words.
  const known = a.known_as && (i18n.language === 'fr' && a.known_as.fr.length ? a.known_as.fr : a.known_as.ar);
  const [open, setOpen] = useState<Extra | null>(null);
  const items: [Extra, string][] = [];
  if (!frenchFirst && a.french) items.push(['french', t('article.extras.french')]);
  if (a.diff) items.push(['diff', t('article.extras.diff')]);
  if (a.changes.length) items.push(['history', t('article.extras.history')]);
  if (a.applied_by?.length) items.push(['applied', t('article.extras.applied', { count: a.applied_by.length })]);
  if (a.cited_by?.length) items.push(['cited', t('article.extras.cited', { count: a.cited_by.length })]);
  // Changes shown as fact whose words this copy does not hold yet: said, never left under «عُدّلت» alone (RD2).
  const missing = [...new Set(a.changes.filter((c) => c.missing).map((c) => `${t(`corpus.types.${c.by.kind}`, { defaultValue: c.by.kind })} ${c.by.number.replace(/-/g, '.')}`))];
  if (!items.length && !known?.length && !missing.length) return null;
  return (
    <div data-noprint>
      {missing.length ? <p className="m-0 mt-2 text-meta font-medium text-amended">{t('pages:history.missing', { by: missing.join(t('corpus.listSep')) })}</p> : null}
      {known?.length ? <p className="m-0 mt-2 text-meta text-ink-soft">{t('article.knownAs', { names: known.map((n) => `«${n}»`).join(t('corpus.listSep')) })}</p> : null}
      {items.length ? <p className="m-0 mt-1 flex flex-wrap items-center gap-x-1 text-meta">
        {items.map(([k, words], i) => (
          <span key={k} className="inline-flex items-center gap-x-1">
            {i ? <span aria-hidden="true" className="text-muted">·</span> : null}
            <button type="button" onClick={() => setOpen(open === k ? null : k)} aria-expanded={open === k}
                    className={`inline-flex min-h-11 items-center px-1 font-medium ${open === k ? 'text-stamp-deep underline underline-offset-4' : k === 'diff' ? 'text-amended' : 'text-stamp'} hover:text-stamp-deep`}>
              {words}
            </button>
          </span>
        ))}
      </p> : null}
      {open === 'french' ? <Suspense fallback={null}><FrenchArticle a={a} consolidatedTo={d.french?.consolidated_to} show /></Suspense> : null}
      {open === 'diff' || open === 'history' ? (
        <Suspense fallback={null}><ArticleHistory a={a} beforeDate={d.version?.before?.valid_from ?? null} show={open} /></Suspense>
      ) : null}
      {open === 'applied' || open === 'cited' ? <Suspense fallback={null}><ArticleLinks a={a} show={open} /></Suspense> : null}
    </div>
  );
}
