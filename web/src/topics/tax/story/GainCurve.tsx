import { useMemo, useState } from 'react';
import { useToolState } from '../../kit/tool/state';
import { INK, num, scale, ticks, useWidth } from '../../kit/viz/viz';
import { curvePoints, exemptUpTo, useBillYears, type CurvePoint } from '../billYears';
import { useTaxT } from '../strings';
import './story.css';

const X0 = 3000, X1 = 30000;
const snap = (g: number) => Math.min(X1, Math.max(X0, Math.round(g / 250) * 250));

/** «شحال غادي يربح الأجير فالشهر، حسب أجرتو» (the bill-story review, Y1, Y5, Y14): the monthly gain at every
 *  gross salary, 2027 and 2031 only (two lines, labelled where they end), drawn at its real width in the page's direction;
 *  the stretch the bill frees from tax shaded and said; the reader a dot they drag, or tap anywhere, or move with the
 *  arrows; under it one sentence with their figures and, a tap away, the numbers as a table. `range` lights the stretch a
 *  story step speaks of. */
export function GainCurve({ slug, range }: { slug: string; range?: [number, number] | null }) {
  const { t, i18n } = useTaxT();
  const lang = i18n.language === 'fr' ? 'fr' : 'ar';
  // The salary grows to the right, in Arabic too: charts read left to right (the chart rule of 1 Nov 2026).
  const rtl = false;
  const [s, set] = useToolState({ g: '10000', k: '0' });
  const kids = Number(s.k) || 0;
  const you = snap(Number(s.g) || 10000);
  const b = useBillYears(slug, you, kids);
  const [ref, width] = useWidth<HTMLDivElement>(640);
  const [table, setTable] = useState(false);
  const points = useMemo(() => (b ? curvePoints(b, kids) : []), [b, kids]);
  const free = useMemo(() => (b ? exemptUpTo(kids, b.rules('2027')).gross : 0), [b, kids]);
  if (!b || !points.length || width < 200) return <div ref={ref} id="st-curve" className="st-curve st-wait" />;

  const phone = width < 560;
  const h = phone ? 300 : 380;
  const m = { t: 34, b: 44, side: phone ? 46 : 64, end: phone ? 14 : 26 };
  const top = Math.max(1000, ...points.map((p) => p.gains['2031'])) * 1.12;
  const x = rtl ? scale(X0, X1, width - m.side, m.end) : scale(X0, X1, m.side, width - m.end);
  const y = scale(0, top, h - m.b, m.t);
  const path = (year: string) => points.map((p, i) => `${i ? 'L' : 'M'}${x(p.g).toFixed(1)},${y(p.gains[year]).toFixed(1)}`).join('');
  const at = points.find((p) => p.g === you) ?? points[0];
  const ends = points[points.length - 1];
  const plateau = Math.max(...points.map((p) => p.gains['2027']));
  const gx = phone ? [5000, 15000, 25000] : [5000, 10000, 15000, 20000, 25000, 30000];
  // In a right-to-left SVG «start» is a text's right edge: a label that grows to the left ends at x («toLeft»).
  const toLeft = rtl ? 'start' : 'end', toRight = rtl ? 'end' : 'start';
  const pick = (clientX: number, svg: SVGSVGElement) => {
    const r = svg.getBoundingClientRect();
    const px = clientX - r.left;
    const g = rtl ? X0 + ((width - m.side - px) / (width - m.side - m.end)) * (X1 - X0) : X0 + ((px - m.side) / (width - m.side - m.end)) * (X1 - X0);
    set({ g: String(snap(g)) });
  };
  const sentence = at.now === 0
    ? t('story.readNone', { g: num(you, lang) })
    : t(kids ? 'story.readKids' : 'story.read', { g: num(you, lang), count: kids, a: num(at.gains['2027'], lang), b: num(at.gains['2031'], lang) });

  return (
    <figure id="st-curve" className="st-curve" ref={ref}>
      <svg style={{ direction: 'ltr' }} width={width} height={h} role="img" aria-label={t('story.curveAria')} className="st-svg"
           onPointerDown={(e) => { (e.currentTarget as SVGSVGElement).setPointerCapture(e.pointerId); pick(e.clientX, e.currentTarget); }}
           onPointerMove={(e) => { if (e.buttons) pick(e.clientX, e.currentTarget); }}>
        {/* Where the bill takes the whole tax away (for these dependents). */}
        {free > X0 ? <rect x={Math.min(x(X0), x(free))} y={m.t} width={Math.abs(x(free) - x(X0))} height={h - m.t - m.b} fill="var(--t)" opacity={0.08} /> : null}
        {range ? <rect x={Math.min(x(range[0]), x(range[1]))} y={m.t} width={Math.abs(x(range[1]) - x(range[0]))} height={h - m.t - m.b} fill="var(--t)" opacity={0.14} /> : null}
        {ticks(top, phone ? 3 : 4).map((v) => (
          <g key={v}>
            <line x1={m.end} x2={width - m.end} y1={y(v)} y2={y(v)} stroke={INK.grid} />
            <text x={rtl ? width - 4 : m.side - 8} y={y(v) + 5} textAnchor={toLeft} className="st-tick">{num(v, lang)}</text>
          </g>
        ))}
        {gx.map((g) => <text key={g} x={x(g)} y={h - m.b + 22} textAnchor="middle" className="st-tick">{num(g, lang)}</text>)}
        <text x={rtl ? width - m.side : m.side} y={h - 6} textAnchor="start" className="st-axis">{t('story.axisX')}</text>
        <text x={rtl ? width - 4 : 4} y={16} textAnchor={rtl ? toLeft : toRight} className="st-axis">{t('story.axisY')}</text>
        <path d={path('2031')} fill="none" stroke={INK.bill} strokeWidth={2} strokeDasharray="6 5" opacity={0.75} />
        <path d={path('2027')} fill="none" stroke={INK.bill} strokeWidth={3.5} strokeLinejoin="round" />
        <text x={x(X1)} y={y(ends.gains['2031']) - 10} textAnchor="end" className="st-label">2031</text>
        <text x={x(X1)} y={y(ends.gains['2027']) - 10} textAnchor="end" className="st-label st-strong">2027</text>
        {free > X0 + 1500 && !phone ? (
          <text x={x((X0 + free) / 2)} y={m.t + 18} textAnchor="middle" className="st-note">{t('story.freeNote', { g: num(free, lang) })}</text>
        ) : null}
        {plateau > 0 && !phone ? (
          <text x={x(21000)} y={y(plateau) - 12} textAnchor="middle" className="st-note">{t('story.plateauNote', { v: num(plateau, lang) })}</text>
        ) : null}
        {/* The reader: a line down to their salary, a dot on 2027, a handle the keyboard moves too. */}
        <line x1={x(you)} x2={x(you)} y1={m.t} y2={h - m.b} stroke={INK.reader} strokeDasharray="2 4" />
        <circle cx={x(you)} cy={y(at.gains['2031'])} r={5} fill="var(--color-sheet)" stroke={INK.bill} strokeWidth={2} />
        <g tabIndex={0} role="slider" aria-label={t('story.handle')} aria-valuemin={X0} aria-valuemax={X1} aria-valuenow={you}
           aria-valuetext={sentence} className="st-handle"
           onKeyDown={(e) => {
             const step = e.shiftKey ? 1000 : 250;
             const more = rtl ? ['ArrowLeft', 'ArrowUp'] : ['ArrowRight', 'ArrowUp'];
             const less = rtl ? ['ArrowRight', 'ArrowDown'] : ['ArrowLeft', 'ArrowDown'];
             if (more.includes(e.key)) { e.preventDefault(); set({ g: String(snap(you + step)) }); }
             if (less.includes(e.key)) { e.preventDefault(); set({ g: String(snap(you - step)) }); }
           }}>
          <circle cx={x(you)} cy={y(at.gains['2027'])} r={phone ? 22 : 16} fill="transparent" />
          <circle cx={x(you)} cy={y(at.gains['2027'])} r={phone ? 9 : 8} fill={INK.reader} stroke="var(--color-sheet)" strokeWidth={2.5} />
        </g>
      </svg>
      <figcaption className="st-read" aria-live="polite"><b>{t('story.youMean')}</b> {sentence}</figcaption>
      <button type="button" className="st-more" aria-expanded={table} onClick={() => setTable((v) => !v)}>{table ? t('story.hideTable') : t('story.showTable')}</button>
      {table ? <Table points={points} lang={lang} /> : null}
    </figure>
  );
}

function Table({ points, lang }: { points: CurvePoint[]; lang: string }) {
  const { t } = useTaxT();
  const rows = points.filter((p) => p.g % 2000 === 0 || p.g === 3000);
  return (
    <div className="st-table-wrap">
      <table className="st-table">
        <thead><tr><th>{t('story.tGross')}</th><th>{t('story.tNow')}</th><th>2027</th><th>2031</th></tr></thead>
        <tbody>
          {rows.map((p) => (
            <tr key={p.g}><td>{num(p.g, lang)}</td><td>{num(p.now, lang)}</td><td>+{num(p.gains['2027'], lang)}</td><td>+{num(p.gains['2031'], lang)}</td></tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
