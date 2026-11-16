import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { reducedMotion } from '@/shared/services/motion';
import { n, useWidth } from '../viz';

/**
 * What reached the Mediator by fax and by WhatsApp, year by year, left to right on every page: the fax in ink, WhatsApp in
 * green from the year it opened, each named where its line ends, the year WhatsApp passed the fax marked. Once in view
 * both lines draw themselves (the post's one motion that plays by itself; none with reduced motion). A tap on a year
 * names its counts.
 */
export type Year = { year: number; fax: number; whatsapp?: number };

export function Mediator({ years, picked, onPick, passed, labels, aria }: {
  years: Year[];
  picked: number;
  onPick: (y: number) => void;
  passed: number | null;
  labels: { fax: string; whatsapp: string; passed: string };
  aria: string;
}) {
  const { i18n } = useTranslation('blog');
  const lang = i18n.language;
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
  const rtl = lang !== 'fr';
  const m = { l: 30, r: phone ? 112 : 124, t: 30, b: 40 };
  const H = phone ? 250 : 290;
  const top = Math.max(...years.map((y) => Math.max(y.fax, y.whatsapp ?? 0)));
  const ceil = Math.ceil(top / 50) * 50;
  const x = (i: number) => m.l + (i / (years.length - 1)) * (width - m.l - m.r);
  const y = (v: number) => H - m.b - (v / ceil) * (H - m.t - m.b);
  const line = (vals: (number | undefined)[]) =>
    vals.map((v, i) => (v === undefined ? null : `${x(i)},${y(v)}`)).filter(Boolean).join(' ');
  const fax = line(years.map((d) => d.fax));
  const wa = line(years.map((d) => d.whatsapp));
  const last = years.length - 1;
  const at = years.findIndex((d) => d.year === passed);
  const grid = Array.from({ length: ceil / 50 + 1 }, (_, i) => i * 50);
  return (
    <div ref={(el) => { ref(el); box.current = el; }} className={`wa-med${drawn ? ' is-drawn' : ''}`} dir="ltr">
      <svg width={width} height={H} role="img" aria-label={aria}>
        {grid.map((g) => (
          <g key={g}>
            <line x1={m.l} x2={width - m.r} y1={y(g)} y2={y(g)} className="wa-med-grid" />
            <text x={m.l - 8} y={y(g) + 5} textAnchor="end" className="wa-med-axis">{g}</text>
          </g>
        ))}
        {passed !== null && at >= 0 ? (
          <g className="wa-med-pass">
            <line x1={x(at)} x2={x(at)} y1={m.t - 6} y2={H - m.b} />
            <text x={x(at)} y={m.t - 12} textAnchor="middle" direction={rtl ? 'rtl' : 'ltr'}>{labels.passed}</text>
          </g>
        ) : null}
        <polyline points={fax} pathLength={1} className="wa-med-line is-fax" />
        <polyline points={wa} pathLength={1} className="wa-med-line is-wa" />
        {years.map((d, i) => (
          <g key={d.year} className={`wa-med-year${picked === d.year ? ' is-on' : ''}`} onPointerDown={() => onPick(d.year)}>
            <rect x={x(i) - 22} y={m.t - 4} width={44} height={H - m.t - m.b + 34} className="wa-med-hit" />
            <circle cx={x(i)} cy={y(d.fax)} r={picked === d.year ? 5.5 : 4} className="is-fax" />
            {d.whatsapp !== undefined ? <circle cx={x(i)} cy={y(d.whatsapp)} r={picked === d.year ? 5.5 : 4} className="is-wa" /> : null}
            <text x={x(i)} y={H - m.b + 24} textAnchor="middle" className="wa-med-axis">{d.year}</text>
          </g>
        ))}
        {/* Each line named where it ends, with its last count; its left edge at the line's end on both pages (in a
            right-to-left text the anchor «end» is its left side). */}
        {([['fax', years[last].fax], ['whatsapp', years[last].whatsapp]] as const).map(([k, v]) => (v === undefined ? null : (
          <text key={k} x={x(last) + 12} y={y(v) + 5} className={`wa-med-name ${k === 'fax' ? 'is-fax' : 'is-wa'}`}
                direction={rtl ? 'rtl' : 'ltr'} textAnchor={rtl ? 'end' : 'start'}>{`${labels[k]} ${n(v, lang)}`}</text>
        )))}
      </svg>
    </div>
  );
}
