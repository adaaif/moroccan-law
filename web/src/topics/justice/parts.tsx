import type { ReactNode } from 'react';
import { dayWords } from '../kit/tool/days';
import type { Cell } from './rules/deadline';
import type { Stop } from './rules/custody';
import { hoursBetween } from './rules/custody';

/** A tool's inputs on their sheet. */
export function Sheet({ children }: { children: ReactNode }) {
  return <section className="flex flex-col gap-4 rounded-card bg-sheet px-5 py-5 sm:px-7">{children}</section>;
}

export { RegistryStamp } from '../kit/RegistryStamp';

/** The days of a court's limit as a month grid, Monday first and in the page's direction: the day it starts from
 *  hatched (it does not count), the counted days in the topic's tint, the days off the end was moved past in grey, the
 *  last day solid; the first of a month carries its name. The legend under says what each look means. */
export function MonthGrid({ cells, lang, today, legend }: {
  cells: Cell[]; lang: string; today: string; legend: Record<'start' | 'counted' | 'off' | 'last', string>;
}) {
  const loc = lang === 'fr' ? 'fr-MA' : 'ar-MA';
  // Monday to Sunday: 2024-01-01 was a Monday.
  const heads = Array.from({ length: 7 }, (_, i) => new Date(Date.UTC(2024, 0, 1 + i, 12)).toLocaleDateString(loc, { weekday: lang === 'fr' ? 'short' : 'narrow', timeZone: 'UTC' }));
  const look: Record<Cell['mark'], React.CSSProperties> = {
    start: { background: HATCH, color: 'var(--color-ink)' },
    counted: { background: 'color-mix(in srgb, var(--t) 16%, var(--color-sheet))', color: 'var(--color-ink)' },
    uncounted: { background: HATCH, color: 'var(--color-ink)' },
    off: { background: 'var(--color-rule)', color: 'var(--color-ink-soft)' },
    last: { background: 'var(--t)', color: 'var(--color-sheet)', fontWeight: 700 },
    // The month's other days in plain ink-soft (PX26 of the where-it-trips review: faded to 2 : 1, they could not be read).
    outside: { color: 'var(--color-ink-soft)' },
  };
  return (
    <div className="flex flex-col gap-3">
      <div className="grid gap-1" role="presentation" style={{ gridTemplateColumns: 'repeat(7, minmax(0, 1fr))' }}>
        {heads.map((h) => <span key={h} lang={lang} className="pb-1 text-center text-meta text-ink-soft">{h}</span>)}
        {cells.map((c) => {
          const d = new Date(`${c.day}T12:00:00Z`);
          const first = d.getUTCDate() === 1;
          return (
            <span key={c.day} title={dayWords(c.day, lang)}
                  className={`relative flex min-h-11 flex-col items-center justify-center text-body tabular-nums ${c.day === today ? 'ring-2 ring-ink' : ''}`}
                  style={{ ...look[c.mark], borderRadius: 8 }}>
              {d.getUTCDate()}
              {first ? <span lang={lang} className="text-meta leading-none" style={{ fontSize: 14 }}>{d.toLocaleDateString(loc, { month: 'short', timeZone: 'UTC' })}</span> : null}
            </span>
          );
        })}
      </div>
      <ul className="m-0 flex list-none flex-wrap gap-x-4 gap-y-1.5 p-0 text-meta text-ink-soft">
        {(['start', 'counted', 'off', 'last'] as const).map((k) => (
          <li key={k} className="flex items-center gap-1.5">
            <span aria-hidden="true" className="inline-block size-4 rounded-[4px]" style={{ ...look[k], border: '1px solid var(--color-rule)' }} />
            {legend[k]}
          </li>
        ))}
      </ul>
    </div>
  );
}
/** The hatch of a day that does not count. */
const HATCH = 'repeating-linear-gradient(135deg, var(--color-sheet) 0 4px, var(--color-rule) 4px 6px)';

/** The custody's hours as one track left to right on every page (the chart rule of 1 Nov 2026, HM34): the first period solid in the topic's colour, each
 *  extension dashed after it, now as an ink hand when it falls inside; under it only the hours of each end, and under
 *  those the stops with their day and time as a list, so no label sits on another whatever the case. */
export function HourTrack({ stops, now, lang, labels, hour }: {
  stops: Stop[]; now: string | null; lang: string; labels: Record<Stop['key'], string>; hour: (n: number) => string;
}) {
  const total = stops[stops.length - 1].hours;
  const at = (h: number) => `${(h / total) * 100}%`;
  const first = stops.find((s) => s.key === 'end')!.hours;
  const nowAt = now ? hoursBetween(stops[0].at, now) : -1;
  const when = (iso: string) => {
    const day = new Date(`${iso}:00Z`).toLocaleDateString(lang === 'fr' ? 'fr-MA' : 'ar-MA', { weekday: 'long', day: 'numeric', month: 'long', timeZone: 'UTC' });
    return `${day} · ${iso.slice(11, 16)}`;
  };
  const ticks = stops.filter((s) => s.key !== 'lawyer');
  const shift = (h: number) => (h === 0 ? undefined : h === total ? '-100%' : '-50%');
  return (
    <div className="flex flex-col gap-4 px-2 pb-2 pt-5">
      <div className="relative" aria-hidden="true" dir="ltr" style={{ paddingBottom: 28 }}>
        <div className="relative h-4 rounded-full bg-rule">
          <div className="absolute inset-y-0 start-0 rounded-full bg-[var(--t)]" style={{ width: at(first) }} />
          <div className="absolute inset-y-0" style={{ insetInlineStart: at(first), insetInlineEnd: 0, borderStartEndRadius: 9999, borderEndEndRadius: 9999,
            background: 'repeating-linear-gradient(90deg, color-mix(in srgb, var(--t) 55%, transparent) 0 8px, transparent 8px 13px)' }} />
          {nowAt >= 0 && nowAt <= total ? (
            <span className="absolute w-1 rounded-full bg-ink" style={{ top: -12, bottom: -12, insetInlineStart: at(nowAt), translate: '-50%' }} />
          ) : null}
        </div>
        {ticks.map((s) => (
          <span key={s.key} dir="auto" className="absolute whitespace-nowrap text-meta font-semibold tabular-nums text-ink"
                style={{ top: 24, left: at(s.hours), translate: shift(s.hours) }}>{hour(s.hours)}</span>
        ))}
      </div>
      <ol className="m-0 flex list-none flex-col gap-1.5 p-0">
        {stops.map((s) => (
          <li key={s.key} className="flex flex-wrap items-baseline gap-x-2 text-body">
            <span aria-hidden="true" className="inline-block size-2.5 shrink-0 rounded-full"
                  style={{ background: s.key === 'ext1' || s.key === 'ext2' ? 'color-mix(in srgb, var(--t) 55%, transparent)' : 'var(--t)' }} />
            <span className="font-semibold">{labels[s.key]}</span>
            <span lang={lang} className="tabular-nums text-ink-soft">{when(s.at)}</span>
          </li>
        ))}
      </ol>
    </div>
  );
}

/** The court a dispute goes to and the courts above it as three tiers (listed bottom up, drawn top down), the reader's
 *  lit and, under each upper tier, the way up to it, solid only where the law opens it: the appeal (or, for a final judgment, the request to annul to the court's president) and the
 *  cassation. */
export function Ladder({ tiers }: { tiers: { key: string; title: string; line: string; on: boolean; way?: string }[] }) {
  return (
    <ol className="m-0 flex list-none flex-col-reverse gap-0 p-0">
      {tiers.map((t, i) => (
        <li key={t.key} className="flex flex-col">
          <div className={`flex flex-col gap-0.5 rounded-control px-4 py-3 ${t.on ? 'bg-[color-mix(in_srgb,var(--t)_14%,var(--color-sheet))]' : 'bg-sheet opacity-60'}`}
               style={{ border: `1.5px ${t.on ? 'solid' : 'dashed'} ${t.on ? 'color-mix(in srgb, var(--t) 60%, transparent)' : 'var(--color-rule)'}` }}>
            <span className="text-body font-bold">{t.title}</span>
            <span className="text-meta text-ink-soft">{t.line}</span>
          </div>
          {i > 0 ? (
            <span style={{ paddingInlineStart: 24 }} className={`flex items-center gap-2 py-1.5 text-meta ${tiers[i].on ? 'text-ink' : 'text-ink-soft'}`}>
              <span aria-hidden="true" className="inline-block h-6 border-s-2" style={{ width: 0, borderStyle: tiers[i].on ? 'solid' : 'dashed', borderColor: tiers[i].on ? 'var(--t)' : 'var(--color-rule)' }} />
              {t.way}
            </span>
          ) : null}
        </li>
      ))}
    </ol>
  );
}

/** Hours of community work on one bar, 0 to 3,600, the floor of 40 marked, growing rightwards on every page (HM34). */
export function HoursBar({ hours, max, floor, label }: { hours: number; max: number; floor: number; label: string }) {
  return (
    <div className="flex flex-col gap-1.5" aria-hidden="true">
      <div className="relative h-3 rounded-full bg-rule" dir="ltr">
        <div className="absolute inset-y-0 start-0 rounded-full bg-[var(--t)] transition-[width] duration-500 motion-reduce:transition-none" style={{ width: `${Math.max(1, (hours / max) * 100)}%` }} />
        <span className="absolute w-0.5 bg-ink" style={{ top: -4, bottom: -4, insetInlineStart: `${(floor / max) * 100}%` }} />
      </div>
      <span className="text-meta text-ink-soft">{label}</span>
    </div>
  );
}
