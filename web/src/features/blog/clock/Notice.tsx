import { type KeyboardEvent, type PointerEvent, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { useWidth } from '../viz';
import type { Notice as N } from './time';

/**
 * How many days before a move the Bulletin first printed its text: a dot a move, the years left to right, above the
 * line printed before the clock moved, below it after (in the repealed red, named in the legend). A tap or the arrows
 * walk the moves; the page says which text, printed which day.
 */
export function Notice({ rows, picked, onPick, aria, labels }: {
  rows: N[];
  picked: number | null;
  onPick: (i: number) => void;
  aria: string;
  /** Words beside a few dots, by the move's day. */
  labels: Record<string, string>;
}) {
  const { i18n } = useTranslation('blog');
  const [ref, width] = useWidth<HTMLDivElement>(640);
  const height = width < 480 ? 230 : 270;
  const left = 34, right = 10, top = 22, bottom = 26;
  const lo = Math.min(-45, ...rows.map((r) => r.days)), hi = Math.max(90, ...rows.map((r) => r.days));
  const year = (r: N) => Number(r.move.at.slice(0, 4)) + (Number(r.move.at.slice(5, 7)) - 1) / 12;
  const x0 = 1916, x1 = 2028;
  const x = (r: N) => left + ((year(r) - x0) / (x1 - x0)) * (width - left - right);
  const y = (d: number) => top + ((hi - d) / (hi - lo)) * (height - top - bottom);
  const ticks = [-30, 0, 30, 60, 90].filter((d) => d >= lo && d <= hi);
  const decades = [1920, 1940, 1960, 1980, 2000, 2020];
  const order = useMemo(() => rows.map((_, i) => i), [rows]);
  const rtl = i18n.language !== 'fr';
  // A label near the right edge runs leftward from its dot, near the left edge rightward: in an RTL text «start» is
  // its right edge.
  const anchor = (px: number) => (px > width * 0.72 ? (rtl ? 'start' : 'end') : px < width * 0.28 ? (rtl ? 'end' : 'start') : 'middle');
  const nearest = (e: PointerEvent<SVGSVGElement>) => {
    const box = e.currentTarget.getBoundingClientRect();
    const px = e.clientX - box.left, py = e.clientY - box.top;
    let best = 0, dist = Infinity;
    rows.forEach((r, i) => {
      const d = (x(r) - px) ** 2 + ((y(r.days) - py) ** 2) / 4;
      if (d < dist) { dist = d; best = i; }
    });
    onPick(best);
  };
  const key = (e: KeyboardEvent<SVGSVGElement>) => {
    const d = e.key === 'ArrowRight' ? 1 : e.key === 'ArrowLeft' ? -1 : 0;
    if (!d) return;
    e.preventDefault();
    onPick(Math.max(0, Math.min(rows.length - 1, (picked ?? (d > 0 ? -1 : rows.length)) + d)));
  };
  return (
    <div ref={ref} className="bp-plot ck-notice" dir="ltr">
      <svg width={width} height={height} role="img" aria-label={aria} tabIndex={0} onPointerDown={nearest}
           onPointerMove={(e) => e.pointerType === 'mouse' && nearest(e)} onKeyDown={key}>
        {ticks.map((d) => (
          <g key={d}>
            <line x1={left} x2={width - right} y1={y(d)} y2={y(d)} className={d === 0 ? 'ck-zero' : 'ck-rule'} />
            <text x={left - 6} y={y(d) + 4.5} textAnchor="end" className="is-soft">{d}</text>
          </g>
        ))}
        {decades.map((d) => (
          <text key={d} x={left + ((d - x0) / (x1 - x0)) * (width - left - right)} y={height - 6} textAnchor="middle" className="is-soft">{d}</text>
        ))}
        {order.map((i) => {
          const r = rows[i];
          return <circle key={i} cx={x(r)} cy={y(r.days)} r={i === picked ? 6.5 : 4.5}
                         className={`ck-dot${r.days < 0 ? ' is-late' : ''}${i === picked ? ' is-picked' : ''}`} />;
        })}
        {rows.map((r, i) => (labels[r.move.at.slice(0, 10)] ? (
          r.days < 0 ? (
            <text key={`l${i}`} x={x(r) + 10} y={y(r.days) + 5} textAnchor={rtl ? 'end' : 'start'} direction={rtl ? 'rtl' : 'ltr'} className="is-strong">
              {labels[r.move.at.slice(0, 10)]}
            </text>
          ) : (
            <text key={`l${i}`} x={Math.min(width - right - 4, Math.max(left + 4, x(r)))} y={y(r.days) - 11}
                  textAnchor={anchor(x(r))} direction={rtl ? 'rtl' : 'ltr'} className="is-strong">{labels[r.move.at.slice(0, 10)]}</text>
          )
        ) : null))}
      </svg>
    </div>
  );
}
