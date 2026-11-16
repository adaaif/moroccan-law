import { type KeyboardEvent, useEffect, useRef, useState } from 'react';
import { reducedMotion } from '@/shared/services/motion';
import { useWidth } from '../viz';

/**
 * Who made the texts of the law's rank, year by year from 1963, left to right on every page: the laws Parliament voted
 * in violet; the King's dahirs and royal decrees «بمثابة قانون» in ink (the decrees lighter); the government's decree-laws
 * grey. The years when the King's texts outnumber the voted laws stand on a pale band (named in the legend, its long runs
 * dated over it, one above the other). The thinnest and fullest years of
 * voted laws are named over their bars. Once in view the years rise one after another (the post's one motion that plays
 * by itself; none with reduced motion). A tap, or the arrow keys, picks a year.
 */
export type Year = { year: number; voted: number; dfl: number; rdl: number; dlaw: number };
const PARTS = ['voted', 'dfl', 'rdl', 'dlaw'] as const;

export function Hands({ years, bands, marks, picked, onPick, aria }: {
  years: Year[];
  bands: [number, number][];
  marks: number[];
  picked: number;
  onPick: (y: number) => void;
  aria: string;
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
      const start = performance.now(), dur = 1800;
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
  const m = { l: 30, r: 8, t: 48, b: 30 };
  const H = phone ? 230 : 280;
  const top = Math.max(...years.map((y) => y.voted + y.dfl + y.rdl + y.dlaw));
  const ceil = Math.ceil(top / 50) * 50;
  const step = (width - m.l - m.r) / years.length;
  const x = (i: number) => m.l + i * step;
  const y = (v: number) => H - m.b - (v / ceil) * (H - m.t - m.b);
  const at = (yr: number) => years.findIndex((d) => d.year === yr);
  const keys = (e: KeyboardEvent) => {
    const by = e.key === 'ArrowRight' ? 1 : e.key === 'ArrowLeft' ? -1 : 0;
    if (!by) return;
    e.preventDefault();
    const i = Math.min(years.length - 1, Math.max(0, at(picked) + by));
    onPick(years[i].year);
  };
  const pickAt = (clientX: number, el: SVGSVGElement) => {
    const r = el.getBoundingClientRect();
    const i = Math.min(years.length - 1, Math.max(0, Math.floor((clientX - r.left - m.l) / step)));
    onPick(years[i].year);
  };
  return (
    <div ref={(el) => { ref(el); box.current = el; }} className="pl-hands" dir="ltr">
      <svg width={width} height={H} role="slider" tabIndex={0} aria-label={aria} aria-valuemin={years[0].year}
           aria-valuemax={years[years.length - 1].year} aria-valuenow={picked} onKeyDown={keys}
           onPointerDown={(e) => pickAt(e.clientX, e.currentTarget)}>
        {/* The long bands' names, one above the other when two stand close (1965–1970, 1972–1977). */}
        {bands.map(([a, b]) => (
          <g key={a} className="pl-band">
            <rect x={x(at(a))} y={m.t - 40} width={x(at(b)) + step - x(at(a))} height={H - m.t - m.b + 40} />
            {b - a >= 3 ? <text x={x(at(a)) + 3} y={m.t - (bands.filter(([c, d]) => d - c >= 3).findIndex(([c]) => c === a) % 2 ? 26 : 8)} textAnchor="start">{`${a}–${b}`}</text> : null}
          </g>
        ))}
        {Array.from({ length: ceil / 50 + 1 }, (_, k) => k * 50).map((g) => (
          <g key={g}>
            <line x1={m.l} x2={width - m.r} y1={y(g)} y2={y(g)} className="pl-grid" />
            <text x={m.l - 6} y={y(g) + 5} textAnchor="end" className="pl-axis">{g}</text>
          </g>
        ))}
        {years.slice(0, shown).map((d, i) => {
          let base = 0;
          return (
            <g key={d.year} className={picked === d.year ? 'is-on' : ''}>
              {PARTS.map((p) => {
                const v = d[p];
                if (!v) return null;
                const r = <rect key={p} x={x(i) + 0.5} y={y(base + v)} width={Math.max(1, step - 1.2)} height={y(base) - y(base + v)} className={`pl-${p}`} />;
                base += v;
                return r;
              })}
              {marks.includes(d.year) ? <text x={x(i) + step / 2} y={y(base) - 6} textAnchor="middle" className="pl-mark">{d.voted}</text> : null}
            </g>
          );
        })}
        {picked ? <line x1={x(at(picked)) + step / 2} x2={x(at(picked)) + step / 2} y1={m.t - 4} y2={H - m.b} className="pl-pick" /> : null}
        {[1963, 1980, 2000, 2026].filter((yr) => !phone || yr !== 1980).map((yr) => (
          <text key={yr} x={x(at(yr)) + step / 2} y={H - 8} textAnchor={yr === 2026 ? 'end' : yr === 1963 ? 'start' : 'middle'} className="pl-axis">{yr}</text>
        ))}
      </svg>
    </div>
  );
}
