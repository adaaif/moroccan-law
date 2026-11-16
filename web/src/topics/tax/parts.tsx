import { useState, type ReactNode } from 'react';
import { ArticlePeek, Chips } from '../kit/tool/parts';
import type { Slice } from './rules/income';
import { articleLabel, useMoney, useTaxT } from './strings';

/** The scale as a staircase the dirhams climb (the tax review, the slice): each slice a step as wide as the
 *  income it covers and as high as its rate; the reader's income filled in the topic's colour up to its mark, the rest of
 *  the stairs drawn light; each step's rate over it and what it costs the reader under it. Drawn left to right on every
 *  page (the chart rule of 1 Nov 2026, HM34: the first slice at the left, «45%» with its sign on the right), the
 *  reader's line in its own direction. */
export function Staircase({ slices, income, compact = false }: { slices: Slice[]; income: number; compact?: boolean }) {
  const { t, i18n } = useTaxT();
  const { n } = useMoney();
  const rtl = i18n.language !== 'fr';
  // A phone's width in viewBox units, so the words keep their size (14 px and more) on the screen they are read on.
  const W = 360, H = compact ? 120 : 220, base = H - (compact ? 14 : 30), top = compact ? 24 : 52;
  const last = slices[slices.length - 1];
  const reach = Math.max(income * 1.2, slices[3]?.from ?? 0, 1);
  const maxX = Math.min(reach, (last.from || reach) * 1.25);
  const X = (v: number) => 4 + (Math.min(v, maxX) / maxX) * (W - 8);
  const maxRate = Math.max(...slices.map((s) => s.rate), 1);
  const hOf = (rate: number) => 8 + (rate / maxRate) * (base - top - 18);
  const shown = slices.filter((s) => s.from < maxX);
  return (
    <figure className="m-0 flex flex-col gap-1.5">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={t('stairs.caption')} direction="ltr" className="block h-auto w-full">
        {shown.map((s, i) => {
          const x0 = X(s.from), x1 = X(s.to ?? maxX), x2 = X(Math.min(income, s.to ?? maxX));
          const h = hOf(s.rate);
          const left = Math.min(x0, x1), width = Math.abs(x1 - x0);
          const filledLeft = Math.min(x0, x2), filled = income > s.from ? Math.abs(x2 - x0) : 0;
          return (
            <g key={i}>
              <rect x={left} y={base - h} width={width} height={h} style={{ fill: 'color-mix(in srgb, var(--t) 12%, var(--color-sheet))', stroke: 'color-mix(in srgb, var(--t) 35%, transparent)' }} strokeWidth="1" />
              {filled ? <rect x={filledLeft} y={base - h} width={filled} height={h} style={{ fill: 'var(--t)' }} /> : null}
              {width >= 26 ? (
                <text x={(x0 + x1) / 2} y={base - h - 6} textAnchor="middle" className="fill-ink" style={{ fontSize: compact ? 18 : 15, fontWeight: 700 }}>
                  {s.rate ? `${s.rate}%` : t('stairs.free')}
                </text>
              ) : null}
              {!compact && s.tax > 0 && filled >= 44 ? (
                <text x={(x0 + x2) / 2} y={base + 20} textAnchor="middle" className="fill-ink-soft" style={{ fontSize: 14 }}>{n(s.tax)}</text>
              ) : null}
            </g>
          );
        })}
        <line x1={X(0)} x2={X(maxX)} y1={base} y2={base} strokeWidth="1.5" className="stroke-ink" />
        {income > 0 ? (
          <g>
            <line x1={X(income)} x2={X(income)} y1={compact ? top - 8 : 22} y2={base + 4} strokeWidth="2" strokeDasharray="4 3" className="stroke-ink" />
            {compact ? null : (
              // The reader's income over its mark, kept inside the drawing near either edge (in Arabic, `start` is the right).
              <text x={X(income)} y={15} direction={rtl ? 'rtl' : 'ltr'} textAnchor={X(income) < 70 ? (rtl ? 'end' : 'start') : X(income) > W - 70 ? (rtl ? 'start' : 'end') : 'middle'} className="fill-ink" style={{ fontSize: 14, fontWeight: 700 }}>
                {`${t('stairs.you')}: ${n(income)}`}
              </text>
            )}
          </g>
        ) : null}
      </svg>
      {compact ? null : <figcaption className="text-meta text-ink-soft">{t('stairs.caption')}</figcaption>}
    </figure>
  );
}

/** The scale as a table, one row a slice, what it costs the reader in the last column. */
export function SliceTable({ slices }: { slices: Slice[] }) {
  const { t } = useTaxT();
  const { n } = useMoney();
  return (
    <details className="group">
      <summary className="flex min-h-11 cursor-pointer list-none items-center justify-between gap-3 text-body font-semibold">
        {t('stairs.table')}<span aria-hidden="true" className="transition-transform group-open:rotate-180 motion-reduce:transition-none">⌄</span>
      </summary>
      <table className="w-full border-collapse text-body tabular-nums">
        <thead><tr className="border-b border-rule text-meta text-ink-soft"><th className="py-1.5 text-start font-medium">{t('stairs.from')}</th><th className="text-start font-medium">{t('stairs.to')}</th><th className="text-start font-medium">{t('stairs.rate')}</th><th className="text-end font-medium">{t('stairs.onYou')}</th></tr></thead>
        <tbody>
          {slices.map((s, i) => (
            <tr key={i} className="border-b border-rule">
              <td className="py-1.5" dir="ltr">{n(s.from)}</td>
              <td dir="ltr">{s.to === null ? t('stairs.above') : n(s.to)}</td>
              <td>{s.rate ? `${s.rate}%` : t('stairs.free')}</td>
              <td className="text-end font-semibold" dir="ltr">{n(s.tax)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </details>
  );
}

export type Line = { key: string; label: ReactNode; note?: ReactNode; amount: number | null; minus?: boolean; sum?: boolean; cites?: string[] };

/** A calculation as a ledger (the work payslip's paper, T10): each line its amount and its article, a tap opening the
 *  article over the page; sums under a double rule. */
export function Ledger({ title, lines, children }: { title: ReactNode; lines: Line[]; children?: ReactNode }) {
  const { c } = useMoney();
  const [peek, setPeek] = useState<string | null>(null);
  return (
    <section className="flex flex-col rounded-control bg-sheet px-4 pb-4 pt-4 shadow-[0_1px_0_var(--color-rule)] sm:px-6">
      <h2 className="m-0 border-b-2 border-ink pb-2 text-lead font-bold">{title}</h2>
      <ul className="m-0 flex list-none flex-col p-0">
        {lines.map((r, i) => {
          const amount = r.amount === null ? '—' : `${r.minus ? '−' : ''}${c(r.amount)}`;
          const inner = (
            <>
              <span className="flex min-w-0 flex-1 flex-col">
                <span className={`text-body ${r.sum ? 'font-bold' : 'font-medium'}`}>{r.label}</span>
                {r.note ? <span className="text-meta text-ink-soft">{r.note}</span> : null}
                {r.cites?.length ? <span lang="ar" dir="rtl" className="self-start text-meta text-stamp">{articleLabel(r.cites[0])}</span> : null}
              </span>
              <span dir="ltr" className={`shrink-0 text-body tabular-nums ${r.sum ? 'font-bold' : 'font-semibold'} ${r.minus ? 'text-amended' : ''}`}>{amount}</span>
            </>
          );
          const cls = `flex w-full items-start gap-3 py-2.5 text-start ${r.sum ? 'border-t-2 border-ink' : i ? 'border-t border-rule' : ''}`;
          return (
            <li key={r.key}>
              {r.cites?.length ? <button type="button" onClick={() => setPeek(r.cites![0])} className={`${cls} hover:text-stamp`}>{inner}</button> : <div className={cls}>{inner}</div>}
            </li>
          );
        })}
      </ul>
      {children}
      {peek ? <ArticlePeek path={peek} onClose={() => setPeek(null)} /> : null}
    </section>
  );
}

/** The year whose law a tool applies (C4: the years the site can cite). */
export function YearChips({ value, onChange }: { value: string; onChange: (y: string) => void }) {
  const { t } = useTaxT();
  return <Chips label={t('year')} value={value} onChange={onChange} options={['2026', '2025'].map((y) => ({ key: y, label: t('yearOf', { year: y }) }))} />;
}

/** An amount typed by the reader, in dirhams. */
export function MoneyField({ label, value, onChange, note }: { label: string; value: string; onChange: (v: string) => void; note?: string }) {
  return (
    <label className="flex flex-col gap-1.5">
      <span className="text-body font-semibold">{label}</span>
      <input type="number" inputMode="decimal" min={0} value={value === '0' ? '' : value} placeholder="0" onChange={(e) => onChange(e.target.value || '0')}
             className="h-12 w-48 rounded-control border border-field bg-sheet px-3 text-body tabular-nums" dir="ltr" />
      {note ? <span className="text-meta text-ink-soft">{note}</span> : null}
    </label>
  );
}

/** A tool's inputs on their sheet. */
export function Inputs({ children }: { children: ReactNode }) {
  return <section className="flex flex-col gap-4 rounded-card bg-sheet px-5 py-5 sm:px-7">{children}</section>;
}
