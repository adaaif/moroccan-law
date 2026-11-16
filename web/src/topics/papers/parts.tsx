import type { ReactNode } from 'react';
import { dayWords } from '../kit/tool/days';
import { todayIso } from '@/shared/services/today';

/** A day typed or picked on the phone's own calendar, the day in words under it (a birth or a card's date is years
 *  away: no chips for it). */
export function DateField({ label, value, onChange, lang, future = false, note }: {
  label: string; value: string; onChange: (d: string) => void; lang: string; future?: boolean; note?: string;
}) {
  return (
    <label className="flex flex-col gap-1.5">
      <span className="text-body font-semibold">{label}</span>
      <input type="date" value={value} dir="ltr" max={future ? undefined : todayIso()} onChange={(e) => e.target.value && onChange(e.target.value)}
             className="h-12 w-full max-w-64 rounded-control border border-field bg-sheet px-3 text-body" />
      <span className="text-meta text-ink-soft">{value ? dayWords(value, lang) : note}</span>
    </label>
  );
}

/** Several of a few, as chips each pressed on its own. */
export function Toggles<K extends string>({ label, options, value, onChange }: {
  label: string; options: { key: K; label: ReactNode }[]; value: K[]; onChange: (v: K[]) => void;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <span className="text-body font-semibold">{label}</span>
      <div role="group" aria-label={label} className="flex flex-wrap gap-2">
        {options.map((o) => {
          const on = value.includes(o.key);
          return (
            <button key={o.key} type="button" aria-pressed={on} onClick={() => onChange(on ? value.filter((k) => k !== o.key) : [...value, o.key])}
                    className={`min-h-11 rounded-full border px-4 text-body transition-[background-color,border-color] duration-150 motion-reduce:transition-none ${on ? 'border-ink bg-ink font-semibold text-sheet' : 'border-field bg-sheet text-ink'}`}>
              {on ? <span aria-hidden="true">✓ </span> : null}{o.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}

/** «YYMMDD», as a card's machine-readable line writes a date. */
const mrz = (d: string) => (d ? d.slice(2).replace(/-/g, '') : '<<<<<<');

/** The identity card drawn large, as the reader holds it: its photo at its left, the end of its validity where the card
 *  prints it, and its machine-readable line under, carrying the birth and the end dates as the card's own line does
 *  (law 04.20, arts 4 and 5). Paper in both themes; an object, so never mirrored. */
export function CardFace({ birth, last, caption, label, lang, warn = false }: {
  birth: string; last: string | null; caption: string; label: string; lang: string; warn?: boolean;
}) {
  return (
    <figure className="m-0 flex justify-center" aria-hidden="true">
      <div dir="ltr" className="relative w-full overflow-hidden" style={{ maxWidth: 380, aspectRatio: '85.6 / 54', borderRadius: 16, background: FACE, border: `1.5px solid ${EDGE}`, color: INK }}>
        <div className="absolute" style={{ left: '6%', top: '14%', width: '24%', height: '50%', borderRadius: 6, background: PHOTO }}>
          <svg viewBox="0 0 40 50" className="size-full">
            <circle cx="20" cy="19" r="9" fill={SHADE} /><path d="M4 50c1.5-11 8-16 16-16s14.5 5 16 16z" fill={SHADE} />
          </svg>
        </div>
        <div className="absolute flex flex-col" style={{ left: '36%', right: '6%', top: '12%', gap: 6 }}>
          <span style={{ height: 7, width: '70%', borderRadius: 4, background: LINE }} />
          <span style={{ height: 7, width: '50%', borderRadius: 4, background: LINE }} />
          <span dir={lang === 'fr' ? 'ltr' : 'rtl'} lang={lang} className="mt-1 text-meta font-semibold" style={{ color: SOFT }}>{caption}</span>
          <span dir={lang === 'fr' ? 'ltr' : 'rtl'} lang={lang} className="font-bold leading-tight tabular-nums" style={{ fontSize: 'clamp(1.15rem, 0.9rem + 1.6vw, 1.6rem)', color: warn ? '#9F2A1F' : INK }}>{label}</span>
        </div>
        <div className="absolute inset-x-0 bottom-0 flex flex-col" style={{ padding: '0 6% 5%', gap: 2, fontFamily: '"OCR B", "OCR-B", ui-monospace, monospace', fontSize: 'clamp(0.62rem, 0.5rem + 0.7vw, 0.85rem)', letterSpacing: '0.12em', color: SOFT }}>
          <span className="truncate">IDMAR{'<'.repeat(25)}</span>
          <span className="truncate">{mrz(birth)}{'<'}{last ? mrz(last) : '<<<<<<'}{'<'.repeat(8)}MAR</span>
        </div>
      </div>
    </figure>
  );
}
/** The card's paper and ink, fixed in both themes (the card is an object): a pale teal, the topic's own. */
const FACE = 'linear-gradient(135deg, #E8F3F4 0%, #F6FAF8 55%, #E3EFEF 100%)';
const EDGE = '#9CC3C8';
const PHOTO = '#CFE3E5';
const SHADE = '#7FA9AE';
const LINE = '#C5DADC';
const INK = '#14262A';
const SOFT = '#4E6669';

/** Dated stops on a dashed lane (the administration's road): the stops gone filled, the reader's next ringed. */
export function Road({ stops, today, lang }: {
  stops: { key: string; date: string; title: string; line?: string; chip?: ReactNode; warn?: boolean }[]; today: string; lang: string;
}) {
  const next = stops.find((x) => x.date >= today)?.key;
  return (
    <ol className="relative m-0 flex list-none flex-col p-0" style={{ paddingInlineStart: 32 }}>
      <span aria-hidden="true" className="absolute"
            style={{ insetBlock: 14, insetInlineStart: 11, width: 3, background: 'repeating-linear-gradient(var(--t) 0 8px, transparent 8px 13px)' }} />
      {stops.map((x) => {
        const past = x.date < today;
        return (
          <li key={x.key} className="relative grid gap-x-3 py-2.5" style={{ gridTemplateColumns: '1fr auto' }}>
            <span aria-hidden="true" className="absolute rounded-full"
                  style={{ insetInlineStart: -29, top: 14, width: 15, height: 15, borderWidth: 3, borderStyle: 'solid',
                           borderColor: x.warn ? 'var(--color-sign-red)' : 'var(--t)', background: past ? 'var(--t)' : 'var(--color-sheet)',
                           boxShadow: x.key === next ? '0 0 0 4px color-mix(in srgb, var(--t) 25%, transparent)' : undefined }} />
            <span lang={lang} className={`text-body font-semibold ${past ? 'text-ink-soft' : ''}`}>{x.title}</span>
            <span className="text-body font-bold tabular-nums">{dayWords(x.date, lang, true)}</span>
            {x.line ? <span lang={lang} className="text-meta text-ink-soft" style={{ gridColumn: '1 / -1' }}>{x.line}</span> : null}
            {x.chip ? <span style={{ gridColumn: '1 / -1' }}>{x.chip}</span> : null}
          </li>
        );
      })}
    </ol>
  );
}
