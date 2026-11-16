import { lazy, Suspense, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { LoadError } from '@/features/corpus/NotFound';
import { Button, Page, PageSkeleton, Skeleton } from '@/shared/components/ui';
import { pick, refPath, useKitItem, useKitT, type AgeLine, type InfoPage as Info, type Named, type Section, type Table } from './api';
import { Cites, KitPage, NextLinks } from './parts';
import { Chips } from './tool/parts';
import { useToolState } from './tool/state';
import { readAge, writeAge } from './progress';
import { useProfile } from './profile';
import { todayIso } from '@/shared/services/today';
import { useRefTitles } from './share';

const SeriesChart = lazy(() => import('./SeriesChart'));
// The bill-page review: a page of changes and a page of claims, each with its own drawing, loaded when named.
const ChangesView = lazy(() => import('./changes/ChangesView'));
const ClaimsView = lazy(() => import('./changes/ClaimsView'));
const PressView = lazy(() => import('./changes/Press'));
const Band = lazy(() => import('./changes/BillBand').then((m) => ({ default: m.BillBand })));
const SeriesStory = lazy(() => import('./SeriesStory'));

/** A topic's page of facts (F8–F11, F13, F14): sections of sentences, each on its articles; the five ways side by side;
 *  a child's line by age; the official series; the protection page's numbers, with the quick exit. */
export default function InfoPage({ slug }: { slug: string }) {
  const { key = '' } = useParams();
  const { t, i18n } = useKitT();
  const q = useKitItem<Info>(slug, 'pages', key);
  const titles = useRefTitles(slug);
  const [mine] = useProfile(slug);
  const lang = i18n.language;
  if (q.isLoading) return <Page width="reading"><PageSkeleton kind="text" /></Page>;
  const p = q.data;
  if (!p) return <Page width="reading"><LoadError error={q.error} retry={() => void q.refetch()} /></Page>;
  // The reader's own section first (its `for` holds their answer to the topic's question).
  const ordered = [...(p.sections ?? [])].sort((a, b) => Number(Boolean(mine && b.for?.includes(mine))) - Number(Boolean(mine && a.for?.includes(mine))));
  if (p.layout === 'changes') return <Suspense fallback={<Page width="reading"><PageSkeleton kind="text" /></Page>}><ChangesView slug={slug} p={p} /></Suspense>;
  if (p.layout === 'press') return <Suspense fallback={<Page width="reading"><PageSkeleton kind="text" /></Page>}><PressView slug={slug} p={p as Parameters<typeof PressView>[0]['p']} /></Suspense>;
  if (p.layout === 'claims') return <Suspense fallback={<Page width="reading"><PageSkeleton kind="text" /></Page>}><ClaimsView slug={slug} p={p} /></Suspense>;
  return (
    <KitPage slug={slug} item={p} title={pick(p.title, lang)} lead={pick(p.lead, lang)} discreet={p.discreet} wide={Boolean(p.table)}
             aside={!p.table ? <Contents slug={slug} sections={ordered} titles={titles} /> : undefined}>
      {p.bill ? <Suspense fallback={null}><Band slug={slug} bill={p.bill} reform={p.reform} /></Suspense> : null}
      {p.contacts?.length ? (
        <section className="flex flex-col gap-2 rounded-card bg-sheet px-5 py-5 sm:px-7">
          <h2 className="m-0 text-lead font-semibold">{p.contacts_title ? pick(p.contacts_title, lang) : t('contacts')}</h2>
          {/* Each number as text one can read, a call where the phone allows, and the official page that gives it (C1
              of the family-papers review: a number shows only with its page). */}
          <ul className="m-0 flex list-none flex-col gap-3 p-0">
            {p.contacts.map((c) => (
              <li key={c.number} className="flex flex-col items-start gap-1">
                <a href={`tel:${c.number}`} className="inline-flex min-h-12 max-w-full items-center gap-3 rounded-full bg-ink ps-2 pe-5 text-body font-semibold text-sheet no-underline hover:bg-stamp hover:text-sheet">
                  <span dir="ltr" className="grid min-w-10 place-items-center rounded-full bg-sheet px-2 text-lead font-bold leading-9 text-ink">{c.number}</span>
                  <span lang={lang}>{t('call', { name: pick(c.name, lang), number: c.number })}</span>
                </a>
                {c.source ? (
                  <a href={c.source.url} target="_blank" rel="noreferrer" title={pick(c.source.name, lang)} className="inline-flex min-h-11 items-center text-meta">
                    {t('band.source', { number: c.number, source: new URL(c.source.url).host.replace(/^www\./, '') })}
                  </a>
                ) : null}
              </li>
            ))}
          </ul>
        </section>
      ) : null}
      {p.links?.length ? (
        <section className="flex flex-col gap-2 rounded-card bg-sheet px-5 py-5 sm:px-7" aria-labelledby="official-links">
          <h2 id="official-links" className="m-0 text-lead font-semibold">{t('links')}</h2>
          <ul className="m-0 flex list-none flex-col p-0">
            {p.links.map((l) => (
              <li key={l.url} className="border-t border-rule first:border-t-0">
                <a href={l.url} target="_blank" rel="noreferrer" className="flex min-h-12 flex-col justify-center gap-0.5 py-2.5 no-underline hover:underline">
                  <span lang={lang} className="text-body font-medium">{pick(l.name, lang)}</span>
                  {l.note ? <span lang={lang} className="text-meta text-ink-soft">{pick(l.note, lang)}</span> : null}
                </a>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
      {p.table ? <Ways slug={slug} table={p.table} /> : null}
      {p.line ? <Line slug={slug} line={p.line} /> : null}
      {p.series?.map((s) => (
        <Suspense key={s.key} fallback={<Skeleton className="h-80 w-full rounded-card" />}><SeriesStory s={s} slug={slug} /><SeriesChart s={s} /></Suspense>
      ))}
      {/* The reader's own section first (its `for` holds their answer to the topic's question), marked as theirs. */}
      {ordered.map((s, i) => (
        <section key={i} id={`section-${i}`} className="flex flex-col gap-3 rounded-card bg-sheet px-5 py-5 sm:px-7"
                 style={{ scrollMarginTop: 24, ...(mine && s.for?.includes(mine) ? { boxShadow: '0 0 0 2px var(--t)' } : {}) }}>
          {s.bill ? <span className="self-start rounded-full px-2.5 py-1 text-meta font-medium" style={DASHED}>{t('bill.mark')}</span> : null}
          <h2 lang={lang} className="m-0 text-lead font-semibold">{pick(s.title, lang)}</h2>
          {s.source ? (
            <a href={s.source.url} target="_blank" rel="noreferrer" className="self-start text-meta">{t('bill.saidIn', { source: pick(s.source.name, lang) })}</a>
          ) : null}
          {s.table ? <FactTable table={s.table} /> : null}
          {s.table ? <Cites cites={s.cites} /> : null}
          <ul className="m-0 flex list-none flex-col gap-4 p-0">
            {(s.facts ?? []).map((f, j) => (
              <li key={j} className="flex flex-col gap-2">
                <p lang={lang} className="m-0 text-body leading-relaxed">{pick(f.text, lang)}</p>
                <Cites cites={f.cites} />
              </li>
            ))}
          </ul>
          {s.tool && titles[s.tool] ? <Button to={refPath(slug, s.tool)} className="self-start">{pick(titles[s.tool], lang)}</Button> : null}
          {s.more && titles[s.more] ? <Link to={refPath(slug, s.more)} className="inline-flex min-h-11 items-center self-start font-medium">{pick(titles[s.more], lang)}</Link> : null}
        </section>
      ))}
      <NextLinks slug={slug} refs={p.next} titles={titles} />
    </KitPage>
  );
}

/** A long page's sections on a desk's side column (the bill-page review, V14): each a way to its place, the
 *  page's tools under them; a page of fewer than three sections keeps its one column. */
function Contents({ slug, sections, titles }: { slug: string; sections: Section[]; titles: Record<string, Named | undefined> }) {
  const { t, i18n } = useKitT();
  const lang = i18n.language;
  if (sections.length < 3) return null;
  const tools = [...new Set(sections.map((s) => s.tool).filter((x): x is string => Boolean(x && titles[x])))];
  return (
    <nav aria-labelledby="page-contents" className="flex flex-col gap-1 rounded-card bg-sheet px-5 py-5">
      <h2 id="page-contents" className="m-0 mb-1 text-body font-semibold">{t('contents')}</h2>
      {sections.map((s, i) => (
        <a key={i} href={`#section-${i}`} lang={lang} className="flex min-h-11 items-center text-body no-underline"
           style={i ? { borderTop: '1px solid var(--color-rule)' } : undefined}>{pick(s.title, lang)}</a>
      ))}
      {tools.map((x) => <Button key={x} to={refPath(slug, x)} className="mt-3 self-start">{pick(titles[x], lang)}</Button>)}
    </nav>
  );
}

/** A bill's marks are drawn in dashes: a draft (a style, for the stylesheet's budget). */
const DASHED = { border: '1px dashed var(--color-ink-soft)' };

/** A table the law states (the road plan's points, categories and speeds): a head and its rows, the figures in
 *  Western digits as the BO prints them, read in the page's direction. */
function FactTable({ table }: { table: NonNullable<Section['table']> }) {
  const { i18n } = useKitT();
  const lang = i18n.language;
  const cell = (c: Named | string) => (typeof c === 'string' ? c : pick(c, lang));
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-start text-body">
        <thead>
          <tr className="border-b border-rule">
            {table.head.map((h, i) => <th key={i} scope="col" lang={lang} className="py-2 pe-3 text-start text-meta font-medium text-ink-soft">{pick(h, lang)}</th>)}
          </tr>
        </thead>
        <tbody>
          {table.rows.map((r, i) => (
            <tr key={i} className="border-b border-rule-soft">
              {r.map((c, j) => (
                <td key={j} lang={typeof c === 'string' ? undefined : lang}
                    className={`py-2 pe-3 align-top ${typeof c === 'string' ? 'whitespace-nowrap font-semibold tabular-nums' : ''}`}>{cell(c)}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** The five ways (F9; G9 of the family-papers review): first the table's one question («شكون بغا يفارق؟»), then the ways
 *  open to that answer first, in the order courts use them, each with how often (the topic's series). A desk compares
 *  them side by side, the others dimmed; a phone shows one way at a time under the same question. */
function Ways({ slug, table }: { slug: string; table: Table }) {
  const { t, i18n } = useKitT();
  const lang = i18n.language;
  const nf = new Intl.NumberFormat(lang === 'fr' ? 'fr-MA' : 'ar-MA');
  const [st, set] = useToolState({ who: '', way: '' });
  const opens = (r: Table['rows'][number]) => !st.who || !r.askers || r.askers.includes(st.who) || Boolean(r.also?.[st.who]);
  const rows = [...table.rows.filter(opens), ...table.rows.filter((r) => !opens(r))];
  const shown = rows.find((r) => r.key === st.way && opens(r)) ?? rows[0];
  const count = (r: Table['rows'][number]) => (r.count ? t('ways.count', { n: nf.format(r.count.n), unit: pick(r.count.unit, lang), year: r.count.year }) : '');
  const condition = (r: Table['rows'][number]) => (st.who && r.also?.[st.who] && !r.askers?.includes(st.who) ? pick(r.also[st.who], lang) : '');
  return (
    <>
      {table.ask ? (
        <section className="flex flex-col gap-2 rounded-card bg-sheet px-5 py-4 sm:px-7">
          <Chips label={pick(table.ask.question, lang)} value={st.who}
                 options={table.ask.options.map((o) => ({ key: o.key, label: pick(o.label, lang) }))}
                 onChange={(who) => set({ who: who === st.who ? '' : who, way: '' })} />
        </section>
      ) : null}
      <div className="hidden overflow-x-auto rounded-card bg-sheet px-5 py-5 md:block">
        <table className="w-full border-collapse text-start text-meta">
          <thead>
            <tr>
              <td />
              {rows.map((r) => (
                <th key={r.key} scope="col" lang={lang} className={`px-3 pb-3 text-start align-bottom text-body font-semibold ${opens(r) ? '' : 'opacity-50'}`}>
                  {r.to ? <Link to={refPath(slug, r.to)}>{pick(r.title, lang)}</Link> : pick(r.title, lang)}
                  {opens(r) ? null : <span className="block text-meta font-normal text-ink-soft">{t('ways.notYou')}</span>}
                  {condition(r) ? <span className="block text-meta font-normal text-amended">{condition(r)}</span> : null}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.some((r) => r.count) ? (
              <tr className="border-t border-rule">
                <th scope="row" className="py-3 pe-3 text-start align-top font-semibold text-ink-soft">{t('ways.used')}</th>
                {rows.map((r) => <td key={r.key} lang={lang} className={`px-3 py-3 align-top font-semibold text-[color:var(--t)] tabular-nums ${opens(r) ? '' : 'opacity-50'}`}>{count(r) || '—'}</td>)}
              </tr>
            ) : null}
            {table.columns.map((c) => (
              <tr key={c.key} className="border-t border-rule">
                <th scope="row" lang={lang} className="py-3 pe-3 text-start align-top font-semibold text-ink-soft">{pick(c.label, lang)}</th>
                {rows.map((r) => <td key={r.key} lang={lang} className={`px-3 py-3 align-top ${opens(r) ? '' : 'opacity-50'}`}>{pick(r.cells[c.key], lang)}</td>)}
              </tr>
            ))}
            <tr className="border-t border-rule">
              <th scope="row" className="py-3 pe-3 text-start align-top font-semibold text-ink-soft">{t('cites')}</th>
              {rows.map((r) => <td key={r.key} className={`px-3 py-3 align-top ${opens(r) ? '' : 'opacity-50'}`}><Cites cites={r.cites} /></td>)}
            </tr>
          </tbody>
        </table>
        {table.ask?.source ? <p lang={lang} className="m-0 mt-3 text-meta text-ink-soft">{t('ways.source', { source: pick(table.ask.source, lang) })}</p> : null}
      </div>
      {/* A phone: one way at a time, chosen among those open to the answer. */}
      <section className="flex flex-col gap-3 md:hidden">
        <Chips label={t('ways.one')} value={shown.key}
               options={rows.filter(opens).map((r) => ({ key: r.key, label: pick(r.title, lang) }))}
               onChange={(way) => set({ way })} />
        <article className="flex flex-col gap-3 rounded-card bg-sheet px-5 py-5">
          <h2 lang={lang} className="m-0 text-lead font-semibold">{pick(shown.title, lang)}</h2>
          {shown.count ? <p lang={lang} className="m-0 text-body font-semibold text-[color:var(--t)]">{count(shown)}</p> : null}
          {condition(shown) ? <p lang={lang} className="m-0 text-meta text-amended">{condition(shown)}</p> : null}
          <dl className="m-0 grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-body">
            {table.columns.map((c) => (
              <div key={c.key} className="contents">
                <dt lang={lang} className="text-meta font-semibold text-ink-soft">{pick(c.label, lang)}</dt>
                <dd lang={lang} className="m-0">{pick(shown.cells[c.key], lang)}</dd>
              </div>
            ))}
          </dl>
          <Cites cites={shown.cites} />
          {shown.to ? <Button to={refPath(slug, shown.to)} className="self-start">{t('ways.open')}</Button> : null}
          {table.ask?.source && shown.count ? <p lang={lang} className="m-0 text-meta text-ink-soft">{t('ways.source', { source: pick(table.ask.source, lang) })}</p> : null}
        </article>
      </section>
    </>
  );
}

/** A child's years as one picture (F8; G10 of the family-papers review): each span the law sets drawn as a bar over
 *  the years 0 to `max`, running left to right on an Arabic page too (the chart rule of 1 Nov 2026), the child's age one line across them; what the line crosses
 *  holds now, the rest is greyed. The age is set on the line, by a year's mark or from the birth date, and kept on the
 *  phone. Under it, what comes at the next two marks. */
function Line({ slug, line }: { slug: string; line: AgeLine }) {
  const { t, i18n } = useKitT();
  const lang = i18n.language;
  const [age, setAgeState] = useState(() => readAge(slug) ?? 9);
  const setAge = (n: number) => { const a = Math.max(0, Math.min(line.max, n)); setAgeState(a); writeAge(slug, a); };
  const at = (n: number) => `${(Math.min(n, line.max) / line.max) * 100}%`;
  const holds = (sp: AgeLine['spans'][number]) => age >= sp.from && age < sp.to;
  const next = line.points.filter((p) => p.age > age).slice(0, 2);
  const fromBirth = (iso: string) => {
    const [y, m, d] = iso.split('-').map(Number);
    const [ty, tm, td] = todayIso().split('-').map(Number);
    setAge(ty - y - (tm < m || (tm === m && td < d) ? 1 : 0));
  };
  return (
    <section className="flex flex-col gap-4 rounded-card bg-sheet px-5 py-5 sm:px-7" aria-labelledby="age-line">
      <h2 id="age-line" className="m-0 text-lead font-semibold">
        {t('line.age')}: <output className="text-[color:var(--t)]">{t('line.years', { count: age })}</output>
      </h2>
      <div className="flex flex-col gap-3 pt-1">
        {line.spans.map((sp, i) => (
          <div key={i} className={`flex flex-col gap-1 transition-opacity duration-200 motion-reduce:transition-none ${holds(sp) ? '' : 'opacity-55'}`}>
            <p lang={lang} className={`m-0 text-meta leading-snug ${holds(sp) ? 'font-semibold text-ink' : 'text-ink-soft'}`}>{pick(sp.text, lang)}</p>
            <span aria-hidden="true" dir="ltr" className="relative block h-3.5 rounded-full bg-rule">
              <span className={`absolute inset-y-0 rounded-full ${holds(sp) ? 'bg-[var(--t)]' : 'bg-field'}`} style={{ insetInlineStart: at(sp.from), width: `calc(${at(sp.to)} - ${at(sp.from)})` }} />
              {/* The child's age, marked on every bar at the same place: the bars read as one picture. */}
              <span className="absolute -inset-y-1 w-[3px] -translate-x-1/2 rounded-full bg-ink" style={{ insetInlineStart: at(age) }} />
            </span>
            {holds(sp) ? <Cites cites={sp.cites} /> : null}
          </div>
        ))}
      </div>
      <input type="range" dir="ltr" min={0} max={line.max} value={age} aria-label={t('line.age')} onChange={(e) => setAge(Number(e.target.value))}
             className="h-11 w-full accent-[var(--t)]" />
      <ol dir="ltr" className="relative m-0 h-11 list-none p-0 text-meta">
        {line.points.map((p) => (
          <li key={p.age} className="absolute top-0 -translate-x-1/2" style={{ insetInlineStart: at(p.age) }}>
            <button type="button" onClick={() => setAge(p.age)} aria-pressed={p.age === age}
                    className={`min-h-11 min-w-11 rounded-full tabular-nums ${p.age === age ? 'bg-ink font-semibold text-sheet' : 'text-ink-soft hover:text-stamp'}`}>
              {p.age}
            </button>
          </li>
        ))}
      </ol>
      <label className="flex flex-wrap items-center gap-2 text-meta text-ink-soft">
        {t('line.birth')}
        <input type="date" max={todayIso()} dir="ltr" onChange={(e) => e.target.value && fromBirth(e.target.value)}
               className="h-11 rounded-control border border-field bg-sheet px-3 text-body text-ink" />
      </label>
      {next.length ? (
        <div className="flex flex-col gap-2 border-t border-rule pt-3">
          <h3 className="m-0 text-body font-semibold">{t('line.next')}</h3>
          <ul className="m-0 flex list-none flex-col gap-3 p-0">
            {next.map((p) => (
              <li key={p.age} className="flex flex-col gap-1.5 border-s-[3px] border-rule ps-3">
                <p className="m-0 text-meta font-semibold text-ink-soft">{t('line.at', { age: t('line.years', { count: p.age }) })}</p>
                <p lang={lang} className="m-0 text-body">{pick(p.text, lang)}</p>
                <Cites cites={p.cites} />
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}
