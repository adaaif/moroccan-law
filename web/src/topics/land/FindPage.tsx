import { lazy, Suspense, useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { AR, longDate } from '@/features/corpus/format';
import { api } from '@/shared/services/api';
import { Button, EmptyState, LinesSkeleton } from '@/shared/components/ui';
import { KitPage } from '../kit/parts';
import { useToolState } from '../kit/tool/state';
import { PlotMark } from '../kit/Plot';
import { useLandT } from './strings';

const FollowButton = lazy(() => import('@/features/follows/FollowButton'));

type Row = { row: number; plot: string; property: string; ref: string; area: string; owners: string[]; owners_count: number; notes: string };
type Found = {
  path: string; kind: string; date: string; issue: string; page: number | null; title: string;
  communes: string[]; provinces: string[]; properties: string[]; rows_total: number; rows: Row[];
};
type Answer = { query: string; count: number; texts: Found[]; place: { commune: string; since: number } | null };

/** Each kind of land text drawn as the plot the doors use: an expropriation's road band, a delimitation's stones… */
const PLOT: Record<string, string> = {
  expropriation: 'expro', utility: 'expro', renewal: 'expro', occupation: 'build', road: 'expro', delimitation: 'register',
  collective: 'collective', plan: 'plan', domain: 'divide', forest: 'own',
};
const EXAMPLES = ['رباط الخير', 'F/18820', 'الدورير'];

/** «أرضي فالجريدة الرسمية» (the land review, M8–M10): a commune, a property's name, a title or requisition number,
 *  or a name as the BO printed it → every land text since 2019 that names it, newest first, each as a stop on the
 *  place's line: its kind, date and BO page, the plots of its table that hold what was typed (or its first), and what
 *  that kind of text starts, with its articles. A commune can be followed. The tables are read by machine and a person
 *  checks a sample before the public sees it (the tool waits for review). The query lives in the address. */
export default function FindPage({ slug }: { slug: string }) {
  const { t, i18n } = useLandT();
  const lang = i18n.language === 'fr' ? 'fr' : 'ar';
  const [s, set] = useToolState({ q: '' });
  const [typed, setTyped] = useState(s.q);
  const q = useQuery({
    queryKey: ['land-places', s.q],
    queryFn: () => api<Answer>(`/topics/land/places/?q=${encodeURIComponent(s.q)}`),
    enabled: s.q.trim().length >= 2,
    staleTime: 10 * 60_000,
  });
  const submit = (e: FormEvent) => { e.preventDefault(); set({ q: typed.trim() }); };
  const a = q.data;
  return (
    <KitPage slug={slug} title={t('find.title')} lead={t('find.lead')}>
      <form role="search" onSubmit={submit} className="flex flex-col gap-2 rounded-card bg-sheet px-5 py-4 sm:px-7">
        <label htmlFor="land-find" className="text-body font-semibold">{t('find.box')}</label>
        <div className="flex gap-2">
          <input id="land-find" type="search" dir="auto" value={typed} onChange={(e) => setTyped(e.target.value)}
                 className="min-h-12 min-w-0 flex-1 rounded-control border border-field bg-sheet px-3 text-lead" />
          <Button type="submit">{t('find.search')}</Button>
        </div>
        <p className="m-0 flex flex-wrap items-center gap-2 text-meta text-ink-soft">
          {t('find.examples')}:
          {EXAMPLES.map((x) => (
            <button key={x} type="button" onClick={() => { setTyped(x); set({ q: x }); }} dir="auto"
                    className="inline-flex min-h-11 items-center rounded-full border border-field bg-sheet px-3 text-body text-ink">{x}</button>
          ))}
        </p>
      </form>

      {!s.q ? null : q.isLoading ? <LinesSkeleton /> : !a?.count ? (
        <EmptyState title={t('find.none', { q: s.q })} />
      ) : (
        <>
          <header className="flex flex-wrap items-end justify-between gap-3">
            <div className="flex flex-col">
              <h2 dir="auto" className="m-0 text-h2 font-bold">{a.place?.commune ?? s.q}</h2>
              <p className="m-0 text-body text-ink-soft">{t('find.since', { texts: t('find.texts', { count: a.count }), year: a.place?.since ?? new Date(a.texts[a.texts.length - 1].date).getFullYear() })}</p>
            </div>
            {a.place ? <Suspense fallback={null}><FollowButton path={`/places/${a.place.commune}`} /></Suspense> : null}
          </header>
          <p className="m-0 text-meta text-ink-soft">{t('find.names')}</p>
          {/* The place's line: each text a stop, newest first, its plot drawn by its kind. */}
          <ol className="m-0 flex list-none flex-col gap-3 p-0">
            {a.texts.map((x) => <Stop key={x.path} x={x} lang={lang} />)}
          </ol>
        </>
      )}
    </KitPage>
  );
}

function Stop({ x, lang }: { x: Found; lang: 'ar' | 'fr' }) {
  const { t } = useLandT();
  return (
    <li className="flex gap-3 rounded-card bg-sheet px-4 py-4 sm:px-5">
      <PlotMark plot={PLOT[x.kind] ?? 'buy'} />
      <div className="flex min-w-0 flex-1 flex-col gap-2">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <span className="rounded-full px-2.5 text-meta font-semibold" style={{ lineHeight: '28px', background: 'color-mix(in srgb, var(--color-sign-red) 12%, var(--color-sheet))', color: 'var(--color-sign-red)' }}>
            {t(`find.kinds.${x.kind}`)}
          </span>
          <span className="text-meta text-ink-soft">{longDate(x.date, lang)}</span>
        </div>
        <Link {...AR} to={x.path} className="text-body font-semibold leading-snug text-ink no-underline hover:text-stamp">{x.title}</Link>
        <span className="text-meta text-ink-soft">
          {lang === 'ar' ? `الجريدة الرسمية ${x.issue}` : `BO n° ${x.issue}`}{x.page ? (lang === 'ar' ? ` · الصفحة ${x.page}` : ` · p. ${x.page}`) : ''}
          {x.provinces.length ? ` · ${x.provinces.join('، ')}` : ''}
        </span>
        {x.rows.length ? (
          <div className="flex flex-col gap-2">
            {x.rows.map((r) => <Plot key={r.row} r={r} />)}
            {x.rows_total > x.rows.length ? <span className="text-meta text-ink-soft">{t('find.rows')}: {x.rows_total}</span> : null}
          </div>
        ) : null}
        <p lang={lang} className="m-0 text-meta">{t(`find.thens.${x.kind}`)}</p>
      </div>
    </li>
  );
}

/** One row of the decree's table, as printed: the plot, its property and number, its area, the owners named. */
function Plot({ r }: { r: Row }) {
  const { t } = useLandT();
  const [open, setOpen] = useState(false);
  const cell = (label: string, value: string, wide = false) => value ? (
    <span className="flex min-w-0 flex-col bg-sheet px-2.5 py-1.5" style={wide ? { gridColumn: '1 / -1' } : undefined}>
      <span className="text-meta text-ink-soft">{label}</span>
      <span dir="auto" className="text-body font-semibold leading-snug" style={{ overflowWrap: 'anywhere' }}>{value}</span>
    </span>
  ) : null;
  return (
    <div className="grid grid-cols-2 gap-px overflow-hidden rounded-control border border-rule bg-rule">
      {cell(t('find.plot'), r.plot)}
      {cell(t('find.area'), r.area ? t('find.m2', { n: r.area }) : '')}
      {cell(t('find.property'), r.property, true)}
      {r.owners.length ? (
        <span className="flex flex-col bg-sheet px-2.5 py-1.5" style={{ gridColumn: '1 / -1' }}>
          <button type="button" aria-expanded={open} onClick={() => setOpen(!open)} className="flex min-h-11 items-center justify-between text-start">
            <span className="text-meta text-ink-soft">{t('find.owners')}</span>
            <span className="text-body font-semibold">{r.owners_count} ⌄</span>
          </button>
          {open ? <ul className="m-0 flex list-none flex-col gap-0.5 p-0">{r.owners.map((o, i) => <li key={i} dir="auto" className="text-meta">{o}</li>)}</ul> : null}
        </span>
      ) : null}
      {cell(t('find.notes'), r.notes, true)}
    </div>
  );
}
