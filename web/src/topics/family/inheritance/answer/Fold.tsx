import { useId, useState, type ReactNode } from 'react';

/** A part of the answer folded under its title (IR19, IR20): the family reads the sum, the professional opens the
 *  working. A 44 px row; the chevron is not mirrored, it points down when closed. */
export default function Fold({ title, children }: { title: string; children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const id = useId();
  return (
    <div className="flex flex-col gap-3 border-t border-rule pt-1">
      <button type="button" aria-expanded={open} aria-controls={id} onClick={() => setOpen(!open)}
              className="flex min-h-12 items-center justify-between gap-3 text-start text-body font-semibold text-ink">
        <span>{title}</span>
        <span aria-hidden="true" className={`text-ink-soft transition-transform motion-reduce:transition-none ${open ? 'rotate-180' : ''}`}>⌄</span>
      </button>
      {open ? <div id={id} className="flex flex-col gap-4 pb-2">{children}</div> : null}
    </div>
  );
}
