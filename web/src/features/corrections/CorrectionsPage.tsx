import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { BlogLinks } from '@/features/blog/BlogLinks';
import { shortName } from '@/features/corpus/article/message';
import { longDate } from '@/features/corpus/format';
import { api } from '@/shared/services/api';
import { useSession } from '@/shared/stores/session';
import '@/shared/locales/pages';
import { usePageTitle } from '@/shared/services/title';
import { Page } from '@/shared/components/ui';

type Row = {
  id: number; path: string; article: string; text: string; wrong: string; right: string; before: string; after: string;
  source: 'proofread' | 'context' | 'report' | 'review' | 'page' | 'witness' | 'reading' | 'split'; evidence: { wrong?: number; right?: number; pair?: boolean }; on: string;
  /** In how many places a long correction (a page read again) differs; its words are the first three. */
  places?: number;
};
const FIRST = 30;
type Listed = { applied: Row[]; waiting: Row[]; can_decide: boolean; counts: { applied: number; waiting: number; reports_open: number; reports_fixed: number } };

/** /corrections, «ما صححناه» (R7 of the for-everyone review): every word put right in a text, where, and how it was found.
 *  The machine only proposes; a person compares with the printed page and applies. Staff decide here too. */
export default function CorrectionsPage() {
  const { t, i18n } = useTranslation();
  usePageTitle([t('pages:corrections.title')]);
  const signedIn = useSession((s) => s.tokens !== null);
  const client = useQueryClient();
  const key = ['quality', 'corrections', signedIn];
  const listed = useQuery({ queryKey: key, queryFn: () => api<Listed>('/quality/corrections/') });
  const decide = useMutation({
    mutationFn: ({ id, verb }: { id: number; verb: 'apply' | 'reject' }) => api<Listed>(`/quality/corrections/${id}/${verb}/`, { method: 'POST' }),
    onSuccess: (data) => client.setQueryData(key, data),
  });
  const d = listed.data;
  const [all, setAll] = useState(false);
  return (
    <Page width="reading" className="gap-5">
      <header className="flex flex-col gap-2 px-1">
        <h1 className="m-0 text-h2 font-bold">{t('pages:corrections.title')}</h1>
        <p className="m-0 max-w-[62ch] text-body leading-relaxed text-ink-soft">{t('pages:corrections.lead')}</p>
      </header>
      {/* The four counts hold their place while the answer comes: lines stood here first and the page jumped (RD16). */}
      <ul className="m-0 grid list-none grid-cols-2 gap-2 p-0 sm:grid-cols-4" aria-busy={!d}>
        {(['applied', 'waiting', 'reports_open', 'reports_fixed'] as const).map((k) => (
          <li key={k} className="flex flex-col rounded-card bg-sheet px-4 py-3">
            <span className="text-h2 font-bold leading-tight">{d ? d.counts[k] : '…'}</span>
            <span className="text-meta text-ink-soft">{t(`pages:corrections.count.${k}`)}</span>
          </li>
        ))}
      </ul>
      <p className="m-0 rounded-card bg-wash px-4 py-3 text-body">{t('pages:corrections.howToReport')}</p>

      {d?.can_decide && d.waiting.length ? (
        <section className="flex flex-col gap-3 rounded-card bg-amended-wash px-5 py-5 sm:px-7">
          <h2 className="m-0 text-lead font-bold text-amended">{t('pages:corrections.waiting', { count: d.counts.waiting })}</h2>
          <p className="m-0 text-meta">{t('pages:corrections.checkFirst')}</p>
          <ul className="m-0 flex list-none flex-col gap-2.5 p-0">
            {d.waiting.slice(0, 60).map((c) => (
              <li key={c.id} className="flex flex-col gap-2 rounded-card bg-sheet px-4 py-3">
                <Where c={c} />
                <Change c={c} />
                <span className="text-meta text-ink-soft">
                  {t(`pages:corrections.source.${c.source}`)}
                  {c.evidence.right ? ` · ${t(c.evidence.pair ? 'pages:corrections.pairEvidence' : 'pages:corrections.evidence', { count: c.evidence.right })}` : ''}
                </span>
                <span className="flex gap-2">
                  <button type="button" disabled={decide.isPending} onClick={() => decide.mutate({ id: c.id, verb: 'apply' })}
                          className="h-10 rounded-control bg-stamp px-4 text-body font-semibold text-on-stamp hover:bg-stamp-deep disabled:opacity-60">{t('pages:corrections.apply')}</button>
                  <button type="button" disabled={decide.isPending} onClick={() => decide.mutate({ id: c.id, verb: 'reject' })}
                          className="h-10 rounded-control px-4 text-body ring-1 ring-rule disabled:opacity-60">{t('pages:corrections.reject')}</button>
                </span>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <section className="flex flex-col gap-3">
        <h2 className="m-0 px-1 text-lead font-bold">{t('pages:corrections.applied')}</h2>
        {d && !d.applied.length ? <p className="m-0 rounded-card bg-sheet px-5 py-4 text-ink-soft">{t('pages:corrections.none')}</p> : null}
        <ul className="m-0 flex list-none flex-col gap-2.5 p-0">
          {/* Thirty, then the rest when asked: the page was 560,000 px tall on a phone (RD22 of the readers review). */}
          {d?.applied.slice(0, all ? undefined : FIRST).map((c) => (
            <li key={c.id} className="flex flex-col gap-1.5 rounded-card bg-sheet px-4 py-3">
              <Where c={c} />
              <Change c={c} />
              <span className="text-meta text-ink-soft">
                {longDate(c.on.slice(0, 10), i18n.language)} · {t(`pages:corrections.source.${c.source}`)}
                {(c.places ?? 1) > 1 ? ` · ${t('pages:corrections.places', { count: c.places })}` : ''}
              </span>
            </li>
          ))}
        </ul>
        {d && !all && d.applied.length > FIRST ? (
          <button type="button" onClick={() => setAll(true)} className="min-h-11 self-start rounded-control px-4 text-body font-medium text-stamp ring-1 ring-rule">
            {t('pages:corrections.more', { count: d.applied.length - FIRST })}
          </button>
        ) : null}
      </section>
      {/* How the Bulletin corrects itself, as the blog counted it. */}
      <BlogLinks slugs={['errata']} />
    </Page>
  );
}

function Where({ c }: { c: Row }) {
  return (
    <Link to={c.path} lang="ar" dir="rtl" className="text-meta font-medium no-underline">
      {c.article}{c.text ? ` · ${shortName(c.text, 60)}` : ''}
    </Link>
  );
}

/** The words as they read and as they should: «… ثم [ألم ← لأم] الأم …». */
function Change({ c }: { c: Row }) {
  const { t } = useTranslation();
  return (
    <p lang="ar" dir="rtl" className="m-0 font-law text-law leading-relaxed">
      {c.before ? <span className="text-ink-soft">… {c.before} </span> : null}
      <del className="rounded bg-repealed/10 px-1 text-repealed" title={t('pages:corrections.was')}>{c.wrong}</del>
      <span aria-hidden="true" className="px-1 text-ink-soft">←</span>
      <ins className="rounded bg-talk-wash px-1 text-talk no-underline" title={t('pages:corrections.now')}>{c.right}</ins>
      {c.after ? <span className="text-ink-soft"> {c.after} …</span> : null}
    </p>
  );
}
