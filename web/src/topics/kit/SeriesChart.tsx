import { useState } from 'react';
import { pick, useKitT, type Series } from './api';
import { Cites } from './parts';
import { useWidth } from './viz/viz';

const H = 280;
const COLOURS = ['var(--color-chart-1)', 'var(--color-chart-2)'];

/** An official series charted beside the articles it concerns (F13 of the family plan): at most two lines, one axis,
 *  a legend and labels at the line ends, a crosshair that reads a year out, the numbers as a table one tap away, and
 *  under it what the numbers do not say. Time runs left to right in both languages, as the HCP prints it. */
export default function SeriesChart({ s }: { s: Series }) {
  const { t, i18n } = useKitT();
  const lang = i18n.language;
  const [at, setAt] = useState<number | null>(null);
  // Drawn at its real width (PX28 of the where-it-trips review), never a scaled drawing: a 640-wide one shrunk to a phone
  // set its 13 px labels near 6 px. Narrow, the margins give room and the years are named every few.
  const [box, width] = useWidth<HTMLDivElement>(640);
  const W = Math.max(280, width);
  const M = W < 420 ? { top: 16, right: 64, bottom: 32, left: 52 } : { top: 16, right: 92, bottom: 32, left: 68 };
  // Dirhams to the centime as the decrees print them (17,92), a rate with its sign (13 %), counts as they are.
  const nf = new Intl.NumberFormat(lang === 'fr' ? 'fr-MA' : 'ar-MA', s.unit === 'dirhams'
    ? { minimumFractionDigits: 2, maximumFractionDigits: 2 } : { maximumFractionDigits: 1 });
  const show = (v: number) => (s.unit === 'percent' ? `${nf.format(v)}%` : nf.format(v));
  const value = (y: Series['years'][number], k: string) => Number(y[k]);
  const top = niceMax(Math.max(...s.years.flatMap((y) => s.lines.map((l) => value(y, l.key)))));
  const x = (i: number) => M.left + (i * (W - M.left - M.right)) / Math.max(1, s.years.length - 1);
  const y = (v: number) => H - M.bottom - (v / top) * (H - M.top - M.bottom);
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((f) => f * top);
  const last = s.years.length - 1;
  const every = Math.max(1, Math.ceil((s.years.length * 44) / (W - M.left - M.right)));
  const titleId = `series-${s.key}`;
  return (
    <figure className="m-0 flex flex-col gap-3 rounded-card bg-sheet px-5 py-5 sm:px-7">
      <figcaption className="flex flex-col gap-1">
        <h2 id={titleId} lang={lang} className="m-0 text-lead font-semibold">{pick(s.title, lang)}</h2>
        {s.lead ? <p lang={lang} className="m-0 text-meta text-ink-soft">{pick(s.lead, lang)}</p> : null}
      </figcaption>
      <ul className="m-0 flex list-none flex-wrap gap-x-5 gap-y-1 p-0 text-meta">
        {s.lines.map((l, i) => (
          <li key={l.key} className="inline-flex items-center gap-2">
            <span aria-hidden="true" className="h-0.5 w-5 rounded-full" style={{ background: COLOURS[i] }} />{pick(l.label, lang)}
          </li>
        ))}
      </ul>
      <div ref={box} className="relative" dir="ltr">
        <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} role="img" aria-labelledby={titleId} className="block"
             onMouseLeave={() => setAt(null)}>
          {ticks.map((v) => (
            <g key={v}>
              <line x1={M.left} x2={W - M.right} y1={y(v)} y2={y(v)} stroke="var(--color-rule)" strokeWidth="1" />
              <text x={M.left - 8} y={y(v)} textAnchor="end" dominantBaseline="middle" fontSize="14" fill="var(--color-ink-soft)">{nf.format(v)}</text>
            </g>
          ))}
          {s.years.map((yr, i) => (i % every && i !== last ? null :
            <text key={yr.year} x={x(i)} y={H - M.bottom + 20} textAnchor="middle" fontSize="14" fill="var(--color-ink-soft)">{yr.year}</text>
          ))}
          {at !== null ? <line x1={x(at)} x2={x(at)} y1={M.top} y2={H - M.bottom} stroke="var(--color-ink-soft)" strokeDasharray="3 3" /> : null}
          {s.lines.map((l, li) => (
            <g key={l.key}>
              <polyline fill="none" stroke={COLOURS[li]} strokeWidth="2" strokeLinejoin="round" strokeLinecap="round"
                        points={s.years.map((yr, i) => `${x(i)},${y(value(yr, l.key))}`).join(' ')} />
              {s.years.map((yr, i) => (
                <circle key={yr.year} cx={x(i)} cy={y(value(yr, l.key))} r={at === i ? 5.5 : 4} fill={COLOURS[li]}
                        stroke="var(--color-sheet)" strokeWidth="2" />
              ))}
              <text x={x(last) + 10} y={y(value(s.years[last], l.key))} dominantBaseline="middle" fontSize="14" fill="var(--color-ink)">
                {show(value(s.years[last], l.key))}
              </text>
            </g>
          ))}
          {/* Hit areas wider than the marks: a column per year. */}
          {s.years.map((yr, i) => (
            <rect key={yr.year} x={x(i) - (W - M.left - M.right) / (2 * Math.max(1, last))} y={M.top}
                  width={(W - M.left - M.right) / Math.max(1, last)} height={H - M.top - M.bottom} fill="transparent"
                  onMouseEnter={() => setAt(i)} onTouchStart={() => setAt(i)} />
          ))}
        </svg>
        {at !== null ? (
          <div dir={lang === 'fr' ? 'ltr' : 'rtl'} role="status"
               className="pointer-events-none absolute top-2 rounded-control bg-ink px-3 py-2 text-meta text-sheet shadow-lg"
               style={{ left: `${Math.min(70, (x(at) / W) * 100)}%` }}>
            <p className="m-0 font-semibold">{s.years[at].year}</p>
            {s.lines.map((l, li) => (
              <p key={l.key} className="m-0 flex items-center gap-2">
                <span aria-hidden="true" className="size-2 rounded-full" style={{ background: COLOURS[li] }} />
                {pick(l.label, lang)}: {show(value(s.years[at], l.key))}
              </p>
            ))}
          </div>
        ) : null}
      </div>
      {s.notes?.length ? (
        <ul className="m-0 flex list-disc flex-col gap-1 ps-5 text-meta text-ink-soft">
          {s.notes.map((n, i) => <li key={i} lang={lang}>{pick(n, lang)}</li>)}
        </ul>
      ) : null}
      <details className="text-meta">
        <summary className="min-h-11 cursor-pointer py-2 font-medium text-stamp">{t('table')}</summary>
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-start">
            <thead>
              <tr className="border-b border-rule">
                <th scope="col" className="py-2 pe-3 text-start font-semibold">{t('year')}</th>
                {s.lines.map((l) => <th key={l.key} scope="col" className="py-2 pe-3 text-start font-semibold">{pick(l.label, lang)}</th>)}
                <th scope="col" className="py-2 text-start font-semibold">{t('sources')}</th>
              </tr>
            </thead>
            <tbody>
              {s.years.map((yr) => (
                <tr key={yr.year} className="border-b border-rule-soft">
                  <th scope="row" className="py-2 pe-3 text-start font-medium">{yr.year}</th>
                  {s.lines.map((l) => <td key={l.key} className="py-2 pe-3 tabular-nums">{show(value(yr, l.key))}</td>)}
                  <td className="py-2">
                    <a href={s.files[yr.from]?.url} target="_blank" rel="noreferrer" dir="ltr">
                      {yr.page ? t('from', { title: s.files[yr.from]?.title ?? yr.from, page: yr.page })
                        : s.files[yr.from]?.title ?? yr.from}
                    </a>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="m-0 mt-2 text-ink-soft" dir="ltr">{s.table}</p>
          <p className="m-0 mt-1 text-ink-soft">{t('sourceFile')}</p>
        </div>
      </details>
      <Cites cites={s.cites} />
    </figure>
  );
}

function niceMax(v: number): number {
  const step = 10 ** Math.floor(Math.log10(v || 1));
  return Math.ceil(v / step) * step;
}
