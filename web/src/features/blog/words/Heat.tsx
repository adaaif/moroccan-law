import { useMemo, useState, type KeyboardEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { longDate } from '@/features/corpus/format';
import type { WordsPost } from '../blog.api';
import { decadeTicks, n, spaced, stepFor, useWidth } from '../viz';
import { opening } from './opening';

type Row = { key: string; name: string; years: number[]; group?: string };

/**
 * The post's one picture: a row a word, a cell a year, each cell as dark as the share of that year's texts that carry
 * the word, against the word's own best year, so a rare word shows its shape as clearly as a common one. The groups
 * (words that left, replaced others, had an era, entered) are named between the rows. A tap answers with the count.
 */
export default function Heat({ post }: { post: WordsPost }) {
  const { t, i18n } = useTranslation('blog');
  const lang = i18n.language;
  const rtl = lang !== 'fr';
  const [ref, width] = useWidth<HTMLDivElement>(900);
  const [pick, setPick] = useState<{ r: number; y: number } | null>(null);
  const f = post.figures;
  const [first, last] = f.span;
  const count = f.texts.length;
  const counts = useMemo(() => Object.fromEntries(f.words.map((w) => [w.key, w])), [f.words]);
  const rows = useMemo(() => {
    const out: Row[] = [];
    for (const g of post.groups) {
      out.push({ key: `g-${g.key}`, name: lang === 'fr' ? g.fr : g.ar, years: [], group: g.key });
      for (const w of g.words) if (!w.part_of && counts[w.key]) out.push({ key: w.key, name: lang === 'fr' ? w.fr : w.ar, years: counts[w.key].years });
    }
    return out;
  }, [post.groups, counts, lang]);
  const words = rows.filter((r) => !r.group);

  const phone = width < 640;
  // The names take the room the longest needs, measured in the chart's type, and never more than two fifths.
  const longest = useMemo(() => {
    const ctx = typeof document === 'undefined' ? null : document.createElement('canvas').getContext('2d');
    if (ctx) ctx.font = '14px "Readex Pro", sans-serif';
    return Math.max(...rows.map((r) => (ctx ? ctx.measureText(r.name).width : r.name.length * 7.5)));
  }, [rows]);
  const label = Math.min(width * 0.42, longest + 14);
  const rowH = phone ? 20 : 24;
  const groupH = phone ? 30 : 34;
  const top = 4;
  const cell = (width - label) / count;
  const x = (i: number) => (rtl ? width - label - (i + 1) * cell : label + i * cell);
  let y = top;
  const placed = rows.map((r) => { const at = y; y += r.group ? groupH : rowH; return { ...r, y: at }; });
  const height = y + 26;

  const share = (r: Row, i: number) => (f.texts[i] ? r.years[i] / f.texts[i] : 0);
  const peaks = useMemo(() => Object.fromEntries(words.map((r) => [r.key, Math.max(...r.years.map((_, i) => share(r, i)))])),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [words, f.texts]);

  const sentence = (() => {
    if (!pick) return t('words.hero.hint');
    const r = words[pick.r];
    const fi = opening(counts[r.key], first);
    return (
      <>
        {t('words.hero.pick', { word: r.name, year: first + pick.y, n: n(r.years[pick.y], lang), texts: n(f.texts[pick.y], lang) })}{' '}
        {fi ? <Link to={fi.path}>{t(fi.kind === 'first' ? 'words.hero.first' : 'words.hero.subject', { date: longDate(fi.date, lang) })}</Link> : null}
      </>
    );
  })();
  const key = (e: KeyboardEvent<SVGSVGElement>) => {
    const d = stepFor(e, rtl);
    const cur = pick ?? { r: 0, y: d < 0 ? count : -1 };
    if (d) { e.preventDefault(); setPick({ r: Math.max(0, cur.r), y: Math.max(0, Math.min(count - 1, cur.y + d)) }); }
    else if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault();
      setPick({ r: Math.max(0, Math.min(words.length - 1, cur.r + (e.key === 'ArrowDown' ? 1 : -1))), y: Math.max(0, Math.min(count - 1, cur.y)) });
    }
  };
  const ticks = decadeTicks(first, last);
  return (
    <div className="bp-heat">
      <div ref={ref} className="bp-plot">
        <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} role="img" tabIndex={0} onKeyDown={key}
             aria-label={t('words.hero.aria', { from: first, to: last })}>
          {placed.map((r) => r.group ? (
            <text key={r.key} x={rtl ? width : 0} y={r.y + groupH - 10} textAnchor="start" direction={rtl ? 'rtl' : 'ltr'} className="heat-group">{r.name}</text>
          ) : (
            <g key={r.key}>
              <text x={rtl ? width - 4 : 4} y={r.y + rowH / 2 + 5} textAnchor="start" direction={rtl ? 'rtl' : 'ltr'} className="heat-word">{r.name}</text>
              {r.years.map((_, i) => {
                const v = share(r, i) / (peaks[r.key] || 1);
                const wi = words.indexOf(r);
                return (
                  <rect key={i} x={x(i)} y={r.y + 2} width={Math.max(1, cell - (phone ? 0.5 : 1))} height={rowH - 4}
                        className={pick && pick.r === wi && pick.y === i ? 'heat-pick' : v ? 'heat-on' : 'heat-off'}
                        style={v ? { opacity: 0.12 + 0.88 * Math.sqrt(v) } : undefined}
                        onPointerDown={() => setPick({ r: wi, y: i })}
                        onPointerEnter={(e) => e.pointerType === 'mouse' && setPick({ r: wi, y: i })} />
                );
              })}
            </g>
          ))}
          {spaced(ticks, (i) => x(i) + cell / 2).map(([i, year]) => (
            <text key={i} x={Math.min(Math.max(x(+i) + cell / 2, rtl ? 18 : label + 18), rtl ? width - label - 18 : width - 18)} y={height - 6} textAnchor="middle" className="is-soft">{year}</text>
          ))}
        </svg>
      </div>
      <p className="bp-pick" aria-live="polite">{sentence}</p>
    </div>
  );
}
