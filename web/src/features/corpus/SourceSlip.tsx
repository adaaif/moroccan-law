import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { documentFileUrl } from './corpus.api';
import { longDate } from './format';
import { Stamp } from './article/Stamp';

type Props = {
  issueNumber: string;
  date: string;
  page: number | null;
  documentId: number;
  pageIndex: number | null;
  compact?: boolean;
};

/** Every text and article names the paper it was read from: its stamp, the issue's date, and the page itself. */
export function SourceSlip({ issueNumber, date, page, documentId, pageIndex, compact }: Props) {
  const { t, i18n } = useTranslation();
  return (
    <div className={`flex items-start gap-4 ${compact ? 'rounded-control border border-rule bg-sheet p-3' : ''}`}>
      <Stamp issue={issueNumber} page={page} />
      <div className="flex min-w-0 flex-col gap-0.5 text-meta">
        <strong className="text-body font-semibold">{t('corpus.issueTitle', { number: issueNumber })}</strong>
        <span>{longDate(date, i18n.language)}</span>
        {page ? <span>{t('corpus.pageLong', { page })}</span> : null}
        <span className="mt-1.5 flex flex-wrap gap-x-4 gap-y-1">
          {pageIndex !== null ? (
            <Link to={`/pages/${documentId}/${pageIndex}`} className="font-medium no-underline">
              {t('corpus.openPage')}
            </Link>
          ) : null}
          <a href={documentFileUrl(documentId)} target="_blank" rel="noreferrer" className="no-underline">
            {t('corpus.openPdf')}
          </a>
        </span>
      </div>
    </div>
  );
}
