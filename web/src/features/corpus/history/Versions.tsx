import { lazy, Suspense, useState } from 'react';
import { useTranslation } from 'react-i18next';
import type { TextDetail } from '../corpus.api';
import { longDate } from '../format';
import { Stamp } from '../article/Stamp';

const BillHead = lazy(() => import('./Proposed').then((m) => ({ default: m.BillHead })));

/** What a version assembled from later amendments is and is not (R6 of the for-everyone review): one quiet line — who
 *  assembled it and when — and, on request, the plain explanation (not official; the BO prevails; each change in an
 *  article's history names its issue). It used to be a dashed amber box above every such text. */
/** `compact` under the title: the chip and «ما معنى هذا؟»; who compiled it and when are in «حول هذا النص» (U4). */
export function ConsolidatedNote({ d, compact = false }: { d: TextDetail; compact?: boolean }) {
  const { t, i18n } = useTranslation();
  const [open, setOpen] = useState(false);
  const v = d.version;
  if (!v || v.consolidation === 'as_published') return null;
  if (v.consolidation === 'bill') return <Suspense fallback={null}><BillHead since={v.valid_from} compact={compact} /></Suspense>;
  // A version a model translated from the official French (BO 7410, no Arabic online): never a consolidation, never the
  // law's words (31 Oct 2026). Before 1956 (A of the Bulletin-from-No.-1 review): the Arabic edition never printed the text,
  // only the French one did, and the French as printed is the reference. One quiet line since 15 Nov 2026: the stamp's
  // chip, «ترجمة غير رسمية من الفرنسية», and what the reference is; who translated it is said on «عن «قانون»».
  if (v.consolidation === 'translation') {
    const frenchOnly = d.issue?.edition === 'translation_fr';
    return (
      <p className="m-0 flex max-w-[64ch] flex-wrap items-center gap-x-3 gap-y-1.5" role="note">
        <Stamp translated />
        <span className="text-meta text-ink-soft">
          {frenchOnly ? t('corpus.translatedRefFrenchOnly') : t('corpus.translatedRef', { issue: d.french?.issue_number ?? '' })}
        </span>
      </p>
    );
  }
  const asOf = (v.consolidation === 'sgg' || v.consolidation === 'adala' || v.consolidation === 'dgi') && v.source?.as_of
    ? v.source.as_of : v.consolidation === 'machine' ? v.valid_from : null;
  return (
    <div className="flex flex-col items-start gap-2">
      <p className="m-0 flex flex-wrap items-center gap-x-3 gap-y-1.5 text-body">
        <Stamp consolidated issued={v.as_issued} asOf={compact ? asOf : null} />
        {compact ? null : (
          <span className="text-ink-soft">
            {t(v.as_issued ? 'history.whoIssued' : `history.who.${v.consolidation}`)}{asOf ? `${t('corpus.listSep')}${longDate(asOf, i18n.language)}` : ''}
          </span>
        )}
        <button type="button" onClick={() => setOpen((o) => !o)} aria-expanded={open} aria-controls={compact ? 'consolidated-note-short' : 'consolidated-note'}
                className="inline-flex h-11 items-center gap-1 rounded-full px-2 font-medium text-stamp hover:bg-wash" data-noprint>
          <svg aria-hidden="true" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
               strokeLinecap="round"><circle cx="12" cy="12" r="9" /><path d="M12 11v5M12 8h.01" /></svg>
          {t('history.whatIsThis')}
        </button>
      </p>
      <p id={compact ? 'consolidated-note-short' : 'consolidated-note'} hidden={!open} className="m-0 max-w-[64ch] rounded-control bg-paper px-4 py-3 text-body leading-relaxed print:block">
        {t(v.as_issued ? 'history.issuedNote' : 'history.consolidatedNote')}
      </p>
    </div>
  );
}

/** The file a consolidation was read from (the SGG's, Adala's or the DGI's), and where the text first appeared. */
export function ConsolidationSlip({ d }: { d: TextDetail }) {
  const { t, i18n } = useTranslation();
  const s = d.version?.source;
  if (!s) return null;
  const who = d.version?.consolidation === 'adala' || d.version?.consolidation === 'dgi' ? d.version.consolidation : 'sgg';
  return (
    <div className="flex flex-col items-start gap-1 text-meta">
      <Stamp consolidated issued={d.version?.as_issued} className="mb-2" />
      <strong className="text-body font-semibold">{t(`history.${who}Name`)}</strong>
      {s.as_of ? <span>{t(`history.${who}AsOf`, { date: longDate(s.as_of, i18n.language) })}</span> : null}
      {s.first_issue ? <span className="text-ink-soft">{t('history.firstPublished', { number: s.first_issue, page: s.first_page ?? '' })}</span> : null}
      <span className="mt-1.5 flex flex-wrap gap-x-4 gap-y-1">
        <a href={`/api/sources/documents/${s.document_id}/file/`} target="_blank" rel="noreferrer" className="font-medium no-underline">
          {t(`history.${who}File`)}
        </a>
        <a href={s.url} target="_blank" rel="noreferrer" className="no-underline">{t(`history.${who}Site`)}</a>
      </span>
    </div>
  );
}
