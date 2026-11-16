import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import '@/shared/locales/pages';
import { api } from '@/shared/services/api';
import { Sheet } from '@/shared/components/Sheet';
import type { ArticleItem } from '../corpus.api';
import { AR, longDate } from '../format';
import { Diff } from './ArticleHistory';

type Proposal = {
  bill: { path: string; title: string; name: { ar: string; fr: string } | null; article: string; stage: string | null; since: string | null };
  verb: string;
  effective_on: string | null;
  when: string;
  partial: boolean;
  wording: string[] | null;
  new: boolean;
  before: string;
  after: string | null;
  unplaced: string;
  diff: NonNullable<ArticleItem['diff']> | null;
};

/** A bill's proposal for an article of the law in force (the finance-bill review, P2): one dashed line under
 *  the law's words — a bill is a draft, never the law — opening what the bill would write, word by word where the
 *  links pipeline can place it, else the bill's own words beside today's. */
export default function Proposed({ a }: { a: ArticleItem }) {
  const { t, i18n } = useTranslation();
  const [open, setOpen] = useState(false);
  const p = a.proposed;
  if (!p) return null;
  const bill = (i18n.language === 'fr' ? p.name?.fr : p.name?.ar) ?? '';
  return (
    <>
      <button type="button" onClick={() => setOpen(true)} aria-haspopup="dialog" data-noprint style={DASHED}
              className="mt-4 flex min-h-12 w-full max-w-[64ch] items-start gap-3 rounded-control bg-sheet px-4 py-3 text-start hover:bg-paper">
        <DraftIcon />
        <span className="flex min-w-0 flex-col gap-0.5">
          <span className="text-body font-semibold text-ink">{t(p.verb === 'added' ? 'pages:proposed.bandAdded' : 'pages:proposed.band', { bill })}</span>
          {p.effective_on ? <span className="text-meta text-ink-soft">{t(p.partial ? 'pages:proposed.fromPartial' : 'pages:proposed.from', { date: longDate(p.effective_on, i18n.language) })}</span> : null}
          <span className="text-meta font-medium text-stamp">{t('pages:proposed.open')}</span>
        </span>
      </button>
      {open ? (
        <Sheet label={t('pages:proposed.title', { bill })} onClose={() => setOpen(false)} centered wide closeButton>
          <Proposals path={a.path} bill={bill} />
        </Sheet>
      ) : null}
    </>
  );
}

function Proposals({ path, bill }: { path: string; bill: string }) {
  const { t, i18n } = useTranslation();
  const q = useQuery({
    queryKey: ['proposed', path],
    queryFn: () => api<{ path: string; proposals: Proposal[] }>(`/corpus/proposed/?path=${encodeURIComponent(path)}`),
    staleTime: 600_000,
  });
  return (
    <div className="flex flex-col gap-5 px-5 pb-6 pt-2">
      <h2 className="m-0 text-h3 font-semibold">{t('pages:proposed.title', { bill })}</h2>
      {q.isPending ? <p className="m-0 text-body text-ink-soft">{t('pages:proposed.loading')}</p> : null}
      {q.data?.proposals.map((p, i) => (
        <section key={i} className="flex flex-col gap-3">
          <p className="m-0 flex flex-wrap items-center gap-x-3 gap-y-1.5 text-meta">
            <span style={DASHED} className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 font-medium text-ink">
              <DraftIcon small />{t('corpus.types.bill')} · {t('pages:proposed.notLaw2')}
            </span>
            {p.bill.stage ? (
              <span className="text-ink-soft">
                {t(`pages:proposed.stages.${p.bill.stage}`)}{p.bill.since ? `${t('corpus.listSep')}${longDate(p.bill.since, i18n.language)}` : ''}
              </span>
            ) : null}
            <Link to={`${p.bill.path}/${articleEid(p.bill.article)}`} className="font-medium no-underline">
              {t('pages:proposed.article', { article: p.bill.article })}
            </Link>
          </p>
          {p.effective_on && !p.partial ? <p className="m-0 text-body">{t('pages:proposed.when', { date: longDate(p.effective_on, i18n.language) })}</p> : null}
          {p.partial && p.when ? (
            <div className="flex flex-col gap-1">
              <p className="m-0 text-body">{t('pages:proposed.whenPartial')}</p>
              <p lang="fr" dir="ltr" className="m-0 rounded-control bg-paper px-4 py-2 text-meta">{p.when}</p>
            </div>
          ) : null}
          {p.diff ? <Diff diff={p.diff} since={null} note={t('pages:proposed.diff')} /> : p.wording?.length ? (
            <div style={DASHED} className="rounded-control px-4 py-3">
              <p className="m-0 mb-2 text-meta text-ink-soft">{t('pages:proposed.wording')}</p>
              <div {...AR} className="flex flex-col gap-1 font-law text-law leading-loose">
                {p.wording.map((line, j) => <p key={j} className="m-0">{line}</p>)}
              </div>
            </div>
          ) : null}
        </section>
      ))}
      <p className="m-0 rounded-control bg-paper px-4 py-3 text-body">{t('pages:proposed.notLaw')}</p>
      {q.data?.proposals[0] ? (
        <Link to={q.data.proposals[0].bill.path} className="font-medium no-underline">{t('pages:proposed.whole')}</Link>
      ) : null}
    </div>
  );
}

/** The bill's own article by its label: «المادة 7» → art_7. */
function articleEid(label: string): string {
  const n = label.match(/\d+/)?.[0];
  return n ? `art_${n}` : '';
}

/** A bill's mark: «مشروع قانون · ليس قانونا بعد» in dashes, a draft; with `to`, its file's page. */
export function BillStamp({ page, to }: { page?: number | null; to?: string | null }) {
  const { t } = useTranslation();
  const inner = <><DraftIcon small />{t('corpus.types.bill')} · {page ? t('stamp.page', { page }) : t('pages:proposed.notLaw2')}</>;
  const cls = 'inline-flex max-w-full items-center gap-1.5 rounded-full px-2.5 py-1 text-meta font-medium leading-tight text-ink no-underline';
  return to ? <Link to={to} title={t('article.seePage')} data-stamp style={DASHED} className={cls}>{inner}</Link>
    : <span data-stamp style={DASHED} className={cls}>{inner}</span>;
}

/** Under a bill's title (P1): its mark, and on request what a bill is — the government's text, which both chambers may
 *  change, law only once voted and published. In «حول هذا النص» it says when it was filed. */
export function BillHead({ since, compact }: { since: string; compact: boolean }) {
  const { t, i18n } = useTranslation();
  const [open, setOpen] = useState(false);
  const id = compact ? 'bill-note-short' : 'bill-note';
  return (
    <div className="flex flex-col items-start gap-2">
      <p className="m-0 flex flex-wrap items-center gap-x-3 gap-y-1.5 text-body">
        <BillStamp />
        {compact ? null : <span className="text-ink-soft">{t('pages:proposed.stages.filed')}{t('corpus.listSep')}{longDate(since, i18n.language)}</span>}
        <button type="button" onClick={() => setOpen((o) => !o)} aria-expanded={open} aria-controls={id}
                className="inline-flex h-10 items-center gap-1 rounded-full px-2 font-medium text-stamp hover:bg-wash" data-noprint>
          {t('pages:proposed.whatIsThis')}
        </button>
      </p>
      <p id={id} hidden={!open} className="m-0 max-w-[64ch] rounded-control bg-paper px-4 py-3 text-body leading-relaxed print:block">
        {t('pages:proposed.billNote')}
      </p>
    </div>
  );
}

/** A bill's marks are drawn in dashes: a draft (a style, for the stylesheet's budget). */
const DASHED = { border: '1px dashed var(--color-ink-soft)' };

/** A draft: a sheet with a pen across it. */
function DraftIcon({ small = false }: { small?: boolean }) {
  const s = small ? 15 : 20;
  return (
    <svg aria-hidden="true" width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"
         strokeLinecap="round" strokeLinejoin="round" className={`shrink-0 ${small ? '' : 'mt-0.5 text-ink-soft'}`}>
      <path d="M14 3H6v18h12V9z" strokeDasharray="3 2.5" /><path d="M10 15l7.5-7.5 2 2L12 17h-2z" />
    </svg>
  );
}
