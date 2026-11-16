import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import type { IssuePage } from './corpus.api';

/** The issue as paper: one mark per page, the pages where a text starts in stamp violet. */
export function PageStrip({ documentId, pages, starts }: { documentId: number; pages: IssuePage[]; starts: Set<number> }) {
  const { t } = useTranslation();
  return (
    <nav aria-label={t('corpus.pageStrip')} className="flex flex-wrap gap-[3px]">
      {pages.map((p) => {
        const start = p.printed_number !== null && starts.has(p.printed_number);
        return (
          <Link
            key={p.index}
            to={`/pages/${documentId}/${p.index}`}
            title={t('corpus.pageLong', { page: p.printed_number ?? p.index + 1 })}
            aria-label={t('corpus.pageLong', { page: p.printed_number ?? p.index + 1 })}
            className={`block h-7 w-[9px] rounded-[2px] max-sm:pointer-events-none ${
              start ? 'bg-stamp hover:bg-stamp-deep' : 'bg-tick hover:bg-ink-soft'
            }`}
          />
        );
      })}
    </nav>
  );
}
