import { lazy, Suspense } from 'react';
import { useParams } from 'react-router-dom';
import { LoadError } from '@/features/corpus/NotFound';
import { longDate } from '@/features/corpus/format';
import { Note, Page, PageSkeleton } from '@/shared/components/ui';
import { pick, useKitItem, useKitT, type Reform } from './api';
import { Cites, KitPage, Stops } from './parts';

const FollowButton = lazy(() => import('@/features/follows/FollowButton'));

/** A reform, tracked honestly (F12 of the family plan): its state said first, among law, bill and announcement, never
 *  mixed; the official record by date; the answers published, beside the articles in force today; what circulates
 *  and is not so. «تابع الإصلاح» tells the reader in «أنا» when the record grows. */
export default function ReformPage({ slug }: { slug: string }) {
  // The family's one reform sits at /reform; a topic that follows several changes (work, T14) at /reform/<key>.
  const { key = 'reform' } = useParams();
  const { t, i18n } = useKitT();
  const q = useKitItem<Reform>(slug, 'reform', key);
  const lang = i18n.language;
  if (q.isLoading) return <Page width="reading"><PageSkeleton kind="text" /></Page>;
  const r = q.data;
  if (!r) return <Page width="reading"><LoadError error={q.error} retry={() => void q.refetch()} /></Page>;
  const reached = r.stages.findIndex((s) => s.key === (r.at ?? r.stage));
  return (
    <KitPage slug={slug} item={r} title={pick(r.title, lang)} lead={pick(r.lead, lang)}>
      <section className="flex flex-col gap-4 rounded-card bg-sheet px-5 py-5 sm:px-7" aria-labelledby="reform-state">
        <h2 id="reform-state" className="m-0 text-lead font-semibold">{t('reform.state')}</h2>
        {/* The stages on one line, in their order (G6 of the family-papers review: a 2 × 2 grid lost it). */}
        <Stops stages={r.stages.map((s) => pick(s.label, lang))} reached={reached} />
        <p lang={lang} className="m-0 text-lead font-medium">{pick(r.line, lang)}</p>
        {r.path?.length ? (
          <ol className="m-0 flex list-none flex-col p-0">
            {r.path.map((s, i) => (
              <li key={s.key} aria-current={i === reached ? 'step' : undefined}
                  className={`flex flex-col gap-1.5 border-t border-rule py-3 first:border-t-0 ${i === reached ? '' : 'text-ink-soft'}`}>
                <p lang={lang} className="m-0 text-body">
                  <span className={`font-semibold ${i === reached ? 'text-amended' : 'text-ink'}`}>{r.stages[i] ? pick(r.stages[i].label, lang) : ''}</span>{t('reform.pathSep')}{pick(s.rule, lang)}
                </p>
                <Cites cites={s.cites} />
              </li>
            ))}
          </ol>
        ) : null}
        <div className="flex flex-wrap items-center gap-3">
          <p className="m-0 text-meta text-ink-soft">{t('reform.lastCheck', { date: longDate(r.checked_on, lang) })}</p>
          <Suspense fallback={null}><FollowButton path={key === 'reform' ? `/topics/${slug}/reform` : `/topics/${slug}/reform/${key}`} /></Suspense>
        </div>
      </section>

      <section className="flex flex-col gap-3 rounded-card bg-sheet px-5 py-5 sm:px-7">
        <h2 className="m-0 text-lead font-semibold">{t('reform.timeline')}</h2>
        <ol className="m-0 flex list-none flex-col p-0">
          {r.timeline.map((e) => (
            <li key={e.date} className="flex gap-4 border-t border-rule py-3 first:border-t-0">
              <time dateTime={e.date} className="w-28 shrink-0 text-meta font-semibold text-ink-soft">{longDate(e.date, lang)}</time>
              <div className="flex min-w-0 flex-1 flex-col gap-1.5">
                <p lang={lang} className="m-0 text-body">{pick(e.text, lang)}</p>
                {e.source?.url ? <a href={e.source.url} target="_blank" rel="noreferrer" className="self-start text-meta">{pick(e.source.name, lang)}</a>
                  : e.source ? <span className="self-start text-meta text-ink-soft">{pick(e.source.name, lang)}</span> : null}
                <Cites cites={e.cites} />
              </div>
            </li>
          ))}
        </ol>
      </section>

      {r.questions?.length ? <section className="flex flex-col gap-4 rounded-card bg-sheet px-5 py-5 sm:px-7">
        <div className="flex flex-col gap-1">
          <h2 className="m-0 text-lead font-semibold">{t('reform.questions')}</h2>
          <p className="m-0 text-meta text-ink-soft">{t('reform.questionsLead')}</p>
        </div>
        {(r.groups ?? []).map((g) => {
          const qs = (r.questions ?? []).filter((x) => x.group === g.key);
          if (!qs.length) return null;
          return (
            <div key={g.key} className="flex flex-col gap-2">
              <h3 lang={lang} className="m-0 text-body font-semibold text-amended">{pick(g.label, lang)}</h3>
              <ul className="m-0 flex list-none flex-col p-0">
                {qs.map((x) => (
                  <li key={x.n} className="flex flex-col gap-1.5 border-t border-rule py-3 first:border-t-0">
                    <p lang={lang} className="m-0 text-body font-medium">{pick(x.subject, lang)}</p>
                    {x.answer ? <p lang={lang} className="m-0 text-meta"><span className="font-semibold">{t('reform.answer')}: </span>{pick(x.answer, lang)}</p> : null}
                    {x.cites?.length ? (
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-meta text-ink-soft">{t('reform.today')}:</span><Cites cites={x.cites} />
                      </div>
                    ) : null}
                  </li>
                ))}
              </ul>
            </div>
          );
        })}
      </section> : null}

      {r.rumours?.length ? <section className="flex flex-col gap-3">
        <h2 className="m-0 text-lead font-semibold">{t('reform.rumours')}</h2>
        {r.rumours.map((x, i) => (
          <Note key={i} tone="warn">
            <p lang={lang} className="m-0 text-body"><span className="font-semibold">{t('reform.claim')}: </span>«{pick(x.claim, lang)}»</p>
            <p lang={lang} className="m-0 text-body"><span className="font-semibold">{t('reform.truth')}: </span>{pick(x.truth, lang)}</p>
            <Cites cites={x.cites} />
          </Note>
        ))}
      </section> : null}
    </KitPage>
  );
}
