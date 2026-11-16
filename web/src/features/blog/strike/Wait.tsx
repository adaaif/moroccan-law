import { useEffect, useRef, useState } from 'react';
import { reducedMotion } from '@/shared/services/motion';
import { useWidth } from '../viz';
import { yearOf } from './wait';

/**
 * Sixty-two years on one line, left to right on every page: from the Bulletin that printed «حق الإضراب مضمون» in 1962 to
 * the one that printed the law in 2025. Each constitution that said it again is a ring on the line; the eight years the
 * bill lay in the House are a band; the law is the violet dot at the end. Once in view the line draws itself, the year
 * and the count of years running at its head (the post's one motion that plays by itself; none with reduced motion).
 */
export function Wait({ from, to, rings, band, labels, aria, rtl }: {
  from: string;
  to: string;
  rings: { year: number; date: string }[];
  band: [string, string];
  labels: { band: string; years: (n: number) => string; law: string };
  aria: string;
  rtl: boolean;
}) {
  const [ref, width] = useWidth<HTMLDivElement>(640);
  const box = useRef<HTMLDivElement>(null);
  const [p, setP] = useState(() => (reducedMotion() ? 1 : 0));
  useEffect(() => {
    if (p === 1 || !box.current) return;
    let raf = 0;
    const io = new IntersectionObserver(([e]) => {
      if (!e.isIntersecting) return;
      io.disconnect();
      const start = performance.now(), dur = 2400;
      const step = (now: number) => {
        const k = Math.min(1, (now - start) / dur);
        setP(1 - Math.pow(1 - k, 3));
        if (k < 1) raf = requestAnimationFrame(step);
      };
      raf = requestAnimationFrame(step);
    }, { threshold: 0.5 });
    io.observe(box.current);
    return () => { io.disconnect(); cancelAnimationFrame(raf); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const phone = width < 560;
  const m = { l: 18, r: 18 };
  const X0 = 1960, X1 = 2027;
  const x = (yr: number) => m.l + ((yr - X0) / (X1 - X0)) * (width - m.l - m.r);
  const y = phone ? 118 : 132, height = y + 84;
  const a = yearOf(from), b = yearOf(to);
  const head = a + (b - a) * p;
  const elapsed = Math.floor(head - a + 1e-9);
  const [b0, b1] = [yearOf(band[0]), yearOf(band[1])];
  const lifted: boolean[] = [];
  rings.forEach((r, i) => { lifted.push(i > 0 && !lifted[i - 1] && x(yearOf(r.date)) - x(yearOf(rings[i - 1].date)) < 40); });
  // Words under the line end at the chart's end edge: in a right-to-left text the anchor «start» is its right side.
  const endAnchor = rtl ? 'start' : 'end';
  return (
    <div ref={(el) => { ref(el); box.current = el; }} className="st-wait" dir="ltr">
      <svg width={width} height={height} role="img" aria-label={aria}>
        <line x1={x(X0)} x2={x(X1)} y1={y} y2={y} className="st-rail" />
        {[1970, 1980, 1990, 2000, 2010, 2020].map((d) => (
          <g key={d}>
            <line x1={x(d)} x2={x(d)} y1={y - 4} y2={y + 4} className="st-tick" />
            <text x={x(d)} y={y + 26} textAnchor="middle" className="st-axis">{d}</text>
          </g>
        ))}
        {/* The bill in the House, under the line, once the line has reached it. */}
        {head >= b0 ? (
          <g className="st-band">
            <rect x={x(b0)} y={y - 9} width={Math.max(0, x(Math.min(head, b1)) - x(b0))} height={18} rx={3} />
            {head >= b1 ? <text x={width - m.r} y={y + 50} textAnchor={endAnchor} direction={rtl ? 'rtl' : 'ltr'} className="st-band-words">{labels.band}</text> : null}
          </g>
        ) : null}
        <line x1={x(a)} x2={x(head)} y1={y} y2={y} className="st-waited" />
        {rings.map((r, i) => {
          // A year that stands too close to the one before it climbs a line, unless that one already climbed (1970, 1972).
          const close = lifted[i];
          return yearOf(r.date) <= head + 0.01 ? (
            <g key={r.year} className="st-ring">
              {close ? <line x1={x(yearOf(r.date))} x2={x(yearOf(r.date))} y1={y - 8} y2={y - 26} className="st-tick" /> : null}
              <circle cx={x(yearOf(r.date))} cy={y} r={phone ? 6 : 7} />
              <text x={x(yearOf(r.date))} y={y - (close ? 32 : 16)} textAnchor="middle">{r.year}</text>
            </g>
          ) : null;
        })}
        {p >= 1 ? (
          <g className="st-law">
            <circle cx={x(b)} cy={y} r={phone ? 8 : 9} />
            <text x={width - m.r} y={y + 72} textAnchor={endAnchor} direction={rtl ? 'rtl' : 'ltr'}>{labels.law}</text>
          </g>
        ) : null}
        {/* The head: the year it has reached and the years waited. */}
        <g className="st-head" transform={`translate(${Math.min(Math.max(x(head), 70), width - 70)} 0)`}>
          <text x={0} y={phone ? 52 : 60} textAnchor="middle" className="st-count">{elapsed}</text>
          <text x={0} y={phone ? 76 : 86} textAnchor="middle" className="st-count-words" direction={rtl ? 'rtl' : 'ltr'}>{labels.years(elapsed)}</text>
        </g>
        <line x1={x(head)} x2={x(head)} y1={phone ? 84 : 94} y2={y - 2} className="st-head-line" />
      </svg>
    </div>
  );
}
