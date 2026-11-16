import { lazy, Suspense, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, Navigate, useParams, useSearchParams } from 'react-router-dom';
import { BlogLinks } from '@/features/blog/BlogLinks';
import { Stamp } from '@/features/corpus/article/Stamp';
import NotFound, { LoadError } from '@/features/corpus/NotFound';
import { usePageTitle } from '@/shared/services/title';
import { Button, EmptyState, LinesSkeleton, Page } from '@/shared/components/ui';
import '@/shared/locales/pages';
import { n, named } from './format';
import { YearBars } from './parts';
import { sharePlace } from './share';
import { type Filters, type MentionRow, type Stamp as StampData, useMentions, usePlace, useTyped } from './places.api';
import './places.css';

const FollowButton = lazy(() => import('@/features/follows/FollowButton'));

/** The stamp of a text of the conventions edition says so: its numbers are its own. */
function Proof({ s }: { s: StampData }) {
  const { t } = useTranslation();
  return <Stamp issue={s.edition === 'conventions_ar' ? t('pages:places.eci', { number: s.issue }) : s.issue} page={s.page} to={s.to} />;
}

function Row({ m }: { m: MentionRow }) {
  const { t, i18n } = useTranslation();
  const lang = i18n.language;
  return (
    <li className="pl-row">
      <div className="pl-row-head">
        <Link to={m.path} className="pl-row-name" lang="ar" dir="rtl">
          {m.in_title ? t('pages:places.inTitle') : m.label}
          <span>{(lang === 'fr' && m.name.fr) || m.name.ar}</span>
        </Link>
        <time dateTime={m.date}>{m.date.slice(0, 4)}</time>
      </div>
      {m.snippet ? (
        <p className="pl-snip" lang="ar" dir="rtl">{m.snippet.before} <mark>{m.snippet.hit}</mark> {m.snippet.after}</p>
      ) : null}
      <div className="pl-row-foot">
        <Proof s={m.stamp} />
        <span className="pl-chip">{t(`pages:places.kinds.${m.kind}`)}</span>
        <span className="pl-chip">{t(`corpus.types.${m.type}`, { defaultValue: m.type })}</span>
      </div>
    </li>
  );
}

/** The second place a list must also name (PL20): typed, then picked. */
function WithPlace({ value, onPick }: { value?: string; onPick: (slug?: string) => void }) {
  const { t, i18n } = useTranslation();
  const [q, setQ] = useState('');
  const typed = useTyped(q);
  if (value) {
    return <button type="button" className="pl-filter on" onClick={() => onPick(undefined)} aria-label={t('pages:places.withClear')}>
      {t('pages:places.withOn', { name: value })} ✕</button>;
  }
  return (
    <span className="pl-with">
      <input type="search" dir="auto" value={q} onChange={(e) => setQ(e.target.value)} placeholder={t('pages:places.withHint')}
             aria-label={t('pages:places.with')} autoComplete="off" />
      {q.trim().length >= 2 && typed.data?.places.length ? (
        <ul className="pl-typed">
          {typed.data.places.slice(0, 6).map((p) => (
            <li key={p.slug}><button type="button" onClick={() => { onPick(p.slug); setQ(''); }}><b>{named(p, i18n.language)}</b>
              <span>{t(`pages:places.kind.${p.kind}`)}</span></button></li>
          ))}
        </ul>
      ) : null}
    </span>
  );
}

/** `/places/<slug>` is a state or a Moroccan place (a Latin slug); a land commune's older follow, `/places/<its Arabic
 *  name>`, still opens the land's finder (here, not in the router: the first load stays under its budget). */
export default function PlaceRoute() {
  const { place = '' } = useParams();
  if (/^[a-z0-9-]+$/.test(place)) return <PlaceView slug={place} />;
  return <Navigate replace to={`/topics/land/tools/find?q=${encodeURIComponent(place)}`} />;
}

/** /places/<slug> (PL19–PL23 of the places review, 1 Nov 2026): a state or a Moroccan place, its texts year by
 *  year (a share of each year's texts; a tap on a year, then another, chooses the years), its first mention on its
 *  printed page, its spellings, and every article that names it, newest first, the name lit as printed; the filters
 *  live in the address, so a link shares them. */
function PlaceView({ slug }: { slug: string }) {
  const { t, i18n } = useTranslation();
  const lang = i18n.language;
  const q = usePlace(slug);
  const p = q.data;
  const [params, setParams] = useSearchParams();
  const f: Filters = useMemo(() => ({
    from: Number(params.get('from')) || undefined, to: Number(params.get('to')) || undefined, kind: params.get('kind') || undefined,
    type: params.get('type') || undefined, title: params.get('title') === '1', with: params.get('with') || undefined,
  }), [params]);
  const set = (patch: Partial<Filters>) => {
    const next = { ...f, ...patch };
    const out = new URLSearchParams();
    for (const [k, v] of Object.entries(next)) if (v) out.set(k, v === true ? '1' : String(v));
    setParams(out, { replace: true });
  };
  const list = useMentions(slug, f);
  usePageTitle(p ? [named(p.place, lang), t('pages:places.title')] : [t('pages:places.title')]);
  const pickYear = (year: number) => {
    if (f.from && f.to && f.from === f.to && year !== f.from) set({ from: Math.min(year, f.from), to: Math.max(year, f.from) });
    else if (f.from === year && f.to === year) set({ from: undefined, to: undefined });
    else set({ from: year, to: year });
  };
  if (q.isLoading) return <Page width="wide" className="pl"><LinesSkeleton lines={8} /></Page>;
  if (!p) return q.error && (q.error as { status?: number }).status !== 404 ? <Page><LoadError error={q.error} retry={() => void q.refetch()} /></Page> : <NotFound />;
  const rows = list.data?.pages.flatMap((page) => page.rows) ?? [];
  const parent = p.near.find((x) => x.slug === p.place.parent);
  const successor = p.near.find((x) => x.slug === p.place.successor);
  const withName = f.with ? (p.near.find((x) => x.slug === f.with) ? named(p.near.find((x) => x.slug === f.with)!, lang) : f.with) : undefined;
  const filtered = !!(f.from || f.kind || f.type || f.title || f.with);
  const first = p.place.first;

  return (
    <Page width="wide" className="pl">
      <nav className="pl-crumb"><Link to="/places">‹ {t('pages:places.title')}</Link></nav>
      <header className="pl-place">
        <div>
          <h1 lang="ar" dir="rtl">{p.place.ar}</h1>
          <p className="pl-meta">
            {[t(`pages:places.kind.${p.place.kind}`), parent ? null : null, lang === 'fr' ? null : (p.place.fr || p.place.en)].filter(Boolean).join(' · ')}
            {parent ? <> · <Link to={parent.path}>{named(parent, lang)}</Link></> : null}
            {successor ? <> · {t('pages:places.became')} <Link to={successor.path}>{named(successor, lang)}</Link></> : null}
          </p>
          <p className="pl-count">{p.place.texts ? t('pages:places.named', { count: p.place.texts, texts: n(p.place.texts, lang), year: first?.date.slice(0, 4) ?? '' }) : t('pages:places.never')}
            {p.place.population ? ` ${t('pages:places.population', { people: n(p.place.population, lang) })}` : ''}</p>
        </div>
        <div className="pl-actions">
          <Suspense fallback={null}><FollowButton path={p.place.path} /></Suspense>
          {p.place.texts ? <Button onClick={() => void sharePlace(p, lang, t)}>{t('pages:places.sharePicture')}</Button> : null}
        </div>
      </header>

      {p.place.texts ? (
        <section className="pl-years" aria-labelledby="pl-years-h">
          <h2 id="pl-years-h">{t('pages:places.years')}</h2>
          <YearBars years={p.years} picked={f.from ? [f.from, f.to ?? f.from] : null} onPick={pickYear} />
          <div className="pl-axis" dir="ltr" aria-hidden="true">{p.years.filter((y) => y.year % 10 === 0).map((y) => <span key={y.year}>{y.year}</span>)}</div>
          <p className="pl-meta">{t('pages:places.yearsHow')}</p>
        </section>
      ) : null}

      <div className="pl-facts">
        {first ? (
          <section aria-labelledby="pl-first-h">
            <h2 id="pl-first-h">{t('pages:places.first')}</h2>
            <p><Link to={first.path} lang="ar" dir="rtl">{first.title}</Link></p>
            <p className="pl-meta">{t('pages:places.firstForm', { form: first.form, date: first.date })}</p>
            <Proof s={first.stamp} />
          </section>
        ) : null}
        {p.place.spellings.length > 1 || p.place.old.length ? (
          <section aria-labelledby="pl-spell-h">
            <h2 id="pl-spell-h">{t('pages:places.spellings')}</h2>
            <ul className="pl-spell">
              {p.place.spellings.map((s) => <li key={s.form}><b lang="ar" dir="rtl">{s.form}</b><span>{s.from === s.to ? s.from : `${s.from}–${s.to}`} · {n(s.n, lang)}</span></li>)}
            </ul>
          </section>
        ) : null}
      </div>

      {p.place.texts ? (
        <section className="pl-list" aria-labelledby="pl-list-h">
          <h2 id="pl-list-h">{t('pages:places.articles')}</h2>
          <div className="pl-filters" role="group" aria-label={t('pages:places.filters')}>
            {Object.entries(p.kinds).map(([k, count]) => (
              <button key={k} type="button" className={`pl-filter${f.kind === k ? ' on' : ''}`} aria-pressed={f.kind === k}
                      onClick={() => set({ kind: f.kind === k ? undefined : k })}>{t(`pages:places.kinds.${k}`)} <span>{n(count, lang)}</span></button>
            ))}
            <select value={f.type ?? ''} onChange={(e) => set({ type: e.target.value || undefined })} aria-label={t('pages:places.type')}>
              <option value="">{t('pages:places.allTypes')}</option>
              {Object.entries(p.types).map(([k, count]) => <option key={k} value={k}>{t(`corpus.types.${k}`, { defaultValue: k })} ({n(count, lang)})</option>)}
            </select>
            <button type="button" className={`pl-filter${f.title ? ' on' : ''}`} aria-pressed={!!f.title} onClick={() => set({ title: !f.title })}>
              {t('pages:places.titleOnly')}</button>
            <WithPlace value={withName} onPick={(s) => set({ with: s })} />
            {filtered ? <button type="button" className="pl-filter clear" onClick={() => setParams(new URLSearchParams(), { replace: true })}>{t('pages:places.clear')}</button> : null}
          </div>
          {f.from ? <p className="pl-meta" aria-live="polite">{t('pages:places.yearsOn', { from: f.from, to: f.to ?? f.from })}</p> : null}
          {list.isLoading ? <LinesSkeleton lines={6} /> : rows.length ? (
            <ol className="pl-rows">{rows.map((m) => <Row key={`${m.path}#${m.in_title}`} m={m} />)}</ol>
          ) : <EmptyState title={t('pages:places.noneHere')} lead={t('pages:places.noneHereLead')} />}
          {list.hasNextPage ? (
            <Button onClick={() => void list.fetchNextPage()} disabled={list.isFetchingNextPage}>{t('pages:places.more')}</Button>
          ) : null}
        </section>
      ) : null}

      {p.near.length ? (
        <section className="pl-near" aria-labelledby="pl-near-h">
          <h2 id="pl-near-h">{t('pages:places.near')}</h2>
          <ul>{p.near.filter((x) => x.slug !== p.place.slug).map((x) => <li key={x.slug}><Link to={x.path}>{named(x, lang)} <span>{n(x.texts, lang)}</span></Link></li>)}</ul>
        </section>
      ) : null}
      {/* What the blog counted of a state, or of Morocco's places. */}
      <BlogLinks slugs={['country', 'gone'].includes(p.place.kind) ? ['countries', 'agreements'] : ['cities']} />
      <p className="pl-source">{t('pages:places.source')}</p>
    </Page>
  );
}
