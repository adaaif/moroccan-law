import type { ReactNode } from 'react';

/** A tool's inputs on their sheet. */
export function Sheet({ children }: { children: ReactNode }) {
  return <section className="flex flex-col gap-4 rounded-card bg-sheet px-5 py-5 sm:px-7">{children}</section>;
}

/** Dirhams typed, digits only, left to right. */
export function MoneyField({ label, value, onChange, note }: { label: string; value: string; onChange: (v: string) => void; note?: string }) {
  return (
    <label className="flex flex-col gap-1.5">
      <span className="text-body font-semibold">{label}</span>
      <input type="number" inputMode="decimal" min={0} value={value === '0' ? '' : value} placeholder="0" onChange={(e) => onChange(e.target.value || '0')}
             className="h-12 w-48 rounded-control border border-field bg-sheet px-3 text-body tabular-nums" dir="ltr" />
      {note ? <span className="text-meta text-ink-soft">{note}</span> : null}
    </label>
  );
}

/** A form as a card: when the law opens it to the reader, the topic's stamp pressed on its corner («مسموح»); when it
 *  does not, a struck word and the reason with its article. Under, what the form obliges, line by line. */
export function StampCard({ title, open, stamp, reason, chip, lines }: {
  title: string; open: boolean; stamp: string; reason?: string; chip: ReactNode; lines: { key: string; label: string; text: string }[];
}) {
  return (
    <article className={`relative flex h-full flex-col gap-3 rounded-card bg-sheet px-5 py-4 ${open ? '' : 'opacity-75'}`}
             style={{ border: `1.5px ${open ? 'solid' : 'dashed'} color-mix(in srgb, var(--t) ${open ? 55 : 30}%, transparent)` }}>
      <header className="flex items-start justify-between gap-3">
        <h3 className="m-0 text-h3 font-bold">{title}</h3>
        <span aria-hidden={!open} className={`shrink-0 rounded-[4px] px-2 py-0.5 text-meta font-bold ${open ? 'text-[color:var(--t)]' : 'text-ink-soft line-through'}`}
              style={{ border: `2px solid ${open ? 'color-mix(in srgb, var(--t) 80%, transparent)' : 'var(--color-rule)'}`, transform: 'rotate(-4deg)' }}>
          {stamp}
        </span>
      </header>
      {reason ? <p className="m-0 text-body text-ink-soft">{reason}</p> : null}
      <span>{chip}</span>
      <dl className="m-0 grid gap-x-3 gap-y-1.5" style={{ gridTemplateColumns: 'auto 1fr' }}>
        {lines.map((l) => (
          <div key={l.key} className="contents">
            <dt className="text-meta font-semibold text-ink-soft">{l.label}</dt>
            <dd className="m-0 text-meta">{l.text}</dd>
          </div>
        ))}
      </dl>
    </article>
  );
}
