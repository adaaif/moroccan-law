import { useConsumerT } from './strings';

const DAY = 864e5;
const at = (d: string) => Date.parse(`${d}T12:00:00Z`);
const monthName = (d: string, lang: string) => new Date(`${d}T12:00:00Z`).toLocaleDateString(lang === 'fr' ? 'fr-MA' : 'ar-MA', { month: 'short', timeZone: 'UTC' });
const short = (d: string, lang: string, year = false) => new Date(`${d}T12:00:00Z`).toLocaleDateString(lang === 'fr' ? 'fr-MA' : 'ar-MA', { day: 'numeric', month: 'short', ...(year ? { year: 'numeric' } : {}), timeZone: 'UTC' });

/** A short period as its days, one cell each (T1: «the days left as a strip»): the days gone dimmed, today ringed, the last
 *  day in the topic's colour. Days run left to right on an Arabic page too (the chart rule of 1 Nov 2026). More than ten days become a bar. */
export function DayStrip({ days, today }: { days: string[]; today: string }) {
  const { t, i18n } = useConsumerT();
  if (!days.length) return null;
  const last = days[days.length - 1];
  if (days.length > 10) {
    const gone = Math.min(days.length, Math.max(0, Math.round((at(today) - at(days[0])) / DAY) + 1));
    return (
      <div dir="ltr" className="flex flex-col gap-1" aria-hidden="true">
        <div className="h-3 overflow-hidden rounded-full bg-rule">
          <div className="h-full rounded-full bg-[var(--t)] transition-[width] duration-500 motion-reduce:transition-none" style={{ width: `${(gone / days.length) * 100}%` }} />
        </div>
        <div className="flex justify-between text-meta text-ink-soft"><span>{short(days[0], i18n.language)}</span><span className="font-semibold text-ink">{short(last, i18n.language)}</span></div>
      </div>
    );
  }
  return (
    <ol dir="ltr" className="m-0 grid list-none gap-1 p-0" style={{ gridTemplateColumns: `repeat(${days.length}, minmax(0, 1fr))` }} aria-hidden="true">
      {days.map((d, i) => {
        const past = d < today, now = d === today, end = d === last;
        // The month under the day only where it changes, so seven days fit a phone's width.
        const month = i === 0 || d.slice(5, 7) !== days[i - 1].slice(5, 7);
        return (
          <li key={d} style={{ animationDelay: `${i * 35}ms` }}
              className={`flex min-w-0 flex-col items-center gap-0.5 rounded-control px-0.5 py-1.5 text-center motion-safe:animate-[rise_220ms_ease-out_both] ${
                end ? 'bg-[var(--t)] text-on-stamp' : past ? 'bg-rule text-ink-soft opacity-60' : 'bg-paper text-ink'} ${now ? 'ring-2 ring-ink' : ''}`}>
            <span className="text-body font-semibold leading-none tabular-nums">{Number(d.slice(8))}</span>
            <span className="text-meta leading-tight">{month ? monthName(d, i18n.language) : '\u00a0'}</span>
          </li>
        );
      })}
      <span className="sr-only">{t('strip.left')}</span>
    </ol>
  );
}

export type Span = { from: string; to: string; label: string; tone?: 'main' | 'soft' | 'extra' | 'warn' };

/** Periods on one line of time (T2, T3): each span a bar from its first day to its last, today a marker across them all,
 *  so the reader sees which periods still run. */
export function Periods({ spans, today, caption }: { spans: Span[]; today: string; caption?: string }) {
  const { i18n } = useConsumerT();
  const lang = i18n.language;
  if (!spans.length) return null;
  const lo = Math.min(...spans.map((s) => at(s.from)), at(today));
  const hi = Math.max(...spans.map((s) => at(s.to)), at(today));
  const x = (d: string) => ((at(d) - lo) / Math.max(DAY, hi - lo)) * 100;
  const years = (s: Span) => s.from.slice(0, 4) !== s.to.slice(0, 4) || s.from.slice(0, 4) !== today.slice(0, 4);
  const tone = { main: 'bg-[var(--t)]', soft: 'bg-[color-mix(in_srgb,var(--t)_35%,var(--color-sheet))]', extra: 'bg-[repeating-linear-gradient(135deg,var(--t)_0_6px,color-mix(in_srgb,var(--t)_45%,var(--color-sheet))_6px_12px)]', warn: 'bg-amended' };
  return (
    <figure className="m-0 flex flex-col gap-2" aria-label={caption}>
      <div className="relative flex flex-col gap-3 py-2">
        {spans.map((s, i) => (
          <div key={i} className="flex flex-col gap-1">
            <div className="flex items-baseline justify-between gap-2 text-meta">
              <span className="font-semibold">{s.label}</span>
              {/* A span outside this year, or across one, names its years: «14 أكتوبر → 14 أكتوبر» read as no time at all. */}
              <span className="tabular-nums text-ink-soft">{short(s.from, lang, years(s))} → {short(s.to, lang, years(s))}</span>
            </div>
            <div className="relative h-3 rounded-full bg-rule">
              <div className={`absolute inset-y-0 rounded-full transition-[inset-inline-start,width] duration-500 motion-reduce:transition-none ${tone[s.tone ?? 'main']}`}
                   style={{ insetInlineStart: `${x(s.from)}%`, width: `${Math.max(1.5, x(s.to) - x(s.from))}%` }} />
              {/* Today on each bar, not one line down the figure: that one crossed the dates written above the bars. */}
              <div aria-hidden="true" className="pointer-events-none absolute -inset-y-1 w-0.5 rounded-full bg-ink transition-[inset-inline-start] duration-500 motion-reduce:transition-none" style={{ insetInlineStart: `${x(today)}%` }} />
            </div>
          </div>
        ))}
      </div>
      {caption ? <figcaption className="text-meta text-ink-soft">{caption}</figcaption> : null}
    </figure>
  );
}
