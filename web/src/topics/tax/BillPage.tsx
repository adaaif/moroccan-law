import { Button, PageSkeleton } from '@/shared/components/ui';
import { KitPage } from '../kit/parts';
import { AnswerCard, Chips, SourceFold } from '../kit/tool/parts';
import { sharePicture } from '../kit/tool/picture';
import Stepper from '../kit/tool/Stepper';
import { useToolState } from '../kit/tool/state';
import { Inputs, MoneyField, SliceTable, Staircase } from './parts';
import { BILL_YEARS as YEARS, exemptUpTo, useBillYears } from './billYears';
import { articleLabel, useMoney, useTaxT } from './strings';

const BILL = '/ma/projet-loi/60-26';
/** A bill's marks are drawn in dashes: a draft (a style, for the stylesheet's budget). */
const DASHED = { border: '1px dashed var(--color-ink-soft)' };

/** «شحال غادي نربح بالمشروع؟» (the finance-bill review, P6, P20; C2 «five», C4 «open»): a salary under the
 *  bill's five scales (247-XXXXVII for 2027–2030, 73-I for 2031) and its 45% expenses, against the law in force today;
 *  the gain each year, the gross under which nothing is due with the reader's dependents, and the picture to forward.
 *  The bill's figures come only from its own rate tables (rows `proposed`), never as law. A CNSS employee: a civil
 *  servant's contributions differ and are not computed here. */
export default function BillPage({ slug }: { slug: string }) {
  const { t, i18n } = useTaxT();
  const { c } = useMoney();
  const lang = i18n.language === 'fr' ? 'fr' : 'ar';
  const [s, set] = useToolState({ y: '2027', g: '10000', k: '0' });
  const gross = Math.max(0, Number(s.g) || 0);
  const kids = Number(s.k);
  const b = useBillYears(slug, gross, kids);
  if (!b) return <KitPage slug={slug} title={t('bill.title')} lead={t('bill.lead')}><PageSkeleton /></KitPage>;
  const { today: today_, years, rules } = b;
  const chosen = years.find((x) => x.y === s.y) ?? years[0];
  const most = Math.max(1, ...years.map((x) => x.gain));
  const free = exemptUpTo(kids, rules(chosen.y));
  const cites = ['/ma/code/cgi/art_73', '/ma/code/cgi/art_247', '/ma/code/cgi/art_59', '/ma/code/cgi/art_74', `${BILL}/art_7`];
  const picture = () => sharePicture({
    dir: lang === 'fr' ? 'ltr' : 'rtl', colour: getComputedStyle(document.documentElement).getPropertyValue('--color-t-tax').trim() || '#8a6d00',
    over: t('bill.cardOver', { year: chosen.y }), value: t('bill.cardValue', { amount: c(chosen.gain) }),
    lines: [t(kids ? 'bill.cardSalary' : 'bill.cardSalaryNone', { gross: c(gross), count: kids }), t('bill.notLaw'),
            ...years.map((x) => t('bill.cardYear', { year: x.y, amount: c(x.gain) }))],
    source: [`${BILL}/art_7`, '/ma/code/cgi/art_73', '/ma/code/cgi/art_247'].map(articleLabel).join(' · '), site: t('bill.site'),
  }, `bill-${chosen.y}`);

  return (
    <KitPage slug={slug} title={t('bill.title')} lead={t('bill.lead')}>
      <p className="m-0 rounded-control px-4 py-3 text-body font-medium" style={DASHED}>{t('bill.band')}</p>
      <AnswerCard share over={t('bill.gain', { year: chosen.y })} value={Math.round(chosen.gain * 100)} format={(v) => t('dh', { amount: c(v / 100) })}
                  under={<p className="m-0">{t('bill.taxes', { now: c(today_.monthly.tax), then: c(chosen.r.monthly.tax), year: chosen.y })}</p>}>
        <p className="m-0 text-meta text-ink-soft">{t(kids ? 'bill.free' : 'bill.freeNone', { gross: c(free.gross), net: c(free.net), count: kids, year: chosen.y })}</p>
      </AnswerCard>

      <Inputs>
        <MoneyField label={t('salary.gross')} value={s.g} onChange={(g) => set({ g })} />
        <Stepper label={t('salary.dependents')} value={kids} max={10} onChange={(v) => set({ k: String(v) })} note={t('salary.dependentsNote')} />
        <Chips label={t('bill.year')} value={s.y} onChange={(y) => set({ y })} options={YEARS.map((y) => ({ key: y, label: y }))} />
      </Inputs>

      {/* The five years one under the other: the month's gain on a bar, the year chosen in ink. */}
      <section className="flex flex-col gap-3 rounded-card bg-sheet px-5 py-5 sm:px-7" aria-labelledby="bill-years">
        <h2 id="bill-years" className="m-0 text-lead font-semibold">{t('bill.years')}</h2>
        <ol className="m-0 flex list-none flex-col gap-1 p-0">
          {years.map((x) => (
            <li key={x.y}>
              <button type="button" onClick={() => set({ y: x.y })} aria-pressed={x.y === chosen.y}
                      style={{ gridTemplateColumns: '3.5rem 1fr auto' }}
                      className={`grid min-h-12 w-full items-center gap-3 rounded-control px-2 text-start hover:bg-paper ${x.y === chosen.y ? 'bg-paper font-semibold' : ''}`}>
                <span className="tabular-nums">{x.y}</span>
                <span className="h-3 rounded-full" style={{ background: 'var(--t)', width: `${Math.max(2, (x.gain / most) * 100)}%`, opacity: x.y === chosen.y ? 1 : 0.45 }} />
                <span className="text-body tabular-nums">{t('bill.perMonth', { amount: c(x.gain) })}</span>
              </button>
            </li>
          ))}
        </ol>
        <p className="m-0 text-meta text-ink-soft">{t('bill.yearsNote')}</p>
      </section>

      <section className="flex flex-col gap-3 rounded-card bg-sheet px-5 py-5 sm:px-7">
        <h2 className="m-0 text-lead font-semibold">{t('bill.scaleOf', { year: chosen.y })}</h2>
        <Staircase slices={chosen.r.slices} income={chosen.r.taxable} />
        <SliceTable slices={chosen.r.slices} />
        <p className="m-0 text-body">{t('bill.expenses', { rate: chosen.r.expensesRate, amount: c(chosen.r.expenses), before: today_.expensesRate })}</p>
      </section>

      <section className="flex flex-col gap-3 rounded-card bg-sheet px-5 py-5 sm:px-7">
        <p className="m-0 text-meta text-ink-soft">{t('bill.assumptions')}</p>
        <SourceFold paths={cites} label={articleLabel} />
        <div className="flex flex-wrap gap-2">
          <Button onClick={() => void picture()}>{t('bill.picture')}</Button>
          <a href={BILL} className="inline-flex min-h-11 items-center rounded-full border border-field bg-sheet px-4 text-body text-ink no-underline">{t('bill.text')}</a>
        </div>
      </section>
    </KitPage>
  );
}
