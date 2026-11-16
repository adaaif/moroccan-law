import { noteUse } from '../use';

/** A count to set with two 44 px buttons, its number read out as it changes; `step` moves it by more than one, and
 *  `format` says it with its unit («6 سنين»). */
export default function Stepper({ label, value, min = 0, max = 20, step = 1, format, onChange, note, faded }: {
  label: string;
  value: number;
  min?: number;
  max?: number;
  step?: number;
  format?: (v: number) => string;
  onChange: (v: number) => void;
  note?: string;
  faded?: boolean;
}) {
  return (
    <div className={`flex min-h-14 items-center gap-3 border-t border-rule py-2 first:border-t-0 ${faded ? 'opacity-60' : ''}`}>
      <span className="flex min-w-0 flex-1 flex-col">
        <span className="text-body">{label}</span>
        {note ? <span className="text-meta text-ink-soft">{note}</span> : null}
      </span>
      <span className="flex items-center gap-1" role="group" aria-label={label}>
        <button type="button" aria-label="−" disabled={value <= min} onClick={() => { noteUse('answered'); onChange(Math.max(min, value - step)); }}
                className="size-11 rounded-full border border-rule text-lead disabled:opacity-40 hover:border-stamp">−</button>
        <output aria-live="polite" style={{ minWidth: 32 }} className="px-1 text-center text-lead font-semibold tabular-nums">{format ? format(value) : value}</output>
        <button type="button" aria-label="+" disabled={value >= max} onClick={() => { noteUse('answered'); onChange(Math.min(max, value + step)); }}
                className="size-11 rounded-full border border-rule text-lead disabled:opacity-40 hover:border-stamp">+</button>
      </span>
    </div>
  );
}
