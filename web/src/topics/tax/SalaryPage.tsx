import { PageSkeleton } from '@/shared/components/ui';
import { todayIso } from '@/shared/services/today';
import { useRateOn } from '../kit/api';
import { KitPage } from '../kit/parts';
import { AnswerCard, Listen, SourceFold } from '../kit/tool/parts';
import Stepper from '../kit/tool/Stepper';
import { useToolState } from '../kit/tool/state';
import { Inputs, Ledger, MoneyField, SliceTable, Staircase, YearChips } from './parts';
import { salaryTax } from './rules/income';
import { articleLabel, useMoney, useTaxT, yearDay } from './strings';
import { Link } from 'react-router-dom';

/** «شحال كيقطعو ليا من الأجرة؟» (T10 of the tax review): from the month's gross salary, the worker's CNSS and AMO
 *  shares (the work topic's rates), professional expenses (CGI 59), the net taxable income on the staircase of art. 73,
 *  the family deduction (74), the month's tax and net. The year chip applies that year's law (2025: 500 a dependent;
 *  2026: 600). The average rate and the rate on the next dirham said apart, in words. Waits for a person's check (C3). */
export default function SalaryPage({ slug }: { slug: string }) {
  const { t, i18n } = useTaxT();
  const { n, c } = useMoney();
  const lang = i18n.language === 'fr' ? 'fr' : 'ar';
  const [s, set] = useToolState({ y: todayIso().slice(0, 4) >= '2026' ? '2026' : '2025', g: '10000', k: '0' });
  const day = yearDay(s.y, todayIso());
  const scale = useRateOn(slug, 'scale', day);
  const family = useRateOn(slug, 'family', day);
  const expenses = useRateOn(slug, 'expenses', day);
  const cnss = useRateOn('work', 'cnss', day);
  if (!scale || !family || !expenses || !cnss) return <KitPage slug={slug} title={t('salary.title')} lead={t('salary.lead')}><PageSkeleton /></KitPage>;
  const gross = Math.max(0, Number(s.g) || 0);
  const kids = Number(s.k);
  const r = salaryTax(gross, kids, { scale, family, expenses, cnss });
  // What 100 dirhams more a month cost in tax and leave in the pocket: the same payslip with 100 more.
  const raise = salaryTax(gross + 100, kids, { scale, family, expenses, cnss });
  const extraTax = Math.round((raise.monthly.tax - r.monthly.tax) * 100) / 100;
  const keep = Math.round((raise.monthly.net - r.monthly.net) * 100) / 100;
  const cites = ['/ma/code/cgi/art_59', '/ma/code/cgi/art_73', '/ma/code/cgi/art_74', '/ma/code/cgi/art_156', s.y === '2025' ? '/ma/loi/60-24/art_8' : '/ma/loi/50-25/art_7'];
  return (
    <KitPage slug={slug} title={t('salary.title')} lead={t('salary.lead')}>
      <AnswerCard share over={t('salary.net')} value={Math.round(r.monthly.net * 100)} format={(v) => t('dh', { amount: c(v / 100) })}
                  under={<p className="m-0">{t('salary.taxLine', { tax: c(r.monthly.tax) })}</p>}>
        <p className="m-0 text-meta text-ink-soft">{t('salary.average', { rate: r.average.toLocaleString(lang === 'fr' ? 'fr-MA' : 'ar-MA') })} · {t('salary.marginal', { rate: r.marginal })}</p>
      </AnswerCard>

      <Inputs>
        <MoneyField label={t('salary.gross')} value={s.g} onChange={(g) => set({ g })} />
        <Stepper label={t('salary.dependents')} value={kids} max={10} onChange={(v) => set({ k: String(v) })} note={t('salary.dependentsNote')} />
        <YearChips value={s.y} onChange={(y) => set({ y })} />
        {/* The bill's years are a bill's, in a tool of their own (the finance-bill review, P6): never a chip of the law's. */}
        <Link to={`/topics/tax/tools/bill?g=${encodeURIComponent(s.g)}&k=${s.k}`} className="inline-flex min-h-11 items-center self-start text-body font-medium">{t('salary.billYears')}</Link>
      </Inputs>

      <section className="flex flex-col gap-3 rounded-card bg-sheet px-5 py-5 sm:px-7">
        <Staircase slices={r.slices} income={r.taxable} />
        <p className="m-0 text-body">{t('salary.marginalNote', { tax: c(extraTax), keep: c(keep) })}</p>
        <SliceTable slices={r.slices} />
      </section>

      <Ledger title={`${t('salary.slip')} · ${t('perYear')}`} lines={[
        { key: 'gross', label: t('salary.lines.gross'), amount: r.grossYear },
        { key: 'cnss', label: t('salary.lines.cnss'), amount: r.cnss, minus: true, cites: ['/ma/decret/2-01-2723/art_2'] },
        { key: 'amo', label: t('salary.lines.amo'), amount: r.amo, minus: true, cites: ['/ma/decret/2-05-734/art_1'] },
        { key: 'expenses', label: t('salary.lines.expenses', { rate: r.expensesRate }), note: t('salary.lines.expensesNote'), amount: r.expenses, minus: true, cites: ['/ma/code/cgi/art_59'] },
        { key: 'taxable', label: t('salary.lines.taxable'), amount: r.taxable, sum: true },
        { key: 'scale', label: t('salary.lines.scale'), amount: r.scale, cites: ['/ma/code/cgi/art_73'] },
        { key: 'family', label: t('salary.lines.family', { count: kids, per: n(family.per) }), amount: r.family, minus: true, cites: ['/ma/code/cgi/art_74'] },
        { key: 'tax', label: t('salary.lines.tax'), note: `${c(r.monthly.tax)} ${t('perMonth')}`, amount: r.tax, sum: true },
      ]}>
        <p className="m-0 pt-3 text-meta text-ink-soft">{t('salary.cnssNote')} {t('salary.profession')}</p>
      </Ledger>

      <section className="flex flex-col gap-3 rounded-card bg-sheet px-5 py-5 sm:px-7">
        <p className="m-0 text-meta text-ink-soft">{t('estimate')}</p>
        <SourceFold paths={cites} label={articleLabel} />
        <div className="flex flex-wrap gap-2">
          <Link to="/topics/work/tools/pay" className="inline-flex min-h-11 items-center rounded-full border border-field bg-sheet px-4 text-body text-ink no-underline">{t('salary.toPay')}</Link>
          <Listen text={[t('salary.net'), t('dh', { amount: c(r.monthly.net) }), t('salary.taxLine', { tax: c(r.monthly.tax) })].join('. ')} lang={lang} />
        </div>
      </section>
    </KitPage>
  );
}
