import { type KeyboardEvent, type PointerEvent, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { useWidth } from '../viz';
import { type Segment, yearOf } from '../marquise/price';

/**
 * A litre of gasoil as the orders wrote it: the price in dirhams on top, the same price in minutes of work at the minimum
 * wage under it, on one line of years (1975 at the left). Where the Bulletin stopped writing the price (1995–2002, the
 * ministry published it; from 2014, «بكل وسيلة») the years are hatched. A finger or the arrows run a line across both
 * panels; the page names the price and the order of that day.
 */
export type Away = { from: string; to: string | null; label: string };

const X0 = 1974.5, X1 = 2016.5;

export function Gasoil({ segs, steps, away, picked, onPick, aria, labels }: {
  segs: Segment[];
  /** Each order's day and price in dirhams a litre, for its dot. */
  steps: { from: string; dh: number }[];
  away: Away[];
  /** The year picked, as a number (1984.85). */
  picked: number | null;
  onPick: (yr: number) => void;
  aria: string;
  labels: { dh: string; minutes: string; hour: string };
}) {
  const { i18n } = useTranslation('blog');
  const rtl = i18n.language !== 'fr';
  const [ref, width] = useWidth<HTMLDivElement>(640);
  const phone = width < 560;
  const m = { l: phone ? 30 : 40, r: 12 };
  const W = width - m.l - m.r;
  const x = (yr: number) => m.l + ((yr - X0) / (X1 - X0)) * W;
  const p1 = { top: 22, h: phone ? 150 : 190 }, p2 = { top: (phone ? 150 : 190) + 70, h: phone ? 110 : 140 };
  const height = p2.top + p2.h + 30;
  const yDh = (v: number) => p1.top + p1.h - (v / 9) * p1.h;
  const yMin = (v: number) => p2.top + p2.h - (v / 70) * p2.h;
  const minutes = (s: Segment) => (s.hours ?? 0) * 60;

  const paths = useMemo(() => {
    const runs: Segment[][] = [];
    let run: Segment[] = [];
    for (const s of segs) {
      if (s.dh === null || s.hours === null) { if (run.length) runs.push(run); run = []; continue; }
      if (s.gap) { run.push({ ...s, to: s.from }); runs.push(run); run = []; continue; }
      run.push(s);
    }
    if (run.length) runs.push(run);
    const path = (r: Segment[], f: (s: Segment) => number) =>
      r.map((s, i) => `${i ? 'L' : 'M'}${x(yearOf(s.from)).toFixed(1)} ${f(s).toFixed(1)}H${x(yearOf(s.to)).toFixed(1)}`).join('');
    return { dh: runs.map((r) => path(r, (s) => yDh(s.dh!))).join(''), min: runs.map((r) => path(r, (s) => yMin(minutes(s)))).join('') };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [segs, width]);

  const scrub = (e: PointerEvent<SVGSVGElement>) => {
    if (e.pointerType === 'mouse' || e.type === 'pointerdown' || e.buttons) {
      const box = e.currentTarget.getBoundingClientRect();
      onPick(Math.max(1975, Math.min(2016, X0 + ((e.clientX - box.left - m.l) / W) * (X1 - X0))));
    }
  };
  const key = (e: KeyboardEvent<SVGSVGElement>) => {
    const d = e.key === 'ArrowRight' ? 1 : e.key === 'ArrowLeft' ? -1 : 0;
    if (!d) return;
    e.preventDefault();
    // The arrows walk the orders, one step at a time.
    const at = picked ?? (d > 0 ? 1974 : 2017);
    const next = d > 0 ? steps.find((s) => yearOf(s.from) > at + 0.001) : [...steps].reverse().find((s) => yearOf(s.from) < at - 0.001);
    if (next) onPick(yearOf(next.from) + 0.0001);
  };
  const awayRect = (a: Away, top: number, h: number) => {
    const x1 = x(yearOf(a.from)), x2 = a.to ? x(yearOf(a.to)) : width - m.r;
    return <rect key={`${a.from}-${top}`} x={x1} y={top} width={Math.max(0, x2 - x1)} height={h} fill="url(#sp-away)" className="sp-away" />;
  };
  const decades = [1980, 1990, 2000, 2010];
  return (
    <div ref={ref} className="sp-gasoil" dir="ltr">
      <svg width={width} height={height} role="img" aria-label={aria} tabIndex={0} onPointerDown={scrub} onPointerMove={scrub} onKeyDown={key}>
        <defs>
          <pattern id="sp-away" width="7" height="7" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <line x1="0" y1="0" x2="0" y2="7" className="sp-away-line" />
          </pattern>
        </defs>
        {/* Dirhams a litre. */}
        <text x={m.l} y={p1.top - 8} className="sp-tick is-unit" textAnchor={rtl ? 'end' : 'start'} direction={rtl ? 'rtl' : 'ltr'}>{labels.dh}</text>
        {[0, 2, 4, 6, 8].map((v) => (
          <g key={`d${v}`}>
            <line x1={m.l} x2={width - m.r} y1={yDh(v)} y2={yDh(v)} className={v ? 'sp-rule' : 'sp-axis'} />
            <text x={m.l - 6} y={yDh(v) + 5} textAnchor="end" className="sp-tick">{v}</text>
          </g>
        ))}
        {away.map((a) => awayRect(a, p1.top, p1.h))}
        {/* The silence named where the line is not: the ministry's years over the line on both sides of their band (above
            6,40 DH, under the 2006 rise), the open stretch at the foot of the panel, ending at its edge. */}
        {away.map((a) => {
          const x1 = x(yearOf(a.from)), x2 = a.to ? x(yearOf(a.to)) : width - m.r;
          // In a right-to-left text the anchor «start» is its right side.
          return a.to ? (
            <text key={`l${a.from}`} x={(x1 + x2) / 2} y={yDh(6.4)} textAnchor="middle" className="sp-away-words" direction={rtl ? 'rtl' : 'ltr'}>{a.label}</text>
          ) : (
            <text key={`l${a.from}`} x={x2 - 2} y={p1.top + p1.h - 12} textAnchor={rtl ? 'start' : 'end'} className="sp-away-words" direction={rtl ? 'rtl' : 'ltr'}>{a.label}</text>
          );
        })}
        <path d={paths.dh} className="sp-gas" />
        {steps.map((s) => <circle key={s.from} cx={x(yearOf(s.from))} cy={yDh(s.dh)} r={3.2} className="sp-gas-dot" />)}
        {/* Minutes of work a litre. */}
        <text x={m.l} y={p2.top - 8} className="sp-tick is-unit" textAnchor={rtl ? 'end' : 'start'} direction={rtl ? 'rtl' : 'ltr'}>{labels.minutes}</text>
        {[0, 20, 40, 60].map((v) => (
          <g key={`m${v}`}>
            <line x1={m.l} x2={width - m.r} y1={yMin(v)} y2={yMin(v)} className={v === 0 ? 'sp-axis' : v === 60 ? 'sp-hour' : 'sp-rule'} />
            <text x={m.l - 6} y={yMin(v) + 5} textAnchor="end" className="sp-tick">{v}</text>
          </g>
        ))}
        <text x={width - m.r} y={yMin(60) - 6} textAnchor={rtl ? 'start' : 'end'} direction={rtl ? 'rtl' : 'ltr'} className="sp-tick is-strong">{labels.hour}</text>
        {away.map((a) => awayRect(a, p2.top, p2.h))}
        <path d={paths.min} className="sp-min" />
        {decades.map((d) => <text key={d} x={x(d)} y={height - 8} textAnchor="middle" className="sp-tick">{d}</text>)}
        {picked !== null ? (
          <line x1={x(picked)} x2={x(picked)} y1={p1.top - 4} y2={p2.top + p2.h} className="sp-cursor" />
        ) : null}
      </svg>
    </div>
  );
}
