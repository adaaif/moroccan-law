import { useEffect, useRef, useState } from 'react';
import { reducedMotion } from '@/shared/services/motion';
import { angle, DIAL_MAX, polar } from './dial';

/**
 * A speedometer, 0 to 140 km/h, always left to right: its ticks every 10, its numbers every 20; a violet dot on its rim
 * for every speed the Bulletin wrote in the post (what the texts printed); the needle on the picked era's speed, with the
 * speed large in its hub and the year under it. When it first comes into view the needle sweeps up from 0 (the post's one
 * motion that plays by itself); after that it moves when the reader picks another year (none with reduced motion).
 */
export function Dial({ kmh, others, year, unit, aria }: {
  kmh: number;
  others: number[];
  year: number;
  unit: string;
  aria: string;
}) {
  const box = useRef<HTMLDivElement>(null);
  const [awake, setAwake] = useState(() => reducedMotion());
  useEffect(() => {
    if (awake || !box.current) return;
    const io = new IntersectionObserver(([e]) => { if (e.isIntersecting) { setAwake(true); io.disconnect(); } }, { threshold: 0.4 });
    io.observe(box.current);
    return () => io.disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const W = 320, cx = 160, cy = 170, R = 140;
  const ticks = Array.from({ length: DIAL_MAX / 10 + 1 }, (_, i) => i * 10);
  const [ax, ay] = polar(cx, cy, R, -120);
  const [bx, by] = polar(cx, cy, R, 120);
  const shown = awake ? kmh : 0;
  return (
    <div ref={box} className="sp-dial" dir="ltr">
      <svg viewBox={`0 0 ${W} 250`} role="img" aria-label={aria}>
        <path d={`M${ax} ${ay} A${R} ${R} 0 1 1 ${bx} ${by}`} className="sp-arc" />
        {ticks.map((v) => {
          const [x1, y1] = polar(cx, cy, R - 4, angle(v));
          const [x2, y2] = polar(cx, cy, R - (v % 20 ? 14 : 22), angle(v));
          const [tx, ty] = polar(cx, cy, R - 40, angle(v));
          return (
            <g key={v}>
              <line x1={x1} y1={y1} x2={x2} y2={y2} className={v % 20 ? 'sp-tick' : 'sp-tick is-major'} />
              {v % 20 ? null : <text x={tx} y={ty + 5} textAnchor="middle" className="sp-num">{v}</text>}
            </g>
          );
        })}
        {others.map((v) => {
          const [x, y] = polar(cx, cy, R + 9, angle(v));
          return <circle key={v} cx={x} cy={y} r={v === kmh ? 6 : 4} className={v === kmh ? 'sp-mark is-on' : 'sp-mark'} />;
        })}
        <g className="sp-needle" style={{ transform: `rotate(${angle(shown)}deg)`, transformOrigin: `${cx}px ${cy}px` }}>
          <path d={`M${cx - 5} ${cy} L${cx} ${cy - R + 18} L${cx + 5} ${cy} Z`} />
        </g>
        <circle cx={cx} cy={cy} r={50} className="sp-hub" />
        <text x={cx} y={cy + 8} textAnchor="middle" className="sp-big">{kmh}</text>
        <text x={cx} y={cy + 32} textAnchor="middle" className="sp-unit">{unit}</text>
        <text x={cx} y={cy + 72} textAnchor="middle" className="sp-year">{year}</text>
      </svg>
    </div>
  );
}
