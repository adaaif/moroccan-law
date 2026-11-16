import { type KeyboardEvent, type PointerEvent, type ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { useWidth } from '@/topics/kit/viz/viz';
import { columnAt, spaced, stepFor } from './viz';

/** The blog's charts follow the rules written for Moroccan readers (docs/design.md, «Charts run left to right»): a
 *  question in Darija, the years left to right on an Arabic page too, figures as the Bulletin prints them, labels where
 *  the marks end and a legend only for coloured kinds, a tap that answers with a sentence, the numbers a tap away in a
 *  table, and the source under each. Drawn at their real width, so no word is shrunk under 14 px. */

/** A chart's frame: its question, what a mark stands for, the chart, the sentence a tap gives, «يعني:», its source,
 *  and its numbers as a table one tap away. */
export function Figure({ id, q, unit, pick, so, source, table, wide = false, children }: {
  id: string;
  q: string;
  unit?: string;
  pick?: ReactNode;
  so: ReactNode;
  source: string;
  table?: ReactNode;
  wide?: boolean;
  children: ReactNode;
}) {
  const { t } = useTranslation('blog');
  return (
    <figure className={`bp-fig${wide ? ' bp-fig-wide' : ''}`} aria-labelledby={`${id}-q`}>
      <p className="bp-q" id={`${id}-q`}>{q}</p>
      {unit ? <p className="bp-unit">{unit}</p> : null}
      {children}
      {pick !== undefined ? <p className="bp-pick" aria-live="polite">{pick}</p> : null}
      <p className="bp-so"><b>{t('fig.so')}</b> {so}</p>
      <p className="bp-src">{source}</p>
      {table ? (
        <details className="bp-table">
          <summary>{t('fig.table')}</summary>
          <div className="bp-table-scroll">{table}</div>
        </details>
      ) : null}
    </figure>
  );
}

/** A plain table of a chart's numbers. */
/** A chart's colours, each named once, in the order its bars draw them from the left (charts run left to right on an
 *  Arabic page too), the grey rest last (1 Nov 2026: every chart that colours kinds names them). Colours are
 *  `.kc-1` … `.kc-4` and `.kc-rest` in post.css, checked for colour-blind readers in both themes. */
export function Legend({ items, rest }: { items: string[]; rest?: string }) {
  return (
    <ul className="bp-legend" dir="ltr">
      {items.map((x, i) => <li key={x}><i className={`kc-${i + 1}`} aria-hidden="true" /><span dir="auto">{x}</span></li>)}
      {rest ? <li><i className="kc-rest" aria-hidden="true" /><span dir="auto">{rest}</span></li> : null}
    </ul>
  );
}

export function Table({ head, rows }: { head: string[]; rows: (string | number)[][] }) {
  return (
    <table>
      <thead><tr>{head.map((h, i) => <th key={i} scope="col">{h}</th>)}</tr></thead>
      <tbody>{rows.map((r, i) => <tr key={i}>{r.map((c, k) => (k ? <td key={k}>{c}</td> : <th key={k} scope="row">{c}</th>))}</tr>)}</tbody>
    </table>
  );
}

/** Bars one a column, the first at the page's start; `hi` in the Bulletin's violet, the picked one in ink. `marks`
 *  draws a short rule across a bar (the year's last printed page over the pages of its files). Labels sit above the
 *  bars they name; `ticks` names a column under the axis. */
export function Bars({ values, parts, over, height = 170, hi = [], labels = {}, marks, ticks = {}, picked, onPick, aria, rtl }: {
  values: number[];
  /** A band drawn dashed over each bar, apart from it (the texts only the French edition printed, 1912–1925). */
  over?: number[];
  /** A part of each bar drawn darker from its foot (a word carried only by a ministry's name). */
  parts?: number[];
  height?: number;
  hi?: number[];
  labels?: Record<number, string>;
  marks?: (number | null)[];
  ticks?: Record<number, string>;
  picked: number | null;
  onPick: (i: number | null) => void;
  aria: string;
  rtl: boolean;
}) {
  const [ref, width] = useWidth<HTMLDivElement>(640);
  const count = values.length;
  const top = Object.keys(labels).length ? 26 : 6;
  const foot = Object.keys(ticks).length ? 24 : 0;
  const plot = height - top - foot;
  const max = Math.max(...values.map((v, i) => v + (over?.[i] ?? 0)), ...(marks ?? []).map((m) => m ?? 0));
  const step = width / count;
  const gap = count > 30 ? Math.min(2, step * 0.25) : step * 0.22;
  const bw = Math.max(1, step - gap);
  const y = (v: number) => top + plot - (v / max) * plot;
  const left = (i: number) => (rtl ? width - (i + 1) * step : i * step) + gap / 2;
  const middle = (i: number) => left(i) + bw / 2;
  const clamp = (x: number, text: string) => {
    const w = text.length * 8.4;
    return Math.min(Math.max(x, w / 2 + 1), width - w / 2 - 1);
  };
  const move = (e: PointerEvent<SVGSVGElement>) => {
    const box = e.currentTarget.getBoundingClientRect();
    onPick(columnAt(e.clientX - box.left, box.width, count, rtl));
  };
  const key = (e: KeyboardEvent<SVGSVGElement>) => {
    const d = stepFor(e, rtl);
    if (!d) return;
    e.preventDefault();
    onPick(Math.max(0, Math.min(count - 1, (picked ?? (d > 0 ? -1 : count)) + d)));
  };
  return (
    <div ref={ref} className="bp-plot">
      <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} role="img" aria-label={aria} tabIndex={0}
           onPointerMove={move} onPointerDown={move} onKeyDown={key}>
        {values.map((v, i) => (
          <rect key={i} x={left(i)} y={y(v)} width={bw} height={Math.max(v > 0 ? 1 : 0, top + plot - y(v))}
                className={i === picked ? 'is-picked' : hi.includes(i) ? 'is-hi' : ''} />
        ))}
        {parts?.map((v, i) => (v ? (
          <rect key={`p${i}`} x={left(i)} y={y(Math.min(v, values[i]))} width={bw} height={top + plot - y(Math.min(v, values[i]))} className="is-part" />
        ) : null))}
        {over?.map((o, i) => (o ? (
          <rect key={`o${i}`} x={left(i) + 0.5} y={y(values[i] + o)} width={Math.max(0.5, bw - 1)} height={y(values[i]) - y(values[i] + o)} className="is-over" />
        ) : null))}
        {marks?.map((m, i) => (m ? <line key={`m${i}`} className="bp-mark" x1={left(i) - 1} x2={left(i) + bw + 1} y1={y(m)} y2={y(m)} /> : null))}
        <line className="bp-axis" x1={0} x2={width} y1={top + plot + 0.5} y2={top + plot + 0.5} />
        {Object.entries(labels).map(([k, text]) => (
          <text key={`l${k}`} x={clamp(middle(+k), text)} y={y(Math.max(values[+k] + (over?.[+k] ?? 0), marks?.[+k] ?? 0)) - 8} textAnchor="middle"
                direction={rtl ? 'rtl' : 'ltr'} className={hi.includes(+k) ? 'is-strong' : ''}>{text}</text>
        ))}
        {spaced(ticks, middle).map(([k, text]) => (
          <text key={`t${k}`} x={clamp(middle(+k), text)} y={height - 6} textAnchor="middle" className="is-soft">{text}</text>
        ))}
      </svg>
    </div>
  );
}


