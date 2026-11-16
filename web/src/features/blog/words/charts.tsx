import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { longDate } from '@/features/corpus/format';
import type { WordCount, WordsPost, WordStop } from '../blog.api';
import { Bars, Figure, Table } from '../kit';
import { decadeTicks, dec, n, spaced, useWidth } from '../viz';
import { opening } from './opening';

/** The third post's quieter charts: each word's stops, two pairs of words as lines, and the words a ministry's name
 *  carried. */

function useWords(post: WordsPost) {
  const { i18n } = useTranslation('blog');
  const fr = i18n.language === 'fr';
  return useMemo(() => {
    const counts = Object.fromEntries(post.figures.words.map((w) => [w.key, w]));
    const names: Record<string, string> = {};
    for (const g of post.groups) for (const w of g.words) names[w.key] = fr ? w.fr : w.ar;
    return { counts, names };
  }, [post, fr]);
}

function useSource(post: WordsPost) {
  return useTranslation('blog').t('fig.source', { from: post.figures.span[0], to: post.figures.span[1] });
}

/** One word's stops down a line, read in time: a hollow dot its first mention, a full one the first text on the subject,
 *  a small one each step after; each says what the text did, quotes it, and opens its article (or its issue). */
export function Road({ word, name, stops, open }: { word: string; name: string; stops: WordStop[]; open?: { ar: string; fr: string } }) {
  const { t, i18n } = useTranslation('blog');
  const lang = i18n.language;
  const fr = lang === 'fr';
  return (
    <section className="bp-road" aria-label={name}>
      <h3 className="bp-road-word">{name}</h3>
      <ol>
        {stops.map((s) => (
          <li key={`${word}-${s.date}-${s.path}`} className={`is-${s.kind}`}>
            <span className="bp-road-when">
              <span className="bp-road-date">{longDate(s.date, lang)}</span>
              <span className="bp-road-kind">{t(`words.stop.${s.kind}`)}</span>
            </span>
            <span className="bp-road-what" dir="auto">{fr ? s.fr : s.ar}</span>
            <span className="bp-road-src">
              <Link to={s.path} className="bp-road-text" lang="ar" dir="rtl" title={s.title}>{s.title}</Link>
              <span className="bp-road-issue">{t('words.s1.issue', { issue: s.issue.replace('-bis', fr ? ' bis' : ' مكرر'), page: s.page ?? '–' })}</span>
            </span>
            {s.path.startsWith('/bo/') ? <span className="bp-road-uncut">{t('words.stop.uncut')}</span> : null}
          </li>
        ))}
      </ol>
      {open ? <p className="bp-road-open">{fr ? open.fr : open.ar}</p> : null}
    </section>
  );
}

/** The words that entered, each with its stops, in the order of their first mention. */
export function Roads({ post }: { post: WordsPost }) {
  const { t, i18n } = useTranslation('blog');
  const lang = i18n.language;
  const src = useSource(post);
  const { counts, names } = useWords(post);
  const entered = post.groups.find((g) => g.key === 'entered')?.words ?? [];
  const rows = entered.map((w) => counts[w.key]).filter((w) => w?.stops?.length)
    .sort((a, b) => a.stops![0].date.localeCompare(b.stops![0].date));
  const late = rows.filter((w) => (opening(w, post.figures.span[0])?.date ?? '') >= '1990').length;
  const kind = (k: string) => t(`words.stop.${k}`);
  return (
    <Figure id="firsts" q={t('words.s1.q')} unit={t('words.s1.unit')} source={src} so={t('words.s1.so', { n: n(late, lang) })} wide
            table={<Table head={['', '', '', '', '']} rows={rows.flatMap((w) => w.stops!.map((s) => [
              longDate(s.date, lang), names[w.key], kind(s.kind), lang === 'fr' ? s.fr : s.ar,
              t('words.s1.issue', { issue: s.issue, page: s.page ?? '–' })]))} />}>
      <div className="bp-roads">
        {rows.map((w) => <Road key={w.key} word={w.key} name={names[w.key]} stops={w.stops!} open={w.open} />)}
      </div>
    </Figure>
  );
}

/** The stops of the words a chart draws, under it. */
export function Stops({ post, keys }: { post: WordsPost; keys: string[] }) {
  const { counts, names } = useWords(post);
  return (
    <div className="bp-roads">
      {keys.filter((k) => counts[k]?.stops?.length).map((k) => (
        <Road key={k} word={k} name={names[k]} stops={counts[k].stops!} open={counts[k].open} />
      ))}
    </div>
  );
}

/** Two words as lines of texts in a thousand, a year a point, each named where it ends. */
function Lines({ a, b, texts, first, names, onPick, picked }: {
  a: WordCount; b: WordCount; texts: number[]; first: number; names: Record<string, string>;
  onPick: (i: number) => void; picked: number | null;
}) {
  const { i18n } = useTranslation('blog');
  const rtl = i18n.language !== 'fr';
  const [ref, width] = useWidth<HTMLDivElement>(640);
  const height = 200, top = 14, foot = 24, end = 120;
  const plot = width - end;
  const per = (w: WordCount) => w.years.map((v, i) => (texts[i] ? (1000 * v) / texts[i] : 0));
  const sa = per(a), sb = per(b);
  const max = Math.max(...sa, ...sb) || 1;
  const count = texts.length;
  const x = (i: number) => (rtl ? width - (i / (count - 1)) * plot : (i / (count - 1)) * plot);
  const y = (v: number) => top + (height - top - foot) * (1 - v / max);
  const path = (s: number[]) => s.map((v, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(' ');
  // The names where the lines end, kept apart.
  let ya = y(sa[count - 1]), yb = y(sb[count - 1]);
  if (Math.abs(ya - yb) < 18) { const m = (ya + yb) / 2; [ya, yb] = ya < yb ? [m - 9, m + 9] : [m + 9, m - 9]; }
  const ex = rtl ? x(count - 1) - 8 : x(count - 1) + 8;
  const ticks = decadeTicks(first, first + count - 1);
  return (
    <div ref={ref} className="bp-plot">
      <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`${names[a.key]}، ${names[b.key]}`}
           onPointerDown={(e) => { const box = e.currentTarget.getBoundingClientRect(); const px = e.clientX - box.left;
             onPick(Math.max(0, Math.min(count - 1, Math.round(((rtl ? width - px : px) / plot) * (count - 1))))); }}>
        <line className="bp-axis" x1={rtl ? end : 0} x2={rtl ? width : plot} y1={height - foot + 0.5} y2={height - foot + 0.5} />
        {picked !== null ? <line className="bp-guide" x1={x(picked)} x2={x(picked)} y1={top} y2={height - foot} /> : null}
        <path d={path(sb)} className="bp-line soft" />
        <path d={path(sa)} className="bp-line" />
        <text x={ex} y={ya + 5} direction={rtl ? 'rtl' : 'ltr'} textAnchor="start" className="is-strong">{names[a.key]}</text>
        <text x={ex} y={yb + 5} direction={rtl ? 'rtl' : 'ltr'} textAnchor="start" className="is-soft">{names[b.key]}</text>
        {spaced(ticks, x).map(([i, year]) => (
          <text key={i} x={Math.min(Math.max(x(+i), rtl ? end + 18 : 18), rtl ? width - 18 : plot - 18)} y={height - 6} textAnchor="middle" className="is-soft">{year}</text>
        ))}
      </svg>
    </div>
  );
}

/** «فرنك» and «درهم», then «المعاقين» and «في وضعية إعاقة». */
export function Pairs({ post, cross }: { post: WordsPost; cross: number }) {
  const { t, i18n } = useTranslation('blog');
  const lang = i18n.language;
  const src = useSource(post);
  const { counts, names } = useWords(post);
  const f = post.figures;
  const [p1, setP1] = useState<number | null>(null);
  const [p2, setP2] = useState<number | null>(null);
  const say = (i: number | null, keys: string[]) => (i === null ? t('fig.hint') : t('words.s2.pick', {
    year: f.span[0] + i,
    list: keys.map((k) => `«${names[k]}» ${dec((1000 * counts[k].years[i]) / (f.texts[i] || 1), 1)}‰`).join(lang === 'fr' ? ', ' : '، '),
  }));
  return (
    <>
      <Figure id="franc" q={t('words.s2.q1')} so={t('words.s2.so1')} source={src} pick={say(p1, ['dirham', 'franc'])}>
        <Lines a={counts.dirham} b={counts.franc} texts={f.texts} first={f.span[0]} names={names} onPick={setP1} picked={p1} />
      </Figure>
      <Figure id="handicap" q={t('words.s2.q2')} so={t('words.s2.so2', { cross })} source={src} pick={say(p2, ['disabled_new', 'disabled_old'])}>
        <Lines a={counts.disabled_new} b={counts.disabled_old} texts={f.texts} first={f.span[0]} names={names} onPick={setP2} picked={p2} />
      </Figure>
    </>
  );
}

const ERAS = ['investment', 'privatization', 'environment'] as const;

/** Each word of an era: its texts a year, and darker the part that only carries it in a ministry's name. */
export function Titles({ post }: { post: WordsPost }) {
  const { t, i18n } = useTranslation('blog');
  const lang = i18n.language;
  const rtl = lang !== 'fr';
  const src = useSource(post);
  const { counts, names } = useWords(post);
  const f = post.figures;
  const [picked, setPicked] = useState<{ k: (typeof ERAS)[number]; i: number } | null>(null);
  const inv = counts.investment.years, invT = counts.investment_title.years;
  const peak = inv.indexOf(Math.max(...inv));
  return (
    <Figure id="titles" q={t('words.s3.q')} unit={t('words.s3.unit')} source={src}
            so={t('words.s3.so', { invYear: f.span[0] + peak, invShare: Math.round((100 * invT[peak]) / inv[peak]) })}
            pick={picked ? t('words.s3.pick', { word: names[picked.k], year: f.span[0] + picked.i, n: n(counts[picked.k].years[picked.i], lang),
                                                title: n(counts[`${picked.k}_title`].years[picked.i], lang) }) : t('fig.hint')}
            table={<Table head={['', ...ERAS.flatMap((k) => [names[k], t('words.s3.inTitle')])]}
                          rows={f.texts.map((_, i) => [f.span[0] + i, ...ERAS.flatMap((k) => [n(counts[k].years[i], lang), n(counts[`${k}_title`].years[i], lang)])])} />}>
      <div className="bp-multi bp-eras">
        {ERAS.map((k) => {
          const all = counts[k].years, part = counts[`${k}_title`].years;
          const top = all.indexOf(Math.max(...all));
          return (
            <figure key={k}>
              <figcaption>{names[k]}</figcaption>
              <Bars values={all} parts={part} rtl={rtl} height={130} picked={picked?.k === k ? picked.i : null}
                    onPick={(i) => setPicked(i === null ? null : { k, i })} labels={{ [top]: n(all[top], lang) }}
                    ticks={{ 0: String(f.span[0]), [all.length - 1]: String(f.span[1]) }} aria={names[k]} />
            </figure>
          );
        })}
      </div>
    </Figure>
  );
}

