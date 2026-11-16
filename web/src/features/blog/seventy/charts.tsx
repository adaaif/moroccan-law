import { useMemo, useState, type CSSProperties } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { longDate } from '@/features/corpus/format';
import type { SeventyPost } from '../blog.api';
import { Bars, Figure, Table } from '../kit';
import { dec, decadeTicks, n } from '../viz';
import { decades, type YearRow } from './rows';
import { useWidth } from '../viz';

/** The post's quieter charts, one a section: texts a year, the days it comes out, the thickest issues, the eighties'
 *  pages against the Bulletin's own numbering, the kinds of text by decade, the price of an issue. */

// Time runs left to right on an Arabic page too (1 Nov 2026: charts are read left to right in Arabic too).
const useRtl = () => false;

/** The line every chart is signed with. */
function useSource(post: SeventyPost): string {
  return useTranslation('blog').t('fig.source', { from: post.span[0], to: post.span[1] });
}

export function TextsChart({ post, rows }: { post: SeventyPost; rows: YearRow[] }) {
  const { t, i18n } = useTranslation('blog');
  const src = useSource(post);
  const lang = i18n.language;
  const rtl = useRtl();
  const [picked, setPicked] = useState<number | null>(null);
  const most = rows.reduce((a, r, i) => (r.texts > rows[a].texts ? i : a), 0);
  const ref = Math.max(0, rows.findIndex((r) => r.year === 1956));
  const [first, last] = post.span;
  // The texts only the French edition printed (1912–1925), a dashed band over their years: never in the Arabic count.
  const french = rows.map((r) => post.figures.french?.[String(r.year)]?.[1] ?? 0);
  const fr = (i: number) => (french[i] ? t('seventy.s1.pickFr', { fr: n(french[i], lang) }) : '');
  return (
    <Figure id="texts" q={t('seventy.s1.q')} source={src}
            pick={picked === null ? t('fig.hint') : `${t('seventy.s1.pick', { year: rows[picked].year, texts: n(rows[picked].texts, lang) })}${fr(picked)}`}
            so={t('seventy.s1.so', { year: rows[most].year, max: n(rows[most].texts, lang), times: Math.floor(rows[most].texts / rows[ref].texts), count: Math.floor(rows[most].texts / rows[ref].texts), first: rows[ref].year })}
            table={<Table head={[t('seventy.piles.cols.year'), t('seventy.piles.cols.texts'), t('seventy.s1.colFr')]}
                          rows={rows.map((r, i) => [r.year, n(r.texts, lang), french[i] ? n(french[i], lang) : '–'])} />}>
      <ul className="bp-legend" dir="ltr">
        <li><i className="bp-key-ar" aria-hidden="true" /><span dir="auto">{t('seventy.s1.keyAr')}</span></li>
        <li><i className="bp-key-fr" aria-hidden="true" /><span dir="auto">{t('seventy.s1.keyFr')}</span></li>
      </ul>
      <Bars values={rows.map((r) => r.texts)} over={french} hi={[ref, most]} rtl={rtl} picked={picked} onPick={setPicked}
            labels={{ [ref]: n(rows[ref].texts, lang), [most]: n(rows[most].texts, lang) }} ticks={decadeTicks(first, last)}
            aria={t('seventy.s1.q')} />
    </Figure>
  );
}

/** Three weeks, one an era of the Bulletin's days: each day a stamp as large as the issues that came out on it. */
export function WeekChart({ post }: { post: SeventyPost }) {
  const { t, i18n } = useTranslation('blog');
  const src = useSource(post);
  const lang = i18n.language;
  const days = t('days', { returnObjects: true }) as string[];
  const [picked, setPicked] = useState<string>(t('fig.hintDay'));
  const eras = useMemo(() => post.weekdays.map((era, k) => {
    const from = Number(era.from.slice(0, 4));
    const next = post.weekdays[k + 1];
    const to = next ? Number(next.from.slice(0, 4)) - 1 : post.span[1];
    const counts = [0, 0, 0, 0, 0, 0, 0];
    for (let y = from; y <= to; y++) (post.figures.weekdays[String(y)] ?? []).forEach((c, d) => { counts[d] += c; });
    return { from, to, counts, total: counts.reduce((a, b) => a + b, 0) };
  }), [post]);
  const max = Math.max(...eras.flatMap((e) => e.counts));
  // An era of one year is named by its year («1913», not «1913–1913»).
  const era = (e: { from: number; to: number }) => (e.from === e.to ? String(e.from) : t('seventy.s2.era', e));
  const [ref, width] = useWidth<HTMLDivElement>(640);
  const narrow = width < 540;
  const stamp = (e: (typeof eras)[number], d: number) => {
    const c = e.counts[d];
    return (
      <button key={`${e.from}-${d}`} type="button" role="cell" className={`bp-day${c > max / 4 ? ' main' : ''}`}
              disabled={!c} aria-label={`${days[d]}، ${era(e)}: ${n(c, lang)}`}
              onClick={() => setPicked(t('seventy.s2.pick', { day: days[d], from: e.from, to: e.to, total: n(c, lang) }))}>
        {c ? <span style={{ '--s': Math.max(0.28, Math.sqrt(c / max)) } as CSSProperties}>{n(c, lang)}</span> : null}
      </button>
    );
  };
  return (
    <Figure id="week" q={t('seventy.s2.q')} so={t('seventy.s2.so')} source={src} pick={picked}
            table={<Table head={['', ...days]} rows={eras.map((e) => [era(e), ...e.counts.map((c) => n(c, lang))])} />}>
      <div ref={ref} className={`bp-week${narrow ? ' is-narrow' : ''}`} role="table" aria-label={t('seventy.s2.q')}
           style={{ '--eras': eras.length } as CSSProperties}>
        {narrow ? (
          // On a phone the week stands on its side: a day a row, an era a column, so each day's name keeps its width.
          <>
            <div className="bp-week-row bp-week-head" role="row">
              <span role="columnheader" />
              {eras.map((e) => (
                <span key={e.from} className="bp-week-era" role="columnheader">
                  <b>{era(e)}</b><span>{t('seventy.s2.eraCount', { total: n(e.total, lang) })}</span>
                </span>
              ))}
            </div>
            {days.map((day, d) => (
              <div key={day} className="bp-week-row" role="row">
                <span className="bp-week-day" role="rowheader">{day}</span>
                {eras.map((e) => stamp(e, d))}
              </div>
            ))}
          </>
        ) : (
          <>
            <div className="bp-week-row bp-week-head" role="row">
              <span role="columnheader" />
              {days.map((d) => <span key={d} className="bp-week-day" role="columnheader">{d}</span>)}
            </div>
            {eras.map((e) => (
              <div key={e.from} className="bp-week-row" role="row">
                <span className="bp-week-era" role="rowheader">
                  <b>{era(e)}</b>
                  <span>{t('seventy.s2.eraCount', { total: n(e.total, lang) })}</span>
                </span>
                {e.counts.map((_, d) => stamp(e, d))}
              </div>
            ))}
          </>
        )}
      </div>
    </Figure>
  );
}

/** The ten thickest issues, each a strip as long as its pages, with what it carries. */
export function Thickest({ post }: { post: SeventyPost }) {
  const { t, i18n } = useTranslation('blog');
  const src = useSource(post);
  const lang = i18n.language;
  const list = post.figures.thickest;
  const max = list[0].pages;
  const label = (key: string) => key.replace('-bis', lang === 'fr' ? ' bis' : ' مكرر');
  return (
    <Figure id="thick" q={t('seventy.s3.q')} unit={t('seventy.s3.unit')} so={t('seventy.s3.so')} source={src}
            table={<Table head={[t('seventy.piles.cols.issue'), '', t('seventy.piles.cols.pages')]}
                          rows={list.map((i) => [label(i.key), longDate(i.date, lang), n(i.pages, lang)])} />}>
      <ol className="bp-thick">
        {list.map((i) => (
          <li key={i.key}>
            <Link to={`/bo/general_ar/${i.key}`}>
              <span className="bp-thick-id">{label(i.key)}<small>{longDate(i.date, lang)}</small></span>
              <span className="bp-thick-what">{post.issues[i.key]?.[lang === 'fr' ? 'fr' : 'ar'] ?? ''}</span>
              <span className={`bp-thick-bar${i.report ? ' is-report' : ''}`} style={{ '--w': i.pages / max } as CSSProperties}>
                <i aria-hidden="true" />
                <b>{t('seventy.s3.pages', { pages: n(i.pages, lang) })}</b>
              </span>
            </Link>
          </li>
        ))}
      </ol>
    </Figure>
  );
}

/** The pages of the files each year, and across each bar the last page the Bulletin printed that year. */
export function ProofChart({ post, rows }: { post: SeventyPost; rows: YearRow[] }) {
  const { t, i18n } = useTranslation('blog');
  const src = useSource(post);
  const lang = i18n.language;
  const rtl = useRtl();
  const [picked, setPicked] = useState<number | null>(null);
  // The thinnest year since independence (1913 counts its issues from February).
  const since = Math.max(0, rows.findIndex((r) => r.year === 1956));
  const least = rows.reduce((a, r, i) => (i >= since && r.pages < rows[a].pages ? i : a), since);
  const ref = rows.findIndex((r) => r.year === 1973);
  const pick = (i: number) => {
    const r = rows[i];
    return t(r.printed ? 'seventy.s4.pick' : 'seventy.s4.pickNone', { year: r.year, pages: n(r.pages, lang), printed: n(r.printed, lang) });
  };
  return (
    <Figure id="proof" q={t('seventy.s4.q')} unit={t('seventy.s4.unit')} source={src}
            pick={picked === null ? t('fig.hint') : pick(picked)}
            so={t('seventy.s4.so', { year: rows[least].year, printed: n(rows[least].printed, lang), pages: n(rows[least].pages, lang) })}
            table={<Table head={[t('seventy.piles.cols.year'), t('seventy.s4.cols.pages'), t('seventy.s4.cols.printed')]}
                          rows={rows.map((r) => [r.year, n(r.pages, lang), r.printed ? n(r.printed, lang) : '–'])} />}>
      <Bars values={rows.map((r) => r.pages)} marks={rows.map((r) => r.printed || null)} hi={[ref, least]} rtl={rtl}
            picked={picked} onPick={setPicked} height={190}
            labels={{ [ref]: n(rows[ref].pages, lang), [least]: n(rows[least].pages, lang) }}
            ticks={decadeTicks(post.span[0], post.span[1])} aria={t('seventy.s4.q')} />
    </Figure>
  );
}

const KINDS = ['dahir', 'law', 'decree', 'order'] as const;

/** Four small charts, one a kind of text: its share of each decade's texts. */
export function KindsChart({ post, rows }: { post: SeventyPost; rows: YearRow[] }) {
  const { t, i18n } = useTranslation('blog');
  const src = useSource(post);
  const lang = i18n.language;
  const rtl = useRtl();
  const [picked, setPicked] = useState<{ kind: (typeof KINDS)[number]; i: number } | null>(null);
  const groups = useMemo(() => decades(rows).map((d) => {
    const texts = d.rows.reduce((a, r) => a + r.texts, 0);
    return { ...d, share: Object.fromEntries(KINDS.map((k) => [k, (100 * d.rows.reduce((a, r) => a + r[k], 0)) / texts])) };
  }), [rows]);
  const pct = (v: number) => (v === 0 ? '0' : v < 1 ? dec(v, 1) : String(Math.round(v)));
  const sign = lang === 'fr' ? '\u202f%' : '٪';
  const last = groups.length - 1;
  return (
    <Figure id="kinds" q={t('seventy.s5.q')} unit={t('seventy.s5.unit')} so={t('seventy.s5.so')} source={src}
            pick={picked ? t('seventy.s5.pick', { kind: t(`seventy.s5.kinds.${picked.kind}`), from: groups[picked.i].from,
                                                  to: groups[picked.i].to, share: pct(groups[picked.i].share[picked.kind]) }) : t('fig.hint')}
            table={<Table head={['', ...KINDS.map((k) => t(`seventy.s5.kinds.${k}`))]}
                          rows={groups.map((g) => [`${g.from}–${g.to}`, ...KINDS.map((k) => `${pct(g.share[k])}${sign}`)])} />}>
      <div className="bp-multi">
        {KINDS.map((k) => (
          <figure key={k}>
            <figcaption>{t(`seventy.s5.kinds.${k}`)}</figcaption>
            <Bars values={groups.map((g) => g.share[k])} height={120} rtl={rtl} hi={[last]}
                  picked={picked?.kind === k ? picked.i : null} onPick={(i) => setPicked(i === null ? null : { kind: k, i })}
                  labels={{ 0: `${pct(groups[0].share[k])}${sign}`, [last]: `${pct(groups[last].share[k])}${sign}` }}
                  aria={t(`seventy.s5.kinds.${k}`)} />
          </figure>
        ))}
      </div>
      <div className="bp-axis-row" dir="ltr"><span>{`${groups[0].from}–${groups[0].to}`}</span><span>{`${groups[last].from}–${groups[last].to}`}</span></div>
    </Figure>
  );
}

/** The price an issue's masthead prints, a column a price, from the first issue that prints it. */
export function PricesChart({ post }: { post: SeventyPost }) {
  const { t, i18n } = useTranslation('blog');
  const src = useSource(post);
  const lang = i18n.language;
  const [picked, setPicked] = useState<number | null>(null);
  const prices = post.prices;
  const dh = (p: (typeof prices)[number]) => (p.unit === 'centime' ? p.price / 10000 : p.unit === 'franc' ? p.price / 100 : p.price);
  const max = Math.max(...prices.map(dh));
  const shown = (p: (typeof prices)[number]) => (Number.isInteger(p.price) ? String(p.price) : dec(p.price, p.unit === 'dirham' ? 2 : 1));
  const unit = (p: (typeof prices)[number]) => t(p.unit === 'centime' ? 'units.centime' : p.unit === 'franc' ? (p.price < 2 ? 'units.franc1' : p.price < 11 ? 'units.francs' : 'units.franc')
                                                  : p.price >= 2 && p.price < 11 ? 'units.dirhams' : 'units.dirham');
  const first = dh(prices[0]), top = dh(prices[prices.length - 1]);
  return (
    <Figure id="prices" q={t('seventy.s6.q')} unit={t('seventy.s6.unit')} source={src}
            so={t('seventy.s6.so', { times: n(Math.round(top / first), lang) })}
            pick={picked === null ? t('fig.hintPrice') : t('seventy.s6.pick', { from: longDate(prices[picked].from, lang), price: `${shown(prices[picked])} ${unit(prices[picked])}`, issue: prices[picked].issue })}
            table={<Table head={['', t('seventy.s6.unit')]} rows={prices.map((p) => [longDate(p.from, lang), `${shown(p)} ${unit(p)}`])} />}>
      {/* The prices in time order, left to right on an Arabic page too (the chart rule of 1 Nov 2026). */}
      <ol className="bp-prices" dir="ltr">
        {prices.map((p, i) => (
          <li key={p.from}>
            <button type="button" aria-pressed={picked === i} onClick={() => setPicked(i)}>
              <span className="bp-price-tag"><b>{shown(p)}</b><small>{unit(p)}</small></span>
              <span className="bp-price-bar" style={{ '--h': dh(p) / max } as CSSProperties} aria-hidden="true" />
              <span className="bp-price-year">{p.from.slice(0, 4)}</span>
            </button>
          </li>
        ))}
      </ol>
    </Figure>
  );
}

