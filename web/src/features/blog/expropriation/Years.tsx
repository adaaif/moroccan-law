import { type KeyboardEvent, useEffect, useRef, useState } from 'react';
import { reducedMotion } from '@/shared/services/motion';
import { useWidth } from '../viz';
import { total, type Year } from './sums';

/**
 * The declarations of public utility that expropriate, year by year, left to right on every page: the part for water in
 * blue at the foot of each bar, everything else above it in grey; the years since 2020 a shade darker. Once in view the
 * bars rise one after another (the post's one motion that plays by itself; none with reduced motion). A tap, or the
 * arrow keys, picks a year.
 */
export function Years({ years, picked, onPick, aria, ticks }: {
  years: Year[];
  picked: number;
  onPick: (y: number) => void;
  aria: string;
  ticks: number[];
}) {
  const [ref, width] = useWidth<HTMLDivElement>(640);
  const box = useRef<HTMLDivElement>(null);
  const [shown, setShown] = useState(() => (reducedMotion() ? years.length : 0));
  useEffect(() => {
    if (shown >= years.length || !box.current) return;
    let raf = 0;
    const io = new IntersectionObserver(([e]) => {
      if (!e.isIntersecting) return;
      io.disconnect();
      const start = performance.now(), dur = 1600;
      const tick = (now: number) => {
        const k = Math.min(1, (now - start) / dur);
        setShown(Math.round(k * years.length));
        if (k < 1) raf = requestAnimationFrame(tick);
      };
      raf = requestAnimationFrame(tick);
    }, { threshold: 0.3 });
    io.observe(box.current);
    return () => { io.disconnect(); cancelAnimationFrame(raf); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const phone = width < 560;
  const m = { l: 32, r: 6, t: 14, b: 30 };
  const H = phone ? 220 : 260;
  const top = Math.max(...years.map(total));
  const ceil = Math.ceil(top / 50) * 50;
  const step = (width - m.l - m.r) / years.length;
  const x = (i: number) => m.l + i * step;
  const y = (v: number) => H - m.b - (v / ceil) * (H - m.t - m.b);
  const at = (yr: number) => years.findIndex((d) => d.year === yr);
  const keys = (e: KeyboardEvent) => {
    const by = e.key === 'ArrowRight' ? 1 : e.key === 'ArrowLeft' ? -1 : 0;
    if (!by) return;
    e.preventDefault();
    onPick(years[Math.min(years.length - 1, Math.max(0, at(picked) + by))].year);
  };
  return (
    <div ref={(el) => { ref(el); box.current = el; }} className="ex-years" dir="ltr">
      <svg width={width} height={H} role="slider" tabIndex={0} aria-label={aria} aria-valuemin={years[0].year} aria-valuemax={years[years.length - 1].year}
           aria-valuenow={picked} onKeyDown={keys}
           onPointerDown={(e) => { const r = e.currentTarget.getBoundingClientRect(); onPick(years[Math.min(years.length - 1, Math.max(0, Math.floor((e.clientX - r.left - m.l) / step)))].year); }}>
        {Array.from({ length: ceil / 50 + 1 }, (_, k) => k * 50).map((g) => (
          <g key={g}>
            <line x1={m.l} x2={width - m.r} y1={y(g)} y2={y(g)} className="ex-grid" />
            <text x={m.l - 6} y={y(g) + 5} textAnchor="end" className="ex-axis">{g}</text>
          </g>
        ))}
        {years.slice(0, shown).map((d, i) => {
          const all = total(d), water = d.water ?? 0;
          return (
            <g key={d.year} className={`${d.year >= 2020 ? 'is-now' : ''}${picked === d.year ? ' is-on' : ''}`}>
              <rect x={x(i) + 0.4} y={y(all)} width={Math.max(1, step - 0.8)} height={y(water) - y(all)} className="ex-rest" />
              <rect x={x(i) + 0.4} y={y(water)} width={Math.max(1, step - 0.8)} height={y(0) - y(water)} className="ex-water" />
            </g>
          );
        })}
        <line x1={x(at(picked)) + step / 2} x2={x(at(picked)) + step / 2} y1={m.t} y2={H - m.b} className="ex-pick" />
        {ticks.map((yr) => (
          <text key={yr} x={x(at(yr)) + step / 2} y={H - 8} textAnchor={at(yr) === 0 ? 'start' : at(yr) === years.length - 1 ? 'end' : 'middle'} className="ex-axis">{yr}</text>
        ))}
      </svg>
    </div>
  );
}
