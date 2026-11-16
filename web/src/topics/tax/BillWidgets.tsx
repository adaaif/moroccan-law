import { Link } from 'react-router-dom';
import { useToolState } from '../kit/tool/state';
import Stepper from '../kit/tool/Stepper';
import { MoneyField } from './parts';
import { slices } from './rules/income';
import { useBillYears } from './billYears';
import { useMoney, useTaxT } from './strings';
import './bill.css';

/** The bill page's calculator (the bill-page review, V6): a gross salary and dependents typed on the page give the
 *  month's gain in 2027, large, and the five years as bars; the whole tool a tap away. The inputs live in the address
 *  (`g`, `k`), so the scale through the years beside it hears them. */
export function BillGain({ slug }: { slug: string }) {
  const { t } = useTaxT();
  const { c } = useMoney();
  const [s, set] = useToolState({ g: '10000', k: '0' });
  const gross = Math.max(0, Number(s.g) || 0), kids = Number(s.k);
  const b = useBillYears(slug, gross, kids);
  const most = Math.max(1, ...(b?.years.map((x) => x.gain) ?? [1]));
  return (
    <section className="bw-gain" aria-labelledby="bw-gain">
      <h2 id="bw-gain" className="bw-h">{t('bill.pageGain')}</h2>
      <div className="bw-inputs">
        <MoneyField label={t('salary.gross')} value={s.g} onChange={(g) => set({ g })} />
        <Stepper label={t('salary.dependents')} value={kids} max={10} onChange={(v) => set({ k: String(v) })} />
      </div>
      {b ? (
        <>
          <p className="bw-big">+{c(b.years[0].gain)} <span>{t('bill.perMonthIn', { year: '2027' })}</span></p>
          <ol className="bw-bars">
            {b.years.map((x, i) => (
              <li key={x.y} className={i === 0 ? 'on' : ''}>
                <span>{x.y}</span><span className="bw-bar" style={{ width: `${Math.max(4, (x.gain / most) * 100)}%` }} /><span>+{c(x.gain)}</span>
              </li>
            ))}
          </ol>
          <p className="bw-note">{t('bill.pageGainNote')}</p>
          <Link to={`/topics/${slug}/tools/bill?g=${encodeURIComponent(s.g)}&k=${s.k}`} className="bw-link">{t('bill.pageGainAll')}</Link>
        </>
      ) : null}
    </section>
  );
}

/** «كل عام جدول جديد» as one picture (V8): today's scale and the bill's five on one income axis, each slice as wide as
 *  the income it covers and as tall as its rate, filled to the reader's taxable income, the month's gain at the end.
 *  Income grows to the right, left to right on an Arabic page too (the chart rule of 1 Nov 2026). */
export function ScaleYears({ slug }: { slug: string }) {
  const { t } = useTaxT();
  const { c, n } = useMoney();
  const [s] = useToolState({ g: '10000', k: '0' });
  const gross = Math.max(0, Number(s.g) || 0), kids = Number(s.k);
  const b = useBillYears(slug, gross, kids);
  if (!b) return null;
  const taxable = b.today.taxable;
  const top = Math.max(260_000, Math.ceil((taxable * 1.25) / 20_000) * 20_000);
  const rows = [{ y: t('bill.today'), law: true, scale: b.base.scale, taxable, end: t('bill.monthTax', { amount: c(b.today.monthly.tax) }) },
    ...b.years.map((x) => ({ y: x.y, law: false, scale: b.rules(x.y).scale, taxable: x.r.taxable, end: `+${c(x.gain)}` }))];
  return (
    <section className="bw-scales" aria-labelledby="bw-scales">
      <h2 id="bw-scales" className="bw-h">{t('bill.scalesTitle', { gross: n(gross) })}</h2>
      <ol dir="ltr" className="bw-years">
        {rows.map((r) => {
          const parts = slices(r.scale);
          return (
            <li key={r.y} className={r.law ? 'law' : ''}>
              <span className="bw-y">{r.y}<small>{r.law ? t('bill.theLaw') : t('bill.theBill')}</small></span>
              <span className="bw-steps" role="img" aria-label={t('bill.scaleAria', { year: r.y, rate: parts.at(-1)?.rate ?? 0 })}>
                {parts.map((p) => {
                  const to = Math.min(p.to ?? top, top);
                  if (to <= p.from) return null;
                  const fill = Math.max(0, Math.min(r.taxable, to) - p.from) / (to - p.from);
                  return (
                    <i key={p.from} style={{ width: `calc(${((to - p.from) / top) * 100}% - 2px)`, height: `${6 + p.rate * 0.8}px` }}>
                      <b style={{ width: `${fill * 100}%` }} />
                    </i>
                  );
                })}
                <em style={{ insetInlineStart: `${(Math.min(r.taxable, top) / top) * 100}%` }} />
              </span>
              <span className="bw-end">{r.end}</span>
            </li>
          );
        })}
      </ol>
      <p dir="ltr" className="bw-axis"><span>0</span><span>{t('bill.axis', { amount: n(top) })}</span></p>
      <p className="bw-note">{t('bill.scalesNote', { taxable: c(taxable) })}</p>
    </section>
  );
}
