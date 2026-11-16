import type { ReactNode } from 'react';
import { useT } from '../strings';

/** Chips to choose one answer, named by the question they answer (the kit's `Chips` names a group by a visible label
 *  above it; here the question is the step's heading). */
export function Choice<K extends string | number>({ name, options, value, onChange, tight = false }: {
  name: string;
  options: { key: K; label: string }[];
  value: K | null;
  onChange: (k: K) => void;
  /** Two short answers beside a question: narrower, so the question keeps the width. */
  tight?: boolean;
}) {
  return (
    <div role="radiogroup" aria-label={name} className={`flex flex-wrap ${tight ? 'gap-1' : 'gap-2'}`}>
      {options.map((o) => (
        <button key={String(o.key)} type="button" role="radio" aria-checked={o.key === value} onClick={() => onChange(o.key)} style={tight ? { minWidth: 44 } : undefined}
                className={`min-h-11 rounded-full border ${tight ? 'px-3' : 'px-4'} text-body transition-[background-color,border-color,transform] duration-150 active:scale-[.97] motion-reduce:transition-none ${
                  o.key === value ? 'border-ink bg-ink font-semibold text-sheet' : 'border-field bg-sheet text-ink'}`}>
          {o.label}
        </button>
      ))}
    </div>
  );
}

/** A yes or a no on one ruled row, the question at the start, its reason under it when it has one. */
export function YesNo({ label, why, value, onChange, children }: {
  label: string;
  why?: string;
  value: boolean;
  onChange: (yes: boolean) => void;
  children?: ReactNode;
}) {
  const { t } = useT();
  return (
    <div className="flex flex-col gap-1 border-t border-rule py-2 first:border-t-0">
      <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-2">
        <span className="min-w-0 flex-1 text-body">{label}</span>
        <Choice tight name={label} value={value ? 'y' : 'n'} onChange={(k) => onChange(k === 'y')}
                options={[{ key: 'n', label: t('ask.no') }, { key: 'y', label: t('ask.yes') }]} />
      </div>
      {why ? <span className="text-meta text-ink-soft">{why}</span> : null}
      {children}
    </div>
  );
}
