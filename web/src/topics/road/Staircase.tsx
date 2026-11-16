import { useRoadT } from './strings';
import type { Step } from './rules/fines';

/** The price as a staircase over the days (A1 of the road tools review): each step a price and the last day it
 *  holds, the step in force lit in the topic's colour, the past ones struck, the reader's today as a marker inside
 *  its step. The steps run left to right on every page, as Moroccans read a chart (HM34). */
export function Staircase({ steps, start, today, labels, money }: {
  steps: Step[];
  /** The day the steps count from (the offence, or the notice served). */
  start: string;
  today: string;
  labels: string[];
  money: (n: number) => string;
}) {
  const { t, i18n } = useRoadT();
  const at = steps.findIndex((s) => today <= s.until);
  const short = (d: string) => new Date(`${d}T12:00:00Z`).toLocaleDateString(i18n.language === 'fr' ? 'fr-MA' : 'ar-MA', { day: 'numeric', month: 'short', timeZone: 'UTC' });
  const days = (a: string, b: string) => Math.round((Date.parse(`${b}T12:00:00Z`) - Date.parse(`${a}T12:00:00Z`)) / 864e5);
  // Where today falls inside its step, from 0 to 1: the days gone of the days the step holds.
  const first = (i: number) => (i ? steps[i - 1].until : start);
  const share = at < 0 ? 1 : Math.min(0.92, Math.max(0.08, (days(first(at), today) + 0.5) / (days(first(at), steps[at].until) + 1)));
  return (
    // Time runs left to right on every page (the chart rule of 1 Nov 2026, HM34), its words in their own direction.
    <div className="flex flex-col gap-2" aria-hidden="true" dir="ltr">
      <div className="relative flex h-36 items-end gap-1.5 pt-7">
        {steps.map((s, i) => (
          <div key={i} style={{ height: `${steps.length === 1 ? 70 : 58 + i * (36 / (steps.length - 1))}%`,
                                // Today's step a shade deeper, so its white figure reads (PX26: 3.98 : 1 on the road's amber).
                                ...(i === at ? { background: 'color-mix(in srgb, var(--t) 82%, black)' } : {}) }}
               className={`relative flex min-w-0 flex-1 flex-col items-center justify-start gap-0.5 rounded-t-control pt-2 transition-[background-color,opacity] duration-300 motion-reduce:transition-none ${
                 i === at ? 'bg-[var(--t)] text-on-stamp' : at < 0 || i < at ? 'bg-rule opacity-50' : 'bg-rule-soft text-ink'}`}>
            <span dir="auto" className={`text-body font-bold tabular-nums ${at < 0 || i < at ? 'line-through' : ''}`}>{money(s.amount)}</span>
            <span dir="auto" className={`text-meta ${i === at ? 'opacity-90' : 'text-ink-soft'}`}>{t('fine.till', { date: short(s.until) })}</span>
            {i === at ? (
              <span className="absolute -top-7 flex flex-col items-center motion-safe:transition-[inset-inline-start] motion-safe:duration-500"
                    style={{ insetInlineStart: `calc(${share * 100}% - 1.6rem)` }}>
                <span dir="auto" className="rounded-full bg-ink px-2 text-meta font-semibold text-paper">{t('fine.today')}</span>
                <span className="h-3 w-0.5 bg-ink" />
              </span>
            ) : null}
          </div>
        ))}
      </div>
      <div className="flex gap-1.5">
        {labels.map((l, i) => <span key={i} dir="auto" className="min-w-0 flex-1 text-center text-meta leading-snug text-ink-soft">{l}</span>)}
      </div>
    </div>
  );
}
