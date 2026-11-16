import { type KeyboardEvent, type PointerEvent, useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { reducedMotion } from '@/shared/services/motion';
import { useWidth } from '../viz';
import { type Price, type Segment, dirhams, yearOf } from './price';

/**
 * «ارسم الثمن»: the reader draws the price of a pack from 1960 to today with a finger, then the orders draw theirs over it,
 * step by step. Afterwards the same staircase turns into hours of work at the minimum wage (a morph, the one motion that
 * answers the switch); a tap names the order of a step. Drawn at its real width, left to right on an Arabic page too.
 */
export type Mode = 'dh' | 'h';
export const FIRST_GUESS = 1961, LAST_YEAR = 2026;

const X0 = 1955.4, X1 = 2027.2;
const ease = (p: number) => (p < 0.5 ? 4 * p ** 3 : 1 - (-2 * p + 2) ** 3 / 2);

export function Draw({ segs, steps, opening, guess, setGuess, revealed, mode, picked, onPick, aria }: {
  /** The staircase from the first price whose wage is known (1960), to today. */
  segs: Segment[];
  /** The orders, one dot each once revealed. */
  steps: Price[];
  /** The lone price before (1956), drawn as a dot. */
  opening: Price;
  guess: (number | null)[];
  setGuess: (g: (number | null)[]) => void;
  revealed: boolean;
  mode: Mode;
  picked: number | null;
  onPick: (i: number) => void;
  aria: string;
}) {
  const { t, i18n } = useTranslation('blog');
  const rtl = i18n.language !== 'fr';
  const [ref, width] = useWidth<HTMLDivElement>(640);
  const height = width < 520 ? 300 : 380;
  const m = { l: width < 520 ? 34 : 42, r: 14, t: 18, b: 30 };
  const W = width - m.l - m.r, H = height - m.t - m.b;
  const x = (yr: number) => m.l + ((yr - X0) / (X1 - X0)) * W;
  const yDh = (v: number) => m.t + H - (v / 35) * H;
  const yH = (v: number) => m.t + H - (v / 2.6) * H;
  // The morph between dirhams (0) and hours (1).
  const [k, setK] = useState(mode === 'h' ? 1 : 0);
  const raf = useRef(0);
  useEffect(() => {
    const target = mode === 'h' ? 1 : 0;
    if (reducedMotion()) { setK(target); return; }
    const from = k, start = performance.now();
    cancelAnimationFrame(raf.current);
    const step = (now: number) => {
      const p = Math.min(1, (now - start) / 900);
      setK(from + (target - from) * ease(p));
      if (p < 1) raf.current = requestAnimationFrame(step);
    };
    raf.current = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode]);
  const y = (s: Segment) => (1 - k) * yDh(s.dh ?? 0) + k * yH(s.hours ?? 0);

  // The staircase as paths: a run of steps, broken where the Bulletin printed no price; the break drawn dashed.
  const { known, rest, gaps, revealStart } = useMemo(() => {
    const runs: Segment[][] = [];
    let run: Segment[] = [];
    const breaks: [Segment, Segment][] = [];
    segs.forEach((s, i) => {
      if (s.dh === null || s.hours === null) { if (run.length) runs.push(run); run = []; return; }
      if (s.gap) {
        // The order's price stands alone; a dashed line leads to the next price the Bulletin printed.
        run.push({ ...s, to: s.from });
        runs.push(run); run = [];
        const next = segs.slice(i + 1).find((x2) => x2.dh !== null && x2.hours !== null);
        if (next) breaks.push([s, next]);
        return;
      }
      run.push(s);
    });
    if (run.length) runs.push(run);
    const path = (r: Segment[]) => r.map((s, i) => `${i ? 'L' : 'M'}${x(yearOf(s.from)).toFixed(1)} ${y(s).toFixed(1)}H${x(yearOf(s.to)).toFixed(1)}`).join('');
    const firstRun = runs[0] ?? [];
    const opened = firstRun.filter((s) => yearOf(s.from) < FIRST_GUESS);
    const later = [firstRun.filter((s) => yearOf(s.from) >= FIRST_GUESS), ...runs.slice(1)].filter((r) => r.length);
    const joins = breaks.map(([a, b]) => `M${x(yearOf(a.from)).toFixed(1)} ${y(a).toFixed(1)}L${x(yearOf(b.from)).toFixed(1)} ${y(b).toFixed(1)}`);
    // The reveal draws on from the end of what is shown.
    const glue = opened.length && later[0]?.length ? `M${x(yearOf(opened[opened.length - 1].to)).toFixed(1)} ${y(opened[opened.length - 1]).toFixed(1)}V${y(later[0][0]).toFixed(1)}` : '';
    return { known: path(opened), rest: glue + later.map(path).join(''), gaps: joins, revealStart: opened.length };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [segs, width, k]);

  // The reader's line: a point a year, from the 1960 price on.
  const startDh = segs.find((s) => s.dh !== null)?.dh ?? 1.4;
  const guessPath = useMemo(() => {
    let d = `M${x(1960.55).toFixed(1)} ${yDh(startDh).toFixed(1)}`;
    let prev = 1960;
    guess.forEach((g, i) => {
      if (g === null) return;
      const yr = FIRST_GUESS + i;
      d += `${yr === prev + 1 ? 'L' : 'M'}${x(yr + 0.5).toFixed(1)} ${yDh(g).toFixed(1)}`;
      prev = yr;
    });
    return d;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [guess, width, startDh]);
  const last = guess.reduce<number>((a, g, i) => (g !== null ? FIRST_GUESS + i : a), 1960);

  const drawing = useRef<{ yr: number; v: number } | null>(null);
  const put = (e: PointerEvent<SVGRectElement>) => {
    const box = (e.currentTarget.ownerSVGElement as SVGSVGElement).getBoundingClientRect();
    const px = e.clientX - box.left, py = e.clientY - box.top;
    const yr = Math.max(FIRST_GUESS, Math.min(LAST_YEAR, Math.round(X0 + ((px - m.l) / W) * (X1 - X0) - 0.5)));
    const v = Math.max(0, Math.min(35, ((m.t + H - py) / H) * 35));
    const next = [...guess];
    const from = drawing.current ?? { yr: last >= FIRST_GUESS ? last : 1960, v: last >= FIRST_GUESS ? guess[last - FIRST_GUESS]! : startDh };
    // Fill the years the finger jumped over, in a straight line, so a quick stroke leaves no holes.
    const lo = Math.min(from.yr, yr), hi = Math.max(from.yr, yr);
    for (let a = lo; a <= hi; a += 1) {
      if (a < FIRST_GUESS) continue;
      const share = hi === lo ? 1 : (a - from.yr) / (yr - from.yr);
      next[a - FIRST_GUESS] = Math.round((from.v + (v - from.v) * share) * 100) / 100;
    }
    drawing.current = { yr, v };
    setGuess(next);
  };

  // A tap on the staircase, once revealed: the nearest order.
  const near = (e: PointerEvent<SVGSVGElement>) => {
    if (!revealed) return;
    const box = e.currentTarget.getBoundingClientRect();
    const yr = X0 + ((e.clientX - box.left - m.l) / W) * (X1 - X0);
    let best = 0;
    steps.forEach((s, i) => { if (Math.abs(yearOf(s.date) - yr) < Math.abs(yearOf(steps[best].date) - yr)) best = i; });
    onPick(best);
  };
  const key = (e: KeyboardEvent<SVGSVGElement>) => {
    if (!revealed) return;
    const d = e.key === 'ArrowRight' ? 1 : e.key === 'ArrowLeft' ? -1 : 0;
    if (!d) return;
    e.preventDefault();
    onPick(Math.max(0, Math.min(steps.length - 1, (picked ?? (d > 0 ? -1 : steps.length)) + d)));
  };
  const stepY = (p: Price) => {
    const s = segs.find((x2) => x2.from === p.date);
    return s ? y(s) : yDh(dirhams(p));
  };

  const ticksY = (1 - k) > 0.5 ? [0, 10, 20, 30].map((v) => ({ v, y: yDh(v), label: `${v}` })) : [0, 1, 2].map((v) => ({ v, y: yH(v), label: `${v}` }));
  const unit = (1 - k) > 0.5 ? t('marquise.draw.unitDh') : t('marquise.draw.unitH');
  const ref144 = yH(31 / 17.92);
  // A rough line length for the reveal's stroke.
  const restRef = useRef<SVGPathElement>(null);
  const [len, setLen] = useState(4000);
  useEffect(() => { if (restRef.current) setLen(Math.ceil(restRef.current.getTotalLength())); }, [rest, revealed]);

  return (
    <div ref={ref} className="mq-draw" dir="ltr">
      {/* While the reader draws, a finger on the chart draws instead of scrolling the page (it scrolls again after). */}
      <svg width={width} height={height} role="img" aria-label={aria} tabIndex={revealed ? 0 : -1} onPointerDown={near} onKeyDown={key}
           style={{ touchAction: revealed ? 'pan-y' : 'none' }}>
        <defs>
          <pattern id="mq-zone" width="8" height="8" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <line x1="0" y1="0" x2="0" y2="8" className="mq-zone-line" />
          </pattern>
        </defs>
        {ticksY.map((tk) => (
          <g key={tk.v}>
            <line x1={m.l} x2={width - m.r} y1={tk.y} y2={tk.y} className={tk.v === 0 ? 'mq-axis' : 'mq-rule'} />
            <text x={m.l - 6} y={tk.y + 5} textAnchor="end" className="mq-tick">{tk.label}</text>
          </g>
        ))}
        <text x={m.l} y={m.t - 4} className="mq-tick is-unit" direction={rtl ? 'rtl' : 'ltr'} textAnchor={rtl ? 'end' : 'start'} dx={rtl ? 0 : 0}>{unit}</text>
        {[1960, 1980, 2000, 2020].map((yr) => <text key={yr} x={x(yr)} y={height - 8} textAnchor="middle" className="mq-tick">{yr}</text>)}
        {!revealed ? (
          <g className="mq-zone">
            <rect x={x(1960.6)} y={m.t} width={x(X1) - x(1960.6)} height={H} fill="url(#mq-zone)" />
            {last < 1968 ? <text x={(x(1961) + x(X1)) / 2} y={m.t + H / 2} textAnchor="middle" className="mq-zone-words" direction={rtl ? 'rtl' : 'ltr'}>{t('marquise.draw.here')}</text> : null}
          </g>
        ) : null}
        {/* What the orders printed before the reader draws: 1956's dot and 1960's step. */}
        <circle cx={x(yearOf(opening.date))} cy={(1 - k) * yDh(dirhams(opening)) + k * yH(dirhams(opening) / 0.808)} r={4} className="mq-price-dot" opacity={1 - k} />
        <path d={known} className="mq-price" />
        {revealed ? (
          <>
            {gaps.map((d, i) => <path key={i} d={d} className="mq-gap" />)}
            <path ref={restRef} d={rest} className="mq-price is-rest" style={{ strokeDasharray: len, strokeDashoffset: 0, ['--len' as string]: len }} />
            {k > 0.5 ? (
              <g className="mq-ref">
                <line x1={m.l} x2={width - m.r} y1={ref144} y2={ref144} />
                <text x={width - m.r} y={ref144 - 9} textAnchor={rtl ? 'start' : 'end'} direction={rtl ? 'rtl' : 'ltr'} className="mq-tick is-strong">{t('marquise.draw.ref144')}</text>
              </g>
            ) : null}
            {steps.map((s, i) => (i < revealStart ? null : (
              <circle key={s.date} cx={x(yearOf(s.date))} cy={stepY(s)} r={i === picked ? 6 : 3.4} className={`mq-step${i === picked ? ' is-picked' : ''}`} />
            )))}
          </>
        ) : null}
        <path d={guessPath} className={`mq-guess${revealed ? ' is-done' : ''}`} style={{ opacity: (revealed ? 0.7 : 1) * (1 - k) }} />
        <circle cx={x(1960.55)} cy={yDh(startDh)} r={6} className={`mq-start${!revealed && last === 1960 ? ' is-calling' : ''}`} style={{ opacity: 1 - k }} />
        {!revealed ? (
          <rect x={x(1960.6)} y={m.t - 6} width={x(X1) - x(1960.6)} height={H + 12} className="mq-pad"
                onPointerDown={(e) => { e.currentTarget.setPointerCapture(e.pointerId); drawing.current = null; put(e); }}
                onPointerMove={(e) => { if (e.buttons || e.pointerType !== 'mouse') put(e); }}
                onPointerUp={() => { drawing.current = null; }} />
        ) : null}
      </svg>
    </div>
  );
}
