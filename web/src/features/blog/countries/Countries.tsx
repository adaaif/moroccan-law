import { useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { WorldMap, type Dot } from '@/features/places/Maps';
import { PlaceSheet } from '@/features/places/parts';
import '@/features/places/places.css';
import type { CountriesPost, CountryRow } from '../blog.api';
import { Head } from '../Head';
import { Figure, Legend, Table } from '../kit';
import { pct } from '@/shared/locales/i18n';
import { dec, endSpans, ends, n, since1956 } from '../viz';
import '@/shared/design/french.css';
import '../post.css';
import './countries.css';

const KINDS = ['studies', 'treaty', 'missions', 'loan', 'finance', 'customs', 'people', 'transport', 'other'] as const;
// The bar's own colours: the four kinds that weigh, then the rest in grey (loans, customs, transport and the finance law
// are about 1 % each: as colours they were slivers nobody could name). The table keeps all nine.
const BAR = ['studies', 'treaty', 'people', 'missions'] as const;

/** A state's line over the periods: every text solid, without the diploma lists dashed; time from left to right, on an
 *  Arabic page too (1 Nov 2026: charts are read left to right in Arabic too): 1913 on the left, the dot on today, a
 *  thin upright at 1956 (`mark`, the first period of independence; C3 of the posts-from-No.-1 review). */
function Line({ s, x, max, tone, mark, w = 112, h = 40 }: { s: number[]; x?: number[]; max: number; tone: 'rise' | 'fall' | 'ink'; mark?: number; w?: number; h?: number }) {
  const at = (i: number) => 3 + (i * (w - 6)) / (s.length - 1);
  const y = (v: number) => h - 3 - ((h - 8) * v) / (max || 1);
  const pts = (vs: number[]) => vs.map((v, i) => `${at(i).toFixed(1)},${y(v).toFixed(1)}`).join(' ');
  const m = mark && mark > 0 ? (at(mark - 1) + at(mark)) / 2 : null;
  return (
    <svg className={`cn-line ${tone}`} viewBox={`0 0 ${w} ${h}`} width={w} height={h} aria-hidden="true">
      {m !== null ? <line x1={m} x2={m} y1={1} y2={h - 1} className="y56" /> : null}
      {x ? <polyline points={pts(x)} className="nodip" /> : null}
      <polyline points={pts(s)} className="all" />
      <circle cx={at(s.length - 1)} cy={y(s[s.length - 1])} r="2.8" className="end" />
    </svg>
  );
}

/**
 * «العالم في الجريدة الرسمية» (post 1 of the places review, 1 Nov 2026): the world in postmarks, period by period
 * (PL7), with the switch that leaves out the diploma lists (PL5, C3: every text first); who rose and who fell (PL8); why
 * the Bulletin names a state (PL9); the states that are gone, as cancelled postmarks (PL10); the world filling in, year
 * by year (PL11); how names were printed (PL12). A tap on a postmark opens the place's sheet, the finder's own (PL23).
 */
export default function Countries({ post }: { post: CountriesPost }) {
  const { t, i18n } = useTranslation('blog');
  const lang = i18n.language;
  const rtl = lang !== 'fr';
  const f = post.figures;
  const N = (v: number) => n(v, lang);
  const P = f.periods.map(([a, b]) => (a === b ? `${a}` : `${a}–${b}`));
  const last = P.length - 1;
  const k56 = since1956(f.periods);
  const spans = endSpans(f.periods);
  const by = useMemo(() => Object.fromEntries(f.states.map((s) => [s.slug, s])) as Record<string, CountryRow>, [f]);
  const name = (s: CountryRow) => (rtl ? s.ar : s.fr || s.en);
  const [period, setPeriod] = useState(0);
  const [nodip, setNodip] = useState(false);
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
  const v = (s: CountryRow, i = period) => (nodip ? s.x : s.s)[i];
  const max = Math.max(...f.states.flatMap((s) => s.s));
  const dots: Dot[] = useMemo(() => f.states.filter((s) => s.lat != null && s.lon != null)
    .map((s) => ({ slug: s.slug, ar: s.ar, fr: s.fr || s.en, lat: s.lat!, lon: s.lon!, value: v(s), gone: s.gone })),
  // eslint-disable-next-line react-hooks/exhaustive-deps
  [f, period, nodip]);
  const ranked = [...f.states].filter((s) => v(s) > 0).sort((a, b) => v(b) - v(a)).slice(0, 8);
  const top = ranked[0] ? v(ranked[0]) : 1;
  const src = t('fig.source', { from: f.periods[0][0], to: f.periods[last][1] });
  const fr = by.france, dz = by.algeria, ua = by.ukraine, ru = by.russia;
  const rose = f.moves.rose.map((k) => by[k]).filter(Boolean);
  const fell = f.moves.fell.map((k) => by[k]).filter(Boolean);
  const kindsTop = f.states.filter((s) => !s.gone).slice(0, 12);
  const gone = f.states.filter((s) => s.gone);
  const oldest = [...gone].filter((s) => s.first?.year).sort((a, b) => (a.first!.year ?? 0) - (b.first!.year ?? 0))[0];
  const climbAt = (y: number) => f.climb.counts[y - f.climb.from] ?? 0;
  const climbYears = f.climb.counts.length;
  const [pickYear, setPickYear] = useState<number | null>(null);
  const sep = rtl ? '، ' : ', ';
  const heavy = (kind: string, share: number, most: number) => f.states.filter((s) => !s.gone && s.n >= 50)
    .filter((s) => (s.kinds[kind] ?? 0) / Object.values(s.kinds).reduce((a, b) => a + b, 0) >= share).slice(0, most).map(name).join(sep);
  const studiesShare = Math.round((100 * f.totals.studies) / Math.max(1, Object.values(f.kinds).reduce((a, b) => a + b, 0)));
  const para = (key: string, values: Record<string, unknown> = {}) => <p className="bp-p">{t(key, values)}</p>;

  return (
    <article className="bp" lang={lang}>
      <Head post={post} />

      <figure className="bp-hero cn-hero" aria-labelledby="cn-q">
        <div className="bp-hero-words">
          <p className="bp-q" id="cn-q">{t('countries.hero.q')}</p>
          <p className="bp-unit">{t('countries.hero.how')}</p>
        </div>
        <div className="cn-controls">
          <div className="cn-periods" dir="ltr" role="group" aria-label={t('countries.hero.periods')}>
            {P.map((p, i) => (
              <button key={p} type="button" className={i === k56 ? 'y56' : undefined} aria-pressed={i === period}
                      onClick={() => { if (timer.current) play(); setPeriod(i); }}>{p}</button>
            ))}
          </div>
          <button type="button" className="cn-play" onClick={play}>{playing ? t('countries.hero.stop') : t('countries.hero.play', { from: f.periods[0][0], to: f.periods[last][1] })}</button>
          <label className="cn-switch"><input type="checkbox" checked={nodip} onChange={(e) => setNodip(e.target.checked)} /> {t('countries.hero.nodip')}</label>
          {k56 > 0 ? <p className="cn-key cn-56">{t('countries.hero.periods56')}</p> : null}
        </div>
        <div className="cn-stage">
          <WorldMap dots={dots} max={max} picked={sheet} onPick={setSheet} rtl={rtl} label={t('countries.hero.aria', { period: P[period] })} />
          <ol className="cn-rank" dir="ltr" aria-label={t('countries.hero.rank', { period: P[period] })}>
            {ranked.map((s, i) => (
              <li key={s.slug}>
                <button type="button" onClick={() => setSheet(s.slug)}>
                  <span className="r">{i + 1}</span>
                  <span className="nm"><b>{name(s)}</b><i style={{ width: `${(100 * v(s)) / top}%` }} /></span>
                  <span className="v">{dec(v(s))}</span>
                </button>
              </li>
            ))}
          </ol>
        </div>
        <div className="bp-hero-foot">
          <p className="bp-pick" aria-live="polite">{t('countries.hero.pick', { period: P[period], texts: N(f.texts[period]), first: ranked[0] ? name(ranked[0]) : '',
            v: ranked[0] ? dec(v(ranked[0])) : '' })}</p>
          <p className="bp-so"><b>{t('fig.so')}</b> {t('countries.hero.so', { fr0: dec(fr?.s[0] ?? 0), fr1: dec(fr?.s[last] ?? 0), ua1: dec(ua?.s[last] ?? 0),
            ua1x: dec(ua?.x[last] ?? 0), first: P[0], last: P[last], uaFirst: ua?.first?.year ?? '' })}</p>
          <p className="bp-src">{src}</p>
        </div>
      </figure>

      <section className="bp-sec" aria-labelledby="cn-s1">
        <h2 id="cn-s1">{t('countries.s1.h')}</h2>
        {para('countries.s1.p1', { fr0: dec(fr?.s[0] ?? 0), fr1: dec(fr?.s[last] ?? 0), dz0: dec(dz?.s[0] ?? 0), dz1: dec(dz?.s[last] ?? 0), first: P[0], last: P[last],
                                   p56: P[Math.max(k56, 0)], fr56: dec(fr?.s[Math.max(k56, 0)] ?? 0), base0: dec(f.baseline[0]), base1: dec(f.baseline[last]) })}
        {para('countries.s1.p2', { ru1: dec(ru?.s[last] ?? 0), ru1x: dec(ru?.x[last] ?? 0), ua1: dec(ua?.s[last] ?? 0), ua1x: dec(ua?.x[last] ?? 0), share: studiesShare })}
        <Figure id="cn-moves" q={t('countries.s1.q')} unit={t('countries.s1.unit', { p0: spans[0], p1: spans[1] })} source={src}
                so={t('countries.s1.so')}
                table={<Table head={['', ...P]} rows={[...rose, ...fell].map((s) => [name(s), ...s.s.map((x) => dec(x))])} />}>
          <div className="cn-moves">
            {[['rise', rose, t('countries.s1.rose')] as const, ['fall', fell, t('countries.s1.fell')] as const].map(([tone, rows, title]) => (
              <div key={tone}>
                <h3 className={`cn-col ${tone}`}>{title}</h3>
                <ol>
                  {rows.map((s) => (
                    <li key={s.slug}>
                      <button type="button" onClick={() => setSheet(s.slug)} className="cn-move">
                        <span className="nm"><b>{name(s)}</b>
                          <span>{t('countries.s1.from', { a: dec(ends(s.s)[0]), b: dec(ends(s.s)[1]), x: dec(ends(s.x)[1]) })}</span></span>
                        <Line s={s.s} x={s.x} max={Math.max(...s.s, ...s.x, 0.5)} tone={tone} mark={k56} />
                      </button>
                    </li>
                  ))}
                </ol>
              </div>
            ))}
          </div>
          <p className="cn-key">{t('countries.s1.key')}</p>
        </Figure>
      </section>

      <section className="bp-sec" aria-labelledby="cn-s2">
        <h2 id="cn-s2">{t('countries.s2.h')}</h2>
        {para('countries.s2.p1', { share: studiesShare })}
        <Figure id="cn-kinds" q={t('countries.s2.q')} unit={t('countries.s2.unit')} source={src} so={t('countries.s2.so', { studies: heavy('studies', 0.7, 4), treaties: heavy('treaty', 0.5, 3) })}
                table={<Table head={['', ...KINDS.map((k) => t(`countries.kinds.${k}`))]} rows={kindsTop.map((s) => [name(s), ...KINDS.map((k) => N(s.kinds[k] ?? 0))])} />}>
          <Legend items={BAR.map((k) => t(`countries.kinds.${k}`))} rest={t('countries.s2.rest')} />
          <ol className="cn-kinds" dir="ltr">
            {kindsTop.map((s) => {
              const total = Object.values(s.kinds).reduce((a, b) => a + b, 0) || 1;
              const parts = [...BAR.map((k) => [t(`countries.kinds.${k}`), s.kinds[k] ?? 0] as const),
                             [t('countries.s2.rest'), total - BAR.reduce((a, k) => a + (s.kinds[k] ?? 0), 0)] as const];
              const main = [...parts].sort((a, b) => b[1] - a[1])[0];
              return (
                <li key={s.slug}>
                  <span className="nm" dir="auto">{name(s)}</span>
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

      <section className="bp-sec" aria-labelledby="cn-s3">
        <h2 id="cn-s3">{t('countries.s3.h')}</h2>
        <p className="bp-p">{t('countries.s3.p1', { count: gone.length, ussrLast: by['soviet-union']?.last ?? '' })}
          {oldest?.first?.year ? ` ${t('countries.s3.oldest', { name: name(oldest), year: oldest.first.year })}` : ''}</p>
        <ul className="cn-gone">
          {gone.map((s) => (
            <li key={s.slug}>
              <button type="button" onClick={() => setSheet(s.slug)}>
                <svg viewBox="0 0 92 92" aria-hidden="true">
                  <circle cx="46" cy="46" r="40" className="o" /><circle cx="46" cy="46" r="30" className="i" />
                  {[0, 1, 2, 3].map((j) => <path key={j} d={`M4 ${30 + j * 9} Q 24 ${24 + j * 9} 46 ${30 + j * 9} T 88 ${30 + j * 9}`} className="w" />)}
                  <text x="46" y="51" textAnchor="middle" direction="ltr">{s.first?.year ?? ''}–{String(s.last).slice(2)}</text>
                </svg>
                <b>{name(s)}</b>
                <span>{t('countries.s3.texts', { count: s.n, n: N(s.n) })}{s.successor && by[s.successor] ? ` · ${t('countries.s3.now', { name: name(by[s.successor]) })}` : ''}</span>
              </button>
            </li>
          ))}
        </ul>
      </section>

      <section className="bp-sec" aria-labelledby="cn-s4">
        <h2 id="cn-s4">{t('countries.s4.h')}</h2>
        {para('countries.s4.p1', { y1956: climbAt(1956), y2000: climbAt(2000), all: f.totals.states, never: f.totals.never })}
        <Figure id="cn-climb" q={t('countries.s4.q')} unit={t('countries.s4.unit')} source={src}
                pick={pickYear === null ? t('fig.hint') : t('countries.s4.pick', { year: pickYear, count: climbAt(pickYear) })}
                so={t('countries.s4.so', { y1956: climbAt(1956), all: f.totals.states })}
                table={<Table head={[t('countries.s4.year'), t('countries.s4.unit')]} rows={f.climb.counts.map((c, i) => [f.climb.from + i, c]).filter((_, i) => i % 5 === 0)} />}>
          <div className="cn-climb" dir="ltr" role="group" aria-label={t('countries.s4.q')}>
            {f.climb.counts.map((c, i) => (
              <button key={i} type="button" style={{ height: `${(100 * c) / Math.max(1, f.climb.counts[climbYears - 1])}%` }}
                      className={[pickYear === f.climb.from + i ? 'on' : '', f.climb.from + i === 1956 ? 'y56' : ''].join(' ').trim() || undefined}
                      onClick={() => setPickYear(f.climb.from + i)}
                      aria-label={t('countries.s4.pick', { year: f.climb.from + i, count: c })} />
            ))}
          </div>
          <div className="cn-axis" dir="ltr" aria-hidden="true"><span>{f.climb.from}</span>
            {f.climb.from < 1956 ? <span className="at56" style={{ left: `${(100 * (1956 - f.climb.from + 0.5)) / climbYears}%` }}>1956</span> : null}
            <span>{f.climb.from + climbYears - 1}</span></div>
        </Figure>
        {f.never.length ? <p className="bp-p cn-never">{t('countries.s4.never', { count: f.never.length, list: f.never.map((x) => (rtl ? x.ar : x.fr)).join('، ') })}</p> : null}
      </section>

      <section className="bp-sec" aria-labelledby="cn-s5">
        <h2 id="cn-s5">{t('countries.s5.h')}</h2>
        {para('countries.s5.p1')}
        <ul className="cn-spell">
          {f.states.filter((s) => s.spellings.length > 1).slice(0, 10).map((s) => (
            <li key={s.slug}><b>{name(s)}</b>{s.spellings.map((sp) => <span key={sp} lang="ar" dir="rtl">{sp}</span>)}</li>
          ))}
        </ul>
      </section>

      <section className="bp-method" aria-labelledby="cn-m">
        <h2 id="cn-m">{t('countries.method.h')}</h2>
        <ul>
          {(['read', 'names', 'old', 'share', 'kinds', 'traps'] as const).map((k) => (
            <li key={k}>{t(`countries.method.${k}`, { texts: N(f.totals.texts), states: f.totals.states })}</li>
          ))}
          <li>{t('countries.method.edition')} {f.totals.conventions ? t('countries.method.editionRead', { n: N(f.totals.conventions) }) : t('countries.method.editionNot')}</li>
          <li>{t('countries.method.check')}</li>
        </ul>
        <p><Link to="/places">{t('countries.method.finder')}</Link></p>
      </section>
      {sheet ? <PlaceSheet slug={sheet} onClose={() => setSheet(null)} /> : null}
    </article>
  );
}
