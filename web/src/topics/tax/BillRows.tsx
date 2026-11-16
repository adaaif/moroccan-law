import { Fragment, useState, type ReactNode } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { reducedMotion } from '../kit/motion';
import { useToolState } from '../kit/tool/state';
import { allowanceCost, salaryTax } from './rules/income';
import { BILL_YEARS, useBillYears } from './billYears';
import { useMoney, useTaxT } from './strings';

/** «لك» under each change of the bill page's salaried section (the bill-rows rewrite, 27 Oct 2026):
 *  the reader's own figure, from the gross salary and dependents the page's calculator and curve keep in the address
 *  (`g`, `k`), so it moves as they do. Each is the tool's arithmetic (rules/income.ts), on the bill's rows. */

/** «**60.000**» in a translated sentence: the figures the reader looks for, in bold. */
function bold(s: string): ReactNode {
  return s.split('**').map((part, i) => (i % 2 ? <b key={i}>{part}</b> : <Fragment key={i}>{part}</Fragment>));
}

function useSalary(slug: string) {
  const [s] = useToolState({ g: '10000', k: '0' });
  const [params] = useSearchParams();
  const gross = Math.max(0, Number(s.g) || 0), kids = Number(s.k) || 0;
  return { gross, kids, mine: params.has('g'), b: useBillYears(slug, gross, kids) };
}

/** «مثلا، بأجر 10.000 درهم خام فالشهر:», the salary a button that takes the reader to where it is typed: the calculator
 *  beside the changes on a desk, else the curve's handle. */
function Lead({ gross, mine }: { gross: number; mine: boolean }) {
  const { t } = useTaxT();
  const { n } = useMoney();
  const go = () => {
    const field = [...document.querySelectorAll<HTMLInputElement>('.bw-gain input')].find((e) => e.offsetParent !== null);
    const target = field ?? document.querySelector<HTMLElement>('.st-story');
    target?.scrollIntoView({ behavior: reducedMotion() ? 'auto' : 'smooth', block: 'center' });
    field?.focus({ preventScroll: true });
  };
  return (
    <>
      {t(mine ? 'rows.leadMine' : 'rows.lead')}{' '}
      <button type="button" className="ch-you-g" onClick={go} title={t('rows.change')}>{t('rows.gross', { amount: n(gross) })}</button>{' '}
      {t('rows.leadEnd')}
    </>
  );
}

/** Professional expenses: what comes off the reader's salary before tax, today and in 2027, and what that alone saves. */
export function YouExpenses({ slug }: { slug: string }) {
  const { t } = useTaxT();
  const { n } = useMoney();
  const { gross, kids, mine, b } = useSalary(slug);
  if (!b) return null;
  const y27 = b.years[0].r;
  const before = Math.round(b.today.expenses / 12), after = Math.round(y27.expenses / 12);
  // This change alone in 2027: the year's tax with today's expenses, less the bill's.
  const alone = Math.round(salaryTax(gross, kids, { ...b.rules('2027'), expenses: b.base.expenses }).monthly.tax - y27.monthly.tax);
  const text = after <= before ? t('rows.expCap', { cap: n(b.base.expenses.cap) })
    : alone > 0 ? t('rows.expMore', { after: n(after), before: n(before), alone: n(alone) })
    : t('rows.expNoTax', { after: n(after), before: n(before) });
  return <div className="ch-you"><p><Lead gross={gross} mine={mine} /> {bold(text)}</p></div>;
}

/** The top rate: the rate on the reader's own last dirham, today and each year of the bill. */
export function YouTop({ slug }: { slug: string }) {
  const { t } = useTaxT();
  const { n } = useMoney();
  const { gross, mine, b } = useSalary(slug);
  if (!b) return null;
  const cells = [{ y: t('bill.today'), rate: b.today.marginal, law: true }, ...b.years.map((x) => ({ y: x.y, rate: x.r.marginal, law: false }))];
  // Whether the reader's income reaches the top slice, today or in any year of the bill (each against its own scale).
  const top = (s: Record<string, number>) => Math.max(s.s1, s.s2, s.s3, s.s4, s.s5);
  const reaches = b.today.taxable > top(b.base.scale) || b.years.some((x, i) => x.r.taxable > top(b.rules(BILL_YEARS[i]).scale));
  return (
    <div className="ch-you">
      <p><Lead gross={gross} mine={mine} /> {t('rows.topLast')}</p>
      {/* A row of years is a chart: today at the left, 2031 at the right, in Arabic too. */}
      <ol className="ch-yrs" dir="ltr" aria-label={t('rows.topAria')}>
        {cells.map((c) => <li key={c.y} className={c.law ? 'law' : ''}><span>{c.y}</span><b>{c.rate}%</b></li>)}
      </ol>
      <p><small>{bold(reaches ? t('rows.topReach', { taxable: n(Math.round(b.today.taxable)) }) : t('rows.topBelow', { taxable: n(Math.round(b.today.taxable)) }))}</small></p>
    </div>
  );
}

const ALLOWANCES = ['500', '1000', '2000', '3000'];

/** The monthly allowances from 2031: the reader picks how much they receive; the tax it would bear a month. */
export function YouAllowance({ slug }: { slug: string }) {
  const { t } = useTaxT();
  const { n } = useMoney();
  const { gross, kids, mine, b } = useSalary(slug);
  const [s, set] = useToolState({ a: '1000' });
  if (!b) return null;
  const a = Number(s.a) || 0;
  const cost = Math.round(allowanceCost(gross, a, kids, b.rules('2031')));
  return (
    <div className="ch-you">
      <div className="ch-chips" role="group" aria-label={t('rows.allowAsk')}>
        <span className="ch-ask">{t('rows.allowAsk')}</span>
        {ALLOWANCES.map((v) => (
          <button key={v} type="button" className="ch-chip" aria-pressed={s.a === v} onClick={() => set({ a: v })}>{n(Number(v))}</button>
        ))}
      </div>
      <p aria-live="polite">
        <Lead gross={gross} mine={mine} />{' '}
        {bold(cost > 0 ? t('rows.allowCost', { a: n(a), cost: n(cost) }) : t('rows.allowNone', { a: n(a) }))}
      </p>
      <p><small>{t('rows.allowNote')}</small></p>
    </div>
  );
}

/** The yearly declaration: one question, and what article 86 or 82 says to the answer. */
export function YouDeclare() {
  const { t } = useTaxT();
  const [only, setOnly] = useState<boolean | null>(null);
  return (
    <div className="ch-you">
      <div className="ch-chips" role="group" aria-label={t('rows.declAsk')}>
        <span className="ch-ask">{t('rows.declAsk')}</span>
        <button type="button" className="ch-chip" aria-pressed={only === true} onClick={() => setOnly(true)}>{t('yes')}</button>
        <button type="button" className="ch-chip" aria-pressed={only === false} onClick={() => setOnly(false)}>{t('no')}</button>
      </div>
      {only === null ? null : (
        <p aria-live="polite">
          {bold(t(only ? 'rows.declOnly' : 'rows.declOther'))}{' '}
          <Link to={only ? '/ma/code/cgi/art_86' : '/ma/code/cgi/art_82'} dir="rtl" lang="ar">{only ? 'المادة 86' : 'المادة 82'}</Link>
        </p>
      )}
    </div>
  );
}
