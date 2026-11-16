import { useMemo, useState, type KeyboardEvent, type PointerEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { longDate } from '@/features/corpus/format';
import type { AgreementsPost } from '../blog.api';
import { decadeTicks, spaced, stepFor, useWidth } from '../viz';

/** A day as a year with its fraction, to place it in time. */
const when = (iso: string) => { const d = new Date(`${iso}T00:00:00Z`); return d.getUTCFullYear() + d.getUTCMonth() / 12 + (d.getUTCDate() - 1) / 365; };
const ROWS = 14;

/**
 * The post's one picture: a row for each lender, the most frequent first, and a short line for each decree that
 * (or, in the first years, a dahir) approved a loan from it (in the source's violet) or the State's guarantee of a loan it made to a public body (in the
 * corrected brown), at the day of its issue. A tap names the decree and opens it; the arrows walk the decrees in time.
 */
export default function Lenders({ post }: { post: AgreementsPost }) {
  const { t, i18n } = useTranslation('blog');
  const lang = i18n.language;
  const rtl = lang !== 'fr';
  const [ref, width] = useWidth<HTMLDivElement>(900);
  const [pick, setPick] = useState<number | null>(null);
  const f = post.figures;
  const [first, last] = f.span;
  const name = (k: string) => { const x = f.names[k]; return x ? (rtl ? x.short_ar ?? x.ar : x.short_fr ?? x.fr) : t('agreements.others'); };
  const rows = useMemo(() => {
    const top = f.lenders.slice(0, ROWS).map((l) => l.key);
    const rest = f.lenders.slice(ROWS);
    return [...top.map((k) => ({ keys: [k], n: f.lenders.find((l) => l.key === k)!.n, label: k })),
            ...(rest.length ? [{ keys: rest.map((l) => l.key), n: rest.reduce((s, l) => s + l.n, 0), label: '' }] : [])];
  }, [f.lenders]);
  const rowOf = useMemo(() => Object.fromEntries(rows.flatMap((r, i) => r.keys.map((k) => [k, i]))), [rows]);
  const phone = width < 640;
  const labels = rows.map((r) => (r.label ? name(r.label) : t('agreements.others')));
  // The names take the room the longest needs, measured in the chart's type, at most two fifths of the width.
  const label = useMemo(() => {
    const ctx = typeof document === 'undefined' ? null : document.createElement('canvas').getContext('2d');
    if (ctx) ctx.font = '14px "Readex Pro", sans-serif';
    return Math.min(width * 0.4, 14 + Math.max(...labels.map((s, i) => (ctx ? ctx.measureText(`${s} ${rows[i].n}`).width : s.length * 7.5))));
  }, [labels, rows, width]);
  const rowH = phone ? 26 : 28, foot = 24;
  const height = rows.length * rowH + foot;
  const t0 = first, t1 = last + 1;
  const plot = width - label - 8;
  const x = (tt: number) => (rtl ? width - label - ((tt - t0) / (t1 - t0)) * plot : label + ((tt - t0) / (t1 - t0)) * plot);
  const marks = useMemo(() => f.money.map(([date, kind, lender], i) => ({ i, x: x(when(date)), row: rowOf[lender], kind })),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [f.money, width, rtl, label, rowOf]);
  const move = (e: PointerEvent<SVGSVGElement>) => {
    const box = e.currentTarget.getBoundingClientRect();
    const px = e.clientX - box.left, row = Math.floor((e.clientY - box.top) / rowH);
    let best = -1, dist = 10;
    for (const m of marks) if (m.row === row && Math.abs(m.x - px) < dist) { dist = Math.abs(m.x - px); best = m.i; }
    if (best >= 0) setPick(best);
  };
  const key = (e: KeyboardEvent<SVGSVGElement>) => {
    const d = stepFor(e, rtl);
    if (!d) return;
    e.preventDefault();
    setPick((p) => Math.max(0, Math.min(f.money.length - 1, (p ?? (d > 0 ? -1 : f.money.length)) + d)));
  };
  const chosen = pick === null ? null : f.money[pick];
  const ticks = decadeTicks(first, last);
  const decades = f.decades.filter((d) => d > first);
  return (
    <div className="ag-lenders">
      <div ref={ref} className="bp-plot">
        <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} role="img" aria-label={t('agreements.hero.aria')} tabIndex={0}
             onPointerMove={(e) => e.pointerType === 'mouse' && move(e)} onPointerDown={move} onKeyDown={key}>
          {decades.map((d) => <line key={d} x1={x(d)} x2={x(d)} y1={0} y2={rows.length * rowH} className="ag-decade" />)}
          {rows.map((r, i) => (
            <g key={r.label || 'others'}>
              <line x1={rtl ? 0 : label} x2={rtl ? width - label : width} y1={(i + 1) * rowH - 0.5} y2={(i + 1) * rowH - 0.5} className="ag-row" />
              <text x={rtl ? width : 0} y={i * rowH + rowH / 2 + 5} textAnchor="start" direction={rtl ? 'rtl' : 'ltr'} className="ag-name">
                {labels[i]} <tspan className="is-soft">{r.n}</tspan>
              </text>
            </g>
          ))}
          {marks.map((m) => (
            <line key={m.i} x1={m.x} x2={m.x} y1={m.row * rowH + 5} y2={(m.row + 1) * rowH - 6}
                  className={`ag-mark${m.kind === 1 ? ' is-guarantee' : ''}`} />
          ))}
          {chosen ? (() => { const m = marks[pick!]; return (
            <g className="ag-picked"><line x1={m.x} x2={m.x} y1={m.row * rowH + 2} y2={(m.row + 1) * rowH - 3} /></g>); })() : null}
          {spaced(ticks, (i) => x(first + i + 0.5)).map(([i, year]) => (
            <text key={i} x={Math.min(Math.max(x(first + +i + 0.5), rtl ? 18 : label + 18), rtl ? width - label - 18 : width - 18)} y={height - 6}
                  textAnchor="middle" className="is-soft">{year}</text>
          ))}
        </svg>
      </div>
      <p className="bp-pick" aria-live="polite">
        {chosen ? <>{t('agreements.hero.pick', { act: t(`agreements.act.${chosen[3].includes('/dahir/') ? 'dahir' : 'decret'}`), number: chosen[4].replace(/-/g, '.'),
                                                 date: longDate(chosen[0], lang), kind: t(`agreements.kinds.${f.kinds[chosen[1]]}`),
                                                 lender: name(chosen[2]) })}{' '}
          <Link to={chosen[3]}>{t('agreements.hero.open')}</Link></> : t('agreements.hero.hint')}
      </p>
    </div>
  );
}
