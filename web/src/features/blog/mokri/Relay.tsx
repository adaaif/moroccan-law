import { type KeyboardEvent, useEffect, useRef, useState } from 'react';
import { reducedMotion } from '@/shared/services/motion';
import { useWidth } from '../viz';
import { runs, texts, type Year } from './runs';

/**
 * Forty-three years left to right on every page: a bar a year, the texts that carry the Grand Vizier's name; under them one
 * violet band for the name, the whole length; under it the Residents General, a band each for the years they are the one
 * named, in turn light and dark, named over two rows (three on a phone). Once in view the violet band draws from left to right (the post's
 * one motion that plays by itself; none with reduced motion). A tap, or the arrow keys, picks a year.
 */
export function Relay({ years, picked, onPick, names, nameLabel, aria }: {
  years: Year[];
  picked: number;
  onPick: (y: number) => void;
  names: Record<string, string>;
  nameLabel: string;
  aria: string;
}) {
  const [ref, width] = useWidth<HTMLDivElement>(640);
  const box = useRef<HTMLDivElement>(null);
  const [drawn, setDrawn] = useState(() => reducedMotion());
  useEffect(() => {
    if (drawn || !box.current) return;
    const io = new IntersectionObserver(([e]) => { if (e.isIntersecting) { setDrawn(true); io.disconnect(); } }, { threshold: 0.4 });
    io.observe(box.current);
    return () => io.disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const phone = width < 560;
  const m = { l: 40, r: 8, t: 12 };
  const rows = phone ? 3 : 2;
  const barsH = phone ? 120 : 150;
  const base = m.t + barsH;
  const nameY = base + 10, nameH = 26;
  const resY = nameY + nameH + 6;
  const H = resY + 66 + rows * 18;
  const step = (width - m.l - m.r) / years.length;
  const x = (i: number) => m.l + i * step;
  const top = Math.max(...years.map(texts));
  const ceil = Math.ceil(top / 200) * 200;
  const y = (v: number) => base - (v / ceil) * barsH;
  const at = (yr: number) => years.findIndex((d) => d.year === yr);
  const keys = (e: KeyboardEvent) => {
    const by = e.key === 'ArrowRight' ? 1 : e.key === 'ArrowLeft' ? -1 : 0;
    if (!by) return;
    e.preventDefault();
    onPick(years[Math.min(years.length - 1, Math.max(0, at(picked) + by))].year);
  };
  const firstYear = years.find((d) => texts(d) > 0)!.year, lastYear = [...years].reverse().find((d) => texts(d) > 0 && d.year < 1956)!.year;
  return (
    <div ref={(el) => { ref(el); box.current = el; }} className={`mk-relay${drawn ? ' is-drawn' : ''}`} dir="ltr">
      <svg width={width} height={H} role="slider" tabIndex={0} aria-label={aria} aria-valuemin={years[0].year} aria-valuemax={years[years.length - 1].year}
           aria-valuenow={picked} onKeyDown={keys}
           onPointerDown={(e) => { const r = e.currentTarget.getBoundingClientRect(); onPick(years[Math.min(years.length - 1, Math.max(0, Math.floor((e.clientX - r.left - m.l) / step)))].year); }}>
        {[0, ceil / 2, ceil].map((g) => (
          <g key={g}>
            <line x1={m.l} x2={width - m.r} y1={y(g)} y2={y(g)} className="mk-grid" />
            <text x={m.l - 6} y={y(g) + 5} textAnchor="end" className="mk-axis">{g}</text>
          </g>
        ))}
        {years.map((d, i) => (
          <rect key={d.year} x={x(i) + 0.5} y={y(texts(d))} width={Math.max(1, step - 1)} height={base - y(texts(d))} className={picked === d.year ? 'mk-bar is-on' : 'mk-bar'} />
        ))}
        {/* The name, the whole length, drawn once. */}
        <rect x={x(at(firstYear))} y={nameY} width={x(at(lastYear)) + step - x(at(firstYear))} height={nameH} rx={4} className="mk-name" />
        <text x={x(at(firstYear)) + 8} y={nameY + 18} className="mk-name-words">{nameLabel}</text>
        {runs(years).map(([key, a, b], k) => (
          <g key={`${key}-${a}`} className={k % 2 ? 'mk-res is-dark' : 'mk-res'}>
            <rect x={x(at(a))} y={resY} width={x(at(b)) + step - x(at(a))} height={12} />
            <text x={x(at(a)) + (x(at(b)) + step - x(at(a))) / 2} y={resY + 30 + (k % rows) * 18} textAnchor="middle">{names[key]}</text>
          </g>
        ))}
        <line x1={x(at(picked)) + step / 2} x2={x(at(picked)) + step / 2} y1={m.t} y2={resY + 12} className="mk-pick" />
        {[years[0].year, 1925, 1935, 1945, 1955].map((yr) => (
          <text key={yr} x={x(at(yr)) + step / 2} y={H - 4} textAnchor={yr === years[0].year ? 'start' : yr === 1955 ? 'end' : 'middle'} className="mk-axis">{yr}</text>
        ))}
      </svg>
    </div>
  );
}
