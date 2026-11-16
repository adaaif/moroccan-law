import { useTranslation } from 'react-i18next';
import { Link, useParams } from 'react-router-dom';
import { useIssueQuality } from './corpus.api';
import { AR, issueNo, longDate } from './format';
import { usePageTitle } from '@/shared/services/title';
import { Page, PageSkeleton } from '@/shared/components/ui';
import { LoadError } from '@/features/corpus/NotFound';
import '@/shared/locales/pages';

const ORDER = ['confirmed', 'layer', 'unconfirmed', 'scan', 'short', 'none'] as const;
const SWATCH: Record<string, string> = {
  confirmed: 'bg-in-force', layer: 'bg-in-force', unconfirmed: 'bg-amended', scan: 'bg-stamp', short: 'bg-amended',
  none: 'bg-tick',
};

/** «جودة القراءة»: an issue page by page — how each was read and whether the PDF's own text vouches for the
 *  reading — the texts its contents list that the pages did not yield, and the readers' open reports. */
export default function IssueQualityPage() {
  const { edition = '', number = '' } = useParams();
  const { t, i18n } = useTranslation();
  usePageTitle([t('pages:quality.title')]);
  const q = useIssueQuality(edition, number);
  if (q.isLoading) return <Shell><PageSkeleton /></Shell>;
  if (!q.data) return <Shell><LoadError error={q.error} retry={() => void q.refetch()} /></Shell>;
  const d = q.data;
  const total = d.pages.length;
  const vouched = d.counts.confirmed + d.counts.layer;

  return (
    <Shell>
      <nav className="text-meta">
        <Link to={`/bo/${d.edition}/${d.key}`} className="no-underline">{t('corpus.issueTitle', { number: issueNo(d, t) })}</Link>
      </nav>
      <header className="flex flex-col gap-2">
        <h1 className="m-0 font-law text-h1 font-semibold">{t('pages:quality.title')}</h1>
        <p className="m-0 max-w-[65ch] text-lead text-ink-soft">{t('pages:quality.lead', { date: longDate(d.date, i18n.language) })}</p>
      </header>

      <dl className="m-0 grid gap-4 sm:grid-cols-3">
        <Fact value={t('pages:quality.of', { a: vouched, b: total })} label={t('pages:quality.vouched')} />
        <Fact value={t('pages:quality.of', { a: d.texts, b: d.texts + d.not_found.length })} label={t('pages:quality.textsFound')} />
        <Fact value={String(d.open_reports)} label={t('pages:quality.openReports')} />
      </dl>

      <section className="flex flex-col gap-3 rounded-control border border-rule bg-sheet p-5">
        <h2 className="m-0 text-body font-semibold">{t('pages:quality.pages')}</h2>
        <ul className="m-0 flex list-none flex-wrap gap-x-5 gap-y-1 p-0 text-meta text-ink-soft">
          {ORDER.filter((k) => d.counts[k]).map((k) => (
            <li key={k} className="flex items-center gap-2">
              <span aria-hidden="true" className={`size-3 rounded-sm ${SWATCH[k]}`} />
              {t(`pages:quality.legend.${k}`)} <span className="tabular-nums">({d.counts[k]})</span>
            </li>
          ))}
        </ul>
        <ol className="m-0 grid list-none grid-cols-[repeat(auto-fill,minmax(2.75rem,1fr))] gap-1.5 p-0">
          {d.pages.map((p) => (
            <li key={p.index}>
              <Link to={`/pages/${d.document_id}/${p.index}`} title={`${t('corpus.pageLong', { page: p.printed ?? p.index + 1 })} — ${t(`pages:quality.legend.${p.reading}`)}`}
                    className={`flex h-11 flex-col items-center justify-center rounded-control text-meta tabular-nums text-on-stamp no-underline hover:opacity-80 ${SWATCH[p.reading]}`}>
                {p.printed ?? p.index + 1}
                {p.suspect ? <span aria-label={t('pages:quality.suspect')} className="leading-none">•</span> : null}
              </Link>
            </li>
          ))}
        </ol>
      </section>

      {d.not_found.length ? (
        <section className="flex flex-col gap-3">
          <h2 className="m-0 text-body font-semibold">{t('pages:quality.notFoundTitle')}</h2>
          <p className="m-0 max-w-[70ch] text-meta text-ink-soft">{t('pages:quality.notFoundLead')}</p>
          <ul className="m-0 flex list-none flex-col gap-2 p-0">
            {d.not_found.map((x, i) => (
              <li key={i} className="rounded-control border border-rule bg-sheet px-4 py-3">
                <span {...AR} className="font-law text-law leading-snug">{x.title}</span>
                {x.page ? <span className="ms-2 text-meta text-ink-soft">{t('corpus.pageLong', { page: x.page })}</span> : null}
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </Shell>
  );
}

function Fact({ value, label }: { value: string; label: string }) {
  return (
    <div className="flex flex-col gap-1 rounded-control border border-rule bg-sheet px-5 py-4">
      <dd className="m-0 font-law text-h2 font-semibold tabular-nums">{value}</dd>
      <dt className="text-meta text-ink-soft">{label}</dt>
    </div>
  );
}

function Shell({ children }: { children: React.ReactNode }) {
  return <Page width="wide" className="gap-7">{children}</Page>;
}
