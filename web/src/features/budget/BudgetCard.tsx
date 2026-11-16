import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { useBudget, useBudgetLaws } from './budget.api';
import { money } from './money';
import './words';

/** The latest finance law on the home page: what the State takes in and spends as two bars, the deficit as its own
 *  figure (the law's, never one bar less the other), and the way in. */
export function BudgetCard() {
  const { t, i18n } = useTranslation();
  const laws = useBudgetLaws();
  const latest = laws.data?.filter((l) => l.kind === 'law').sort((a, b) => b.year - a.year)[0];
  const budget = useBudget(latest ? String(latest.year) : '');
  const b = budget.data?.balance;
  if (!latest) return null;
  const n = (key: string) => Number(b?.[key]?.amount ?? 0);
  const revenue = n('ordinary_revenue');
  const spending = n('ordinary_spending') + n('investment');
  const deficit = -n('state_balance');
  const bars = [
    [t('budget.fact.revenue'), revenue, 'bg-in-force'],
    [t('budget.fact.spending'), spending, 'bg-stamp'],
  ] as const;
  const most = Math.max(revenue, spending) || 1;
  return (
    <Link to={`/budget/${latest.year}`}
          className="grid items-center gap-8 rounded-control bg-sheet px-5 py-8 text-ink no-underline hover:text-ink sm:px-12 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.3fr)] lg:gap-14">
      <div className="flex flex-col gap-3">
        <h2 className="m-0 font-law text-h1 font-bold leading-tight">{t('budget.title', { year: latest.year })}</h2>
        <p className="m-0 max-w-[52ch] text-body leading-relaxed text-ink-soft">{t('budget.cardLead')}</p>
        <span className="text-body font-semibold text-stamp">{t('budget.open')}</span>
      </div>
      {b ? (
        <dl className="m-0 flex flex-col gap-4">
          {bars.map(([label, value, tone]) => (
            // One group a line, its bar inside the figure: a <dl> holds its <dt>/<dd> pairs one <div> deep (UX15).
            <div key={label} className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1.5 text-body">
              <dt>{label}</dt>
              <dd className="m-0 font-semibold">{money(value, i18n.language, t)}</dd>
              <dd aria-hidden="true" className="m-0 h-5 w-full rounded-[3px] bg-paper">
                <div className={`h-full rounded-[3px] ${tone}`} style={{ width: `${(100 * value) / most}%` }} />
              </dd>
            </div>
          ))}
          <div className="flex items-baseline gap-3 text-body text-amended">
            <dt>{t('budget.fact.deficit')}</dt>
            <dd className="m-0 font-semibold">{money(deficit, i18n.language, t)}</dd>
          </div>
        </dl>
      ) : null}
    </Link>
  );
}
