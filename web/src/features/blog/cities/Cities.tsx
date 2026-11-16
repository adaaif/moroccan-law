import { type CSSProperties, useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { MoroccoMap, type Dot } from '@/features/places/Maps';
import { PlaceSheet } from '@/features/places/parts';
import '@/features/places/places.css';
import type { CitiesPost, CityRow } from '../blog.api';
import { Head } from '../Head';
import { Figure, Legend, Table } from '../kit';
import { pct } from '@/shared/locales/i18n';
import { dec, endSpans, ends, labelled, n, since1956 } from '../viz';
import '@/shared/design/french.css';
import '../post.css';
import '../countries/countries.css';

const KINDS = ['land', 'territory', 'water', 'schools', 'courts', 'health', 'economy', 'other'] as const;
// The bar's own colours (1 Nov 2026: every chart that colours kinds names them in a legend): the four kinds that weigh most,
// then courts, health and the economy together in grey; seven colours could not all be told apart. The table keeps each.
const BAR = ['schools', 'land', 'water', 'territory'] as const;
const REST = ['courts', 'health', 'economy'] as const;

/** A city's line over the periods, time from left to right on an Arabic page too (as the countries' lines), a thin
 *  upright at 1956. */
function Line({ series, max, mark, w = 112, h = 40, tone }: { series: number[]; max: number; mark?: number; w?: number; h?: number; tone: 'rise' | 'fall' }) {
  const at = (i: number) => 3 + (i * (w - 6)) / (series.length - 1);
  const y = (v: number) => h - 3 - ((h - 8) * v) / (max || 1);
  const m = mark && mark > 0 ? (at(mark - 1) + at(mark)) / 2 : null;
  return (
    <svg className={`cn-line ${tone}`} viewBox={`0 0 ${w} ${h}`} width={w} height={h} aria-hidden="true">
      {m !== null ? <line x1={m} x2={m} y1={1} y2={h - 1} className="y56" /> : null}
      <polyline points={series.map((v, i) => `${at(i).toFixed(1)},${y(v).toFixed(1)}`).join(' ')} className="all" />
      <circle cx={at(series.length - 1)} cy={y(series[series.length - 1])} r="2.8" className="end" />
    </svg>
  );
}

/**
 * «المغرب في الجريدة الرسمية» (post 2 of the places review, 1 Nov 2026): Morocco whole, its cities as dots
 * period by period (PL13); the State's texts spreading out from its five biggest cities (PL14); who rose and who fell;
 * the old names beside the new (PL15); since 2020, texts per 10,000 inhabitants (PL16); what the texts did in each city
 * (PL17). A city counts with its province of the same name (C5). A tap on a dot opens the place's sheet (PL23).
 */
export default function Cities({ post }: { post: CitiesPost }) {
  const { t, i18n } = useTranslation('blog');
  const lang = i18n.language;
  const rtl = lang !== 'fr';
  const f = post.figures;
  const N = (v: number) => n(v, lang);
  const P = f.periods.map(([a, b]) => `${a}–${b}`);
  const last = P.length - 1;
  const k56 = since1956(f.periods);
  const shown = labelled(P.length, k56);
  const before = (c?: CityRow) => (c && k56 > 0 ? c.c.slice(0, k56).reduce((a, b) => a + b, 0) : 0);
  const after = (c?: CityRow) => (c ? c.c.slice(Math.max(k56, 0)).reduce((a, b) => a + b, 0) : 0);
  const by = useMemo(() => Object.fromEntries(f.cities.map((c) => [c.slug, c])) as Record<string, CityRow>, [f]);
  const name = (c: CityRow) => (rtl ? c.ar : c.fr);
  const [period, setPeriod] = useState(0);
  const [sheet, setSheet] = useState<string | null>(null);
  const [playing, setPlaying] = useState(false);
  const timer = useRef<number | null>(null);
  useEffect(() => () => { if (timer.current) window.clearInterval(timer.current); }, []);
  const play = () => {
    if (timer.current) { window.clearInterval(timer.current); timer.current = null; setPlaying(false); return; }
    let i = 0;
    setPeriod(0);
    setPlaying(true);
    timer.current = window.setInterval(() => {
      i += 1;
      if (i > last) { window.clearInterval(timer.current!); timer.current = null; setPlaying(false); return; }
      setPeriod(i);
    }, 1300);
  };
  const rose = new Set(f.moves.rose);
  const max = Math.max(...f.cities.flatMap((c) => c.s));
  const dots: Dot[] = useMemo(() => f.cities.filter((c) => c.lat != null && c.lon != null)
    .map((c) => ({ slug: c.slug, ar: c.ar, fr: c.fr, lat: c.lat!, lon: c.lon!, value: c.s[period], tone: rose.has(c.slug) ? 'rise' as const : null })),
  // eslint-disable-next-line react-hooks/exhaustive-deps
  [f, period]);
  const ranked = [...f.cities].filter((c) => c.s[period] > 0).sort((a, b) => b.s[period] - a.s[period]).slice(0, 8);
  const top = ranked[0]?.s[period] || 1;
  const src = t('fig.source', { from: f.periods[0][0], to: f.periods[last][1] });
  const casa = by.casablanca, rabat = by.rabat;
  const one = (v: number) => (v > 0 ? N(Math.round(1000 / v)) : '—');
  const [fivePick, setFivePick] = useState<number | null>(null);
  const fiveMax = Math.max(...f.five.top, ...f.five.rest);
  const olds = f.cities.filter((c) => c.old && c.old.c.reduce((a, b) => a + b, 0) >= 5);
  const para = (key: string, values: Record<string, unknown> = {}) => <p className="bp-p">{t(key, values)}</p>;
  /** A text read on its printed page: what it did, its stamp, a link to it. */
  const Stop = ({ k }: { k: string }) => {
    const s = post.stops.find((x) => x.key === k);
    if (!s) return null;
    return (
      <p className="bp-p ct-stop">
        <Link to={`/ma${s.text.replace('/akn/ma/act', '')}`}>{t('cities.stop', { issue: s.issue, page: s.page, date: s.date.slice(0, 4) })}</Link>{' '}
        {rtl ? s.ar : s.fr}
      </p>
    );
  };

  return (
    <article className="bp" lang={lang}>
      <Head post={post} />

      <figure className="bp-hero cn-hero" aria-labelledby="ct-q">
        <div className="bp-hero-words">
          <p className="bp-q" id="ct-q">{t('cities.hero.q')}</p>
          <p className="bp-unit">{t('cities.hero.how')}</p>
        </div>
        <div className="cn-controls">
          <div className="cn-periods" dir="ltr" role="group" aria-label={t('countries.hero.periods')}>
            {P.map((p, i) => <button key={p} type="button" className={i === k56 ? 'y56' : undefined} aria-pressed={i === period}
                                      onClick={() => { if (timer.current) play(); setPeriod(i); }}>{p}</button>)}
          </div>
          <button type="button" className="cn-play" onClick={play}>{playing ? t('countries.hero.stop') : t('countries.hero.play', { from: f.periods[0][0], to: f.periods[last][1] })}</button>
          {k56 > 0 ? <p className="cn-key cn-56">{t('countries.hero.periods56')}</p> : null}
        </div>
        <div className="cn-stage ma">
          <MoroccoMap dots={dots} max={max} picked={sheet} onPick={setSheet} rtl={rtl} label={t('cities.hero.aria', { period: P[period] })} />
          <ol className="cn-rank" dir="ltr" aria-label={t('countries.hero.rank', { period: P[period] })}>
            {ranked.map((c, i) => (
              <li key={c.slug}>
                <button type="button" onClick={() => setSheet(c.slug)}>
                  <span className="r">{i + 1}</span>
                  <span className="nm"><b>{name(c)}</b><i style={{ width: `${(100 * c.s[period]) / top}%` }} /></span>
                  <span className="v">{dec(c.s[period])}</span>
                </button>
              </li>
            ))}
          </ol>
        </div>
        <div className="bp-hero-foot">
          <p className="bp-pick" aria-live="polite">{t('cities.hero.pick', { period: P[period], texts: N(f.texts[period]), first: ranked[0] ? name(ranked[0]) : '', one: ranked[0] ? one(ranked[0].s[period]) : '' })}</p>
          <p className="bp-so"><b>{t('fig.so')}</b> {t('cities.hero.so', { casa0: one(casa?.s[0] ?? 0), casa1: one(casa?.s[last] ?? 0), first: P[0], last: P[last] })}</p>
          <p className="bp-src">{src}</p>
        </div>
      </figure>

      <section className="bp-sec" aria-labelledby="ct-s1">
        <h2 id="ct-s1">{t('cities.s1.h')}</h2>
        {para('cities.s1.p1', { casa0: one(casa?.s[0] ?? 0), casa1: one(casa?.s[last] ?? 0), rabat0: one(rabat?.s[0] ?? 0), rabat1: one(rabat?.s[last] ?? 0),
                                top0: dec(f.five.top[0]), top1: dec(f.five.top[last]), rest0: dec(f.five.rest[0]), rest1: dec(f.five.rest[last]), first: P[0], last: P[last],
                                five: f.five.slugs.map((s) => (by[s] ? name(by[s]) : s)).join('، ') })}
        <Figure id="ct-five" q={t('cities.s1.q')} unit={t('cities.s1.unit')} source={src}
                pick={fivePick === null ? t('fig.hint') : t('cities.s1.pick', { period: P[fivePick], top: dec(f.five.top[fivePick]), rest: dec(f.five.rest[fivePick]) })}
                so={t('cities.s1.so', { top0: dec(f.five.top[0]), top1: dec(f.five.top[last]), rest0: dec(f.five.rest[0]), rest1: dec(f.five.rest[last]) })}
                table={<Table head={['', t('cities.s1.five'), t('cities.s1.rest')]} rows={P.map((p, i) => [p, dec(f.five.top[i]), dec(f.five.rest[i])])} />}>
          <div className="ct-pairs" dir="ltr" role="group" aria-label={t('cities.s1.q')} style={{ '--n': P.length } as CSSProperties}>
            {P.map((p, i) => (
              <button key={p} type="button" className={[fivePick === i ? 'on' : '', i === k56 ? 'y56' : '', shown.has(i) ? '' : 'minor'].join(' ').trim() || undefined}
                      onClick={() => setFivePick(i)} aria-label={t('cities.s1.pick', { period: p, top: dec(f.five.top[i]), rest: dec(f.five.rest[i]) })}>
                <span className="col"><i className="top" style={{ height: `${(100 * f.five.top[i]) / fiveMax}%` }} /><i className="rest" style={{ height: `${(100 * f.five.rest[i]) / fiveMax}%` }} /></span>
                <span className="p"><span>{f.periods[i][0]}</span><span>–{f.periods[i][1]}</span></span>
              </button>
            ))}
          </div>
          <p className="cn-key">{t('cities.s1.key', { five: f.five.slugs.map((s) => (by[s] ? name(by[s]) : s)).join(rtl ? '، ' : ', ') })}</p>
        </Figure>
      </section>

      <section className="bp-sec" aria-labelledby="ct-s2">
        <h2 id="ct-s2">{t('cities.s2.h')}</h2>
        {k56 > 0 ? para('cities.s2.reach', { tet0: N(before(by.tetouan)), hoc0: N(before(by['al-hoceima'])), nad0: N(before(by.nador)),
                                              tet1: N(after(by.tetouan)), hoc1: N(after(by['al-hoceima'])), nad1: N(after(by.nador)) }) : null}
        {k56 > 0 && f.totals.zone ? para('cities.s2.zone', { count: f.totals.zone, n: N(f.totals.zone) }) : null}
        <Stop k="zone" />
        <Stop k="south" />
        <Stop k="dakhla" />
        {para('cities.s2.p1', { rose: f.moves.rose.map((k) => by[k]).filter(Boolean).map(name).join(rtl ? '، ' : ', '),
                                fell: f.moves.fell.map((k) => by[k]).filter(Boolean).map(name).join(rtl ? '، ' : ', ') })}
        <Figure id="ct-moves" q={t('cities.s2.q')} unit={t('cities.s2.unit', { p0: endSpans(f.periods)[0], p1: endSpans(f.periods)[1] })} source={src} so={t('cities.s2.so')}
                table={<Table head={['', ...P]} rows={[...f.moves.rose, ...f.moves.fell].map((k) => by[k]).filter(Boolean).map((c) => [name(c), ...c.s.map((x) => dec(x))])} />}>
          <div className="cn-moves">
            {[['rise', f.moves.rose, t('countries.s1.rose')] as const, ['fall', f.moves.fell, t('countries.s1.fell')] as const].map(([tone, rows, title]) => (
              <div key={tone}>
                <h3 className={`cn-col ${tone}`}>{title}</h3>
                <ol>
                  {rows.map((k) => by[k]).filter(Boolean).map((c) => (
                    <li key={c.slug}>
                      <button type="button" onClick={() => setSheet(c.slug)} className="cn-move">
                        <span className="nm"><b>{name(c)}</b><span>{t('cities.s2.from', { a: dec(ends(c.s)[0]), b: dec(ends(c.s)[1]) })}</span></span>
                        <Line series={c.s} max={Math.max(...c.s, 0.5)} tone={tone} mark={k56} />
                      </button>
                    </li>
                  ))}
                </ol>
              </div>
            ))}
          </div>
        </Figure>
      </section>

      {olds.length ? (
        <section className="bp-sec" aria-labelledby="ct-s3">
          <h2 id="ct-s3">{t('cities.s3.h')}</h2>
          {para('cities.s3.p1')}
          <Stop k="north" />
          <Figure id="ct-old" q={t('cities.s3.q')} unit={t('cities.s3.unit')} source={src} so={t('cities.s3.so')}
                  table={<Table head={['', ...P]} rows={olds.flatMap((c) => [[`${c.old!.forms[0]} (${t('cities.s3.old')})`, ...c.old!.c.map(N)], [name(c), ...c.c.map((v, i) => N(v - c.old!.c[i]))]])} />}>
            <ul className="ct-old">
              {olds.map((c) => {
                // Each period whole: the share of its texts that still print the old name.
                const was = c.old!.c.map((v, i) => (c.c[i] ? v / c.c[i] : 0));
                return (
                  <li key={c.slug}>
                    <p><b lang="ar" dir="rtl">{c.old!.forms[0]}</b> → <b>{name(c)}</b></p>
                    <div className="ct-old-bars" dir="ltr" aria-hidden="true" style={{ '--n': P.length } as CSSProperties}>
                      {P.map((p, i) => (
                        <span key={p} className={i === k56 ? 'y56' : undefined} title={pct(`${p}: ${Math.round(100 * was[i])}٪`)}>{c.c[i] ? <><i className="now" style={{ height: `${100 * (1 - was[i])}%` }} /><i className="was" style={{ height: `${100 * was[i]}%` }} /></> : null}</span>
                      ))}
                    </div>
                  </li>
                );
              })}
            </ul>
            <div className="cn-axis" dir="ltr" aria-hidden="true"><span>{P[0]}</span><span>{P[last]}</span></div>
          </Figure>
        </section>
      ) : null}

      <section className="bp-sec" aria-labelledby="ct-s4">
        <h2 id="ct-s4">{t('cities.s4.h')}</h2>
        {para('cities.s4.p1', { period: P[last] })}
        <Figure id="ct-people" q={t('cities.s4.q')} unit={t('cities.s4.unit')} source={t('cities.s4.source', { from: f.periods[last][0], to: f.periods[last][1] })}
                so={t('cities.s4.so', { first: f.people[0] && by[f.people[0].slug] ? name(by[f.people[0].slug]) : '', v: f.people[0] ? dec(f.people[0].v) : '' })}
                table={<Table head={['', t('cities.s4.unit')]} rows={[...f.people, ...f.people_low].map((r) => [by[r.slug] ? name(by[r.slug]) : r.slug, dec(r.v)])} />}>
          <ol className="pl-rank" dir="ltr">
            {f.people.map((r, i) => by[r.slug] ? (
              <li key={r.slug}>
                <button type="button" onClick={() => setSheet(r.slug)}>
                  <span className="r">{i + 1}</span>
                  <span className="nm"><span className="ln"><b>{name(by[r.slug])}</b><small>{N(by[r.slug].pop ?? 0)}</small></span>
                    <span className="bar" style={{ width: `${(100 * r.v) / f.people[0].v}%` }} /></span>
                  <span className="v">{dec(r.v)}</span>
                </button>
              </li>
            ) : null)}
          </ol>
        </Figure>
      </section>

      <section className="bp-sec" aria-labelledby="ct-s5">
        <h2 id="ct-s5">{t('cities.s5.h')}</h2>
        {para('cities.s5.p1')}
        <Figure id="ct-kinds" q={t('cities.s5.q')} unit={t('cities.s5.unit')} source={src} so={t('cities.s5.so')}
                table={<Table head={['', ...KINDS.map((k) => t(`cities.kinds.${k}`))]} rows={f.cities.slice(0, 12).map((c) => [name(c), ...KINDS.map((k) => N(c.kinds[k] ?? 0))])} />}>
          <Legend items={BAR.map((k) => t(`cities.kinds.${k}`))} rest={t('cities.s5.rest')} />
          <ol className="cn-kinds" dir="ltr">
            {f.cities.slice(0, 12).map((c) => {
              const parts = [...BAR.map((k) => [t(`cities.kinds.${k}`), c.kinds[k] ?? 0] as const),
                             [t('cities.s5.rest'), REST.reduce((a, k) => a + (c.kinds[k] ?? 0), 0)] as const];
              const total = parts.reduce((a, p) => a + p[1], 0) || 1;
              const main = [...parts].sort((a, b) => b[1] - a[1])[0];
              return (
                <li key={c.slug}>
                  <span className="nm" dir="auto">{name(c)}</span>
                  <span className="bar" role="img" aria-label={parts.filter((p) => p[1]).map((p) => `${p[0]} ${p[1]}`).join('، ')}>
                    {parts.map(([k, v], i) => (v ? <i key={k} className={`kc-${i < BAR.length ? i + 1 : 'rest'}`} style={{ width: `${(100 * v) / total}%` }} /> : null))}
                  </span>
                  <span className="lab" dir="auto">{pct(`${main[0]} ${Math.round((100 * main[1]) / total)}٪`)}</span>
                </li>
              );
            })}
          </ol>
        </Figure>
      </section>

      <section className="bp-method" aria-labelledby="ct-m">
        <h2 id="ct-m">{t('cities.method.h')}</h2>
        <ul>
          {(['read', 'names', 'old', 'together', 'traps', 'people', 'check'] as const).map((k) => <li key={k}>{t(`cities.method.${k}`, { texts: N(f.totals.texts), cities: f.totals.cities })}</li>)}
        </ul>
        <p><Link to="/places">{t('countries.method.finder')}</Link></p>
      </section>
      {sheet ? <PlaceSheet slug={sheet} onClose={() => setSheet(null)} /> : null}
    </article>
  );
}
