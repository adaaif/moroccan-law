import { useState } from 'react';
import { ArticlePeek } from '../../../kit/tool/parts';
import type { Ref } from './refs';

/** The articles a line rests on, from any law, as the calculator's chips: the law named once, then its articles; a tap
 *  opens the article over the tool, so the family keeps its place on the page (IR24, IR25). One sheet for the lot. */
export default function LawChips({ refs, className = '' }: { refs: Ref[]; className?: string }) {
  const [open, setOpen] = useState<string | null>(null);
  if (!refs.length) return null;
  const laws: { law: string; refs: Ref[] }[] = [];
  for (const r of refs) {
    const last = laws[laws.length - 1];
    if (last?.law === r.law) last.refs.push(r);
    else laws.push({ law: r.law, refs: [r] });
  }
  return (
    <span className={`flex flex-col gap-1 ${className}`}>
      {laws.map((g) => (
        <span key={g.law} className="flex flex-wrap items-center gap-1.5">
          <span className="text-meta text-ink-soft">{g.law}</span>
          {g.refs.map((r) => (
            <button key={r.path} type="button" onClick={() => setOpen(r.path)}
                    className="inline-flex min-h-11 items-center rounded-full bg-wash px-3 text-meta font-semibold text-stamp hover:bg-stamp hover:text-on-stamp">
              {r.label}
            </button>
          ))}
        </span>
      ))}
      {open !== null ? <ArticlePeek path={open} onClose={() => setOpen(null)} /> : null}
    </span>
  );
}
