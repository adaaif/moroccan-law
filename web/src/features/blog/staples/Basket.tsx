import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { reducedMotion } from '@/shared/services/motion';
import { useWidth } from '../viz';

/**
 * Five staples on three days: 5 September 1980, 29 May 1981, 7 June 1981. A line each from the first price (100) to the
 * other two, so a rise and its half-return read the same for bread at 0,70 DH and flour at 94 DH a quintal. Under the
 * columns, the time between them: months up, days back. The lines draw themselves once, up then back, when the chart
 * comes into view (the post's one motion that plays by itself); a tap picks a line and the page names its three orders.
 * Each line is named at its end, with what it kept of the rise. Left to right on an Arabic page too.
 */
export type Item = { key: string; name: string; values: number[] };

export function Basket({ items, columns, spans, picked, onPick, aria }: {
  items: Item[];
  /** The three days and their issues, as their heads print them (the issue's short name for a phone). */
  columns: [string, string, string][];
  /** The time between the columns, in words: «9 أشهر», «9 أيام». */
  spans: [string, string];
  picked: string;
  onPick: (k: string) => void;
  aria: string;
}) {
  const { i18n } = useTranslation('blog');
  const rtl = i18n.language !== 'fr';
  const [ref, width] = useWidth<HTMLDivElement>(640);
  const box = useRef<HTMLDivElement>(null);
  const [on, setOn] = useState(() => reducedMotion());
  // Once drawn, the chart holds still: a line picked later moves to the front without drawing itself again.
  const [done, setDone] = useState(on);
  useEffect(() => {
    if (on || !box.current) return;
    const io = new IntersectionObserver(([e]) => { if (e.isIntersecting) { setOn(true); io.disconnect(); } }, { threshold: 0.45 });
    io.observe(box.current);
    return () => io.disconnect();
  }, [on]);
  useEffect(() => {
    if (!on || done) return;
    const t = window.setTimeout(() => setDone(true), 2800);
    return () => window.clearTimeout(t);
  }, [on, done]);
  const phone = width < 560;
  const left = phone ? 52 : 92, right = phone ? 96 : 150, top = 70, bottom = 50;
  const height = phone ? 360 : 400;
  const xs = [left, (left + width - right) / 2, width - right];
  const lo = 94, hi = 180;
  const y = (v: number) => top + (1 - (v - lo) / (hi - lo)) * (height - top - bottom);
  const index = (it: Item) => it.values.map((v) => (v / it.values[0]) * 100);
  // The names at the lines' ends keep 19 px apart.
  const spread = (ys: number[]) => {
    const order = ys.map((v, i) => [v, i] as const).sort((a, b) => a[0] - b[0]);
    const out = [...ys];
    let prev = -Infinity;
    for (const [v, i] of order) { out[i] = Math.max(v, prev + 19); prev = out[i]; }
    return out;
  };
  const endY = spread(items.map((it) => y(index(it)[2])));
  // The picked line's rise goes over its peak, unless another peak sits just above it (one within 6 px is the same
  // line to the eye): then under it, inside the line's own angle.
  const over = (it: Item) => {
    const py = y(index(it)[1]);
    return !items.some((o) => o !== it && py - y(index(o)[1]) > 6 && py - y(index(o)[1]) < 44);
  };
  const base = height - bottom;
  // A right-to-left word whose left edge sits at x: in an RTL text the anchor «end» is its left side.
  const leftEdge = rtl ? 'end' : 'start';
  return (
    <div ref={(el) => { ref(el); box.current = el; }} className={`sp-basket${on ? ' is-on' : ''}${done ? ' is-done' : ''}`} dir="ltr">
      <svg width={width} height={height} role="img" aria-label={aria}>
        {columns.map(([day, issue, short], i) => (
          <g key={day}>
            <line x1={xs[i]} x2={xs[i]} y1={top - 14} y2={base} className="sp-col" />
            <text x={xs[i]} y={18} textAnchor="middle" className="sp-col-day" direction={rtl ? 'rtl' : 'ltr'}>{day}</text>
            <text x={xs[i]} y={40} textAnchor="middle" className="sp-col-issue" direction={rtl ? 'rtl' : 'ltr'}>{phone ? short : issue}</text>
          </g>
        ))}
        {/* The time between the columns: the columns stand at the same distance, the time does not. */}
        {spans.map((s, i) => {
          const a = xs[i] + 6, b = xs[i + 1] - 6, yy = base + 18;
          return (
            <g key={s} className={`sp-span is-${i}`}>
              <path d={`M${a} ${yy - 6}V${yy}H${b}V${yy - 6}`} />
              <text x={(a + b) / 2} y={yy + 20} textAnchor="middle" direction={rtl ? 'rtl' : 'ltr'}>{s}</text>
            </g>
          );
        })}
        <text x={xs[0] - 12} y={y(100) + 5} textAnchor="end" className="sp-tick">100</text>
        {/* The picked line last, so it is drawn over the others. */}
        {items.map((it, k) => [it, k] as const).sort((a, b) => Number(a[0].key === picked) - Number(b[0].key === picked)).map(([it, k]) => {
          const v = index(it);
          const isOn = it.key === picked;
          const up = `M${xs[0]} ${y(v[0])}L${xs[1]} ${y(v[1])}`, back = `M${xs[1]} ${y(v[1])}L${xs[2]} ${y(v[2])}`;
          const rise = Math.round(v[1] - 100), kept = Math.round(v[2] - 100);
          return (
            <g key={it.key} className={`sp-line${isOn ? ' is-picked' : ''}`} onPointerDown={() => onPick(it.key)} style={{ ['--k' as string]: k }}>
              <path d={up + back} className="sp-hit" />
              <path d={up} pathLength={1} className="sp-up" />
              <path d={back} pathLength={1} className="sp-back" />
              {[0, 1, 2].map((i) => <circle key={i} cx={xs[i]} cy={y(v[i])} r={isOn ? 5.5 : 3.5} className={`sp-dot is-${i}`} />)}
              {isOn ? <text x={xs[1]} y={y(v[1]) + (over(it) ? -14 : 30)} textAnchor="middle" className="sp-peak">+{rise}%</text> : null}
              <g className="sp-end">
                <text x={xs[2] + 12} y={endY[k] + 5} textAnchor="start" className="sp-end-pct">+{kept}%</text>
                <text x={xs[2] + (phone ? 58 : 64)} y={endY[k] + 5} textAnchor={leftEdge} direction={rtl ? 'rtl' : 'ltr'} className="sp-end-name">{it.name}</text>
              </g>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
