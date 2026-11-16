import { type KeyboardEvent, type PointerEvent, useEffect, useMemo, useRef } from 'react';
import { useTheme, useWidth } from '../viz';
import { colours, layout, paint } from './paint';
import { MONTH_START } from './time';

/**
 * The post's picture: a row a year from 1913 at the top to 2026 at the foot, a mark a day from January at the left to
 * December at the right (charts run left to right on an Arabic page too), gold where the legal time stood an hour
 * ahead of Greenwich. Drawn on a canvas at the device's pixels (41,724 days); its words in an SVG over it, never under
 * 14 px. A tap or the arrows pick a day; the page says what the law said that day.
 */
export type Pick = { year: number; slot: number };
export type Outline = { year: number; from: number; to: number };

export function Grid({ rows, first, focus, outlines, picked, onPick, aria, monthNames, lang, labelled, tall = 0 }: {
  rows: Uint8Array[];
  first: number;
  focus: [number, number] | null;
  outlines: Outline[];
  picked: Pick | null;
  onPick: (p: Pick) => void;
  aria: string;
  monthNames: string[];
  lang: string;
  /** Years named at the right of their row on a wide screen. */
  labelled: Record<number, string>;
  /** The height the rows may fill on a desk. */
  tall?: number;
}) {
  const [ref, width] = useWidth<HTMLDivElement>(360);
  const canvas = useRef<HTMLCanvasElement>(null);
  const theme = useTheme();
  const l = useMemo(() => layout(width, rows.length, Object.keys(labelled).length > 0, tall), [width, rows.length, labelled, tall]);
  const last = first + rows.length - 1;

  useEffect(() => {
    const cv = canvas.current;
    if (!cv) return;
    const dpr = Math.min(3, window.devicePixelRatio || 1);
    cv.width = Math.round(l.width * dpr);
    cv.height = Math.round(l.height * dpr);
    const ctx = cv.getContext('2d')!;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, l.width, l.height);
    const col = colours(cv);
    paint(ctx, rows, l, col, focus, first, picked?.year ?? null);
    ctx.lineWidth = 1.5;
    ctx.strokeStyle = col.stamp;
    for (const o of outlines) {
      const i = o.year - first;
      ctx.strokeRect(l.left + o.from * l.cell - 1, l.top + i * l.rowH - 1.5, (o.to - o.from + 1) * l.cell + 2, l.rowH - l.gap + 3);
    }
    if (picked) {
      const i = picked.year - first, x = l.left + (picked.slot + 0.5) * l.cell, y = l.top + i * l.rowH;
      ctx.fillStyle = col.ink;
      ctx.fillRect(x - 0.75, l.top - 4, 1.5, l.height - l.top);
      ctx.fillRect(l.left - 6, y + (l.rowH - l.gap) / 2 - 0.75, l.width - l.left - l.right + 6, 1.5);
      ctx.beginPath();
      ctx.arc(x, y + (l.rowH - l.gap) / 2, 4.5, 0, Math.PI * 2);
      ctx.fillStyle = col.sheet; ctx.fill();
      ctx.lineWidth = 2; ctx.strokeStyle = col.ink; ctx.stroke();
    }
  }, [rows, l, focus, outlines, picked, first, theme]);

  const at = (e: PointerEvent<HTMLDivElement>): Pick | null => {
    const box = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - box.left, y = e.clientY - box.top;
    if (x < l.left - 4 || y < l.top - 4) return null;
    if (x > l.width - l.right + 4) return null;
    const slot = Math.max(0, Math.min(365, Math.floor((x - l.left) / l.cell)));
    const year = first + Math.max(0, Math.min(rows.length - 1, Math.floor((y - l.top) / l.rowH)));
    return { year, slot };
  };
  const move = (e: PointerEvent<HTMLDivElement>) => {
    // A finger scrolls the page; it picks a day where it lands and while it drags sideways (pan-y).
    if (e.pointerType !== 'mouse' && e.type === 'pointermove' && e.buttons === 0) return;
    const p = at(e);
    if (p) onPick(p);
  };
  const key = (e: KeyboardEvent<HTMLDivElement>) => {
    const p = picked ?? { year: last, slot: 263 };
    const next = { ArrowLeft: { ...p, slot: p.slot - 1 }, ArrowRight: { ...p, slot: p.slot + 1 }, ArrowUp: { ...p, year: p.year - 1 },
                   ArrowDown: { ...p, year: p.year + 1 }, Home: { ...p, slot: 0 }, End: { ...p, slot: 365 } }[e.key];
    if (!next) return;
    e.preventDefault();
    onPick({ year: Math.max(first, Math.min(last, next.year)), slot: Math.max(0, Math.min(365, next.slot)) });
  };

  // Year labels: the first and last, and each decade, kept 13 px apart at the least.
  const years = [first, ...Array.from({ length: 12 }, (_, k) => 1920 + k * 10).filter((y) => y < last), last]
    .filter((y, i, a) => i === 0 || (y - a[i - 1]) * l.rowH >= 13 || y === last);
  const wide = l.right > 2;
  const monthsShown = width >= 620 ? monthNames.map((_, m) => m) : [0, 3, 6, 9];
  return (
    <div ref={ref} className="ck-grid" dir="ltr" style={{ height: l.height }} role="img" aria-label={aria} tabIndex={0}
         onPointerDown={move} onPointerMove={move} onKeyDown={key}>
      <canvas ref={canvas} style={{ width: l.width, height: l.height }} />
      <svg width={l.width} height={l.height} aria-hidden="true">
        {monthsShown.map((m) => (
          <text key={m} x={l.left + MONTH_START[m] * l.cell + 2} y={15} className="ck-axis" direction={lang === 'fr' ? 'ltr' : 'rtl'}
                textAnchor={lang === 'fr' ? 'start' : 'end'}>
            {monthNames[m]}
          </text>
        ))}
        {monthsShown.map((m) => <line key={`m${m}`} x1={l.left + MONTH_START[m] * l.cell} x2={l.left + MONTH_START[m] * l.cell} y1={19} y2={l.top - 2} className="ck-axis-tick" />)}
        {years.map((y) => (
          <text key={y} x={l.left - 7} y={l.top + (y - first) * l.rowH + l.rowH / 2 + 4.5} textAnchor="end" className="ck-axis">{y}</text>
        ))}
        {wide ? Object.entries(labelled).map(([y, text]) => (
          <g key={`n${y}`}>
            <line x1={l.width - l.right + 2} x2={l.width - l.right + 10} y1={l.top + (+y - first) * l.rowH + l.rowH / 2} y2={l.top + (+y - first) * l.rowH + l.rowH / 2} className="ck-axis-tick" />
            <text x={l.width - l.right + 14} y={l.top + (+y - first) * l.rowH + l.rowH / 2 + 4.5} direction={lang === 'fr' ? 'ltr' : 'rtl'}
                  textAnchor={lang === 'fr' ? 'start' : 'end'} className="ck-axis is-note">{text}</text>
          </g>
        )) : null}
      </svg>
    </div>
  );
}
