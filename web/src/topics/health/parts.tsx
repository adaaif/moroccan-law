import { useState } from 'react';
import { useHealthT } from './strings';
import { pct } from '@/shared/locales/i18n';

/** An amount typed in dirhams, Western digits, left to right in both languages. */
export function MoneyField({ label, value, onChange, note }: { label: string; value: string; onChange: (v: string) => void; note?: string }) {
  return (
    <label className="flex flex-col gap-1.5">
      <span className="text-body font-semibold">{label}</span>
      <input type="number" inputMode="decimal" min={0} value={value === '0' ? '' : value} placeholder="0" onChange={(e) => onChange(e.target.value || '0')}
             className="h-12 w-48 rounded-control border border-field bg-sheet px-3 text-body tabular-nums" dir="ltr" />
      {note ? <span className="max-w-[60ch] text-meta text-ink-soft">{note}</span> : null}
    </label>
  );
}

/** «من 300 درهم، شحال كيرجع ليك؟» as one bar, readable by Moroccans at a glance: the
 *  price the whole width, what the fund pays back from the left in the topic's colour, the reader's part after it in ink
 *  (left to right on every page: the chart rule of 1 Nov 2026, HM34), each labelled at its end with its amount; then
 *  «يعني:» with the reader's own figures, the numbers as a table one tap away, and the source. Drawn in the page's width,
 *  no word under 14 px. */
export function SplitBar({ price, back, left, rate, money, source }: {
  price: number; back: number; left: number; rate: number; money: (x: number) => string; source: string;
}) {
  const { t } = useHealthT();
  const [table, setTable] = useState(false);
  const dh = (x: number) => t('dh', { amount: money(x) });
  const share = price > 0 ? back / price : 0;
  return (
    <section className="flex flex-col gap-3 rounded-card bg-sheet px-5 py-5 sm:px-7" aria-labelledby="split-q">
      <h2 id="split-q" className="m-0 text-lead font-semibold">{t('refund.q', { price: dh(price) })}</h2>
      <div aria-hidden="true" dir="ltr" className="flex h-9 w-full overflow-hidden rounded-control">
        {share > 0 ? <div className="bg-[var(--t)] transition-[width] duration-500 motion-reduce:transition-none" style={{ width: `${share * 100}%` }} /> : null}
        {share < 1 ? <div className="flex-1 bg-ink" /> : null}
      </div>
      <div aria-hidden="true" dir="ltr" className="flex items-start justify-between gap-4 text-meta">
        <span className="flex flex-col items-start"><b dir="auto" className="text-body font-bold text-[color:var(--t)] tabular-nums">{dh(back)}</b><span dir="auto" className="text-ink-soft">{t('refund.back')} · {pct(`${rate}%`)}</span></span>
        <span className="flex flex-col items-end"><b dir="auto" className="text-body font-bold text-ink tabular-nums">{dh(left)}</b><span dir="auto" className="text-ink-soft">{t('refund.left')}</span></span>
      </div>
      <p className="m-0 text-body" aria-live="polite">{t('refund.means', { price: dh(price), back: dh(back), left: dh(left) })}</p>
      <button type="button" aria-expanded={table} onClick={() => setTable((o) => !o)}
              className="min-h-11 self-start border-0 bg-transparent p-0 text-meta font-medium text-stamp">{t('refund.table')}</button>
      {table ? (
        <table className="w-full max-w-md border-collapse text-body tabular-nums">
          <tbody>
            {[[t('refund.priceRow'), dh(price)], [t('refund.back'), dh(back)], [t('refund.left'), dh(left)], ['%', `${rate}%`]].map(([k, v]) => (
              <tr key={k} className="border-t border-rule"><th scope="row" className="py-2 text-start font-normal text-ink-soft">{k}</th><td className="py-2 text-end font-semibold">{v}</td></tr>
            ))}
          </tbody>
        </table>
      ) : null}
      <p className="m-0 text-meta text-ink-soft">{t('refund.source', { src: source })}</p>
    </section>
  );
}
