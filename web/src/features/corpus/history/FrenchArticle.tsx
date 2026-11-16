import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import type { ArticleItem } from '../corpus.api';
import { longDate, paragraphs } from '../format';
import '@/shared/design/french.css';

/** An article's official French translation (C3), on request, below the Arabic, which alone is the law. A French
 *  consolidation (Adala's labour code, `consolidatedTo`) says so, and an article changed since says its French is older. */
export function FrenchArticle({ a, consolidatedTo, show = false }: {
  a: ArticleItem;
  consolidatedTo?: string | null;
  /** The translation alone, opened from the article's line of words (N7 of the read-and-trusted review). */
  show?: boolean;
}) {
  const { t } = useTranslation();
  const [chosen, setOpen] = useState(false);
  const open = show || chosen;
  if (!a.french) return null;
  return (
    <div className={show ? 'mt-2' : 'mt-3'} data-noprint>
      {show ? null : (
        <button type="button" onClick={() => setOpen((o) => !o)} aria-expanded={open} lang="fr"
                className={`rounded-full border px-3 py-1 text-meta font-medium ${open ? 'border-stamp bg-wash text-stamp' : 'border-rule text-stamp'}`}>
          {t(consolidatedTo ? 'french.showConsolidated' : 'french.show')}
        </button>
      )}
      {open ? (
        <div lang="fr" dir="ltr" className={`${show ? '' : 'mt-3 '}max-w-[70ch] rounded-control border border-rule bg-paper px-4 py-3 text-start`}>
          {a.french.older ? <p className="m-0 mb-2 text-meta font-medium text-amended">{t('french.older')}</p> : null}
          <p className="m-0 text-body font-semibold">{a.french.label}</p>
          {paragraphs(a.french.body).map((p, i) => <p key={i} className="m-0 mt-2 font-law-fr text-lead leading-relaxed">{p}</p>)}
          <p className="m-0 mt-3 text-meta text-ink-soft">{consolidatedTo
            ? t('french.consolidated', { date: longDate(consolidatedTo, 'fr') }) : t('french.note')}</p>
        </div>
      ) : null}
    </div>
  );
}
