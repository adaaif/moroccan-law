import type React from 'react';

/** The registry's date stamp (the justice review): the clerk presses it on a requête to say the day it was filed
 *  (58.25 art. 77: the copy so stamped is the receipt). Here it says the last day one may still file: a double frame in
 *  the topic's ink pressed a little askew on the paper, its caption on top, the day large, the weekday under. An object,
 *  so never mirrored; the day is written as the reader's language writes it. */
export function RegistryStamp({ day, lang, caption, foot }: { day: string; lang: string; caption: string; foot?: string }) {
  const d = new Date(`${day}T12:00:00Z`);
  const fmt = (o: Intl.DateTimeFormatOptions) => d.toLocaleDateString(lang === 'fr' ? 'fr-MA' : 'ar-MA', { ...o, timeZone: 'UTC' });
  return (
    <figure className="m-0 flex justify-center py-2" aria-hidden="true">
      <div className="relative w-full overflow-hidden rounded-card bg-sheet px-6 pb-6 pt-7"
           style={{ maxWidth: 420, boxShadow: 'inset 0 0 0 1px var(--color-rule)' }}>
        {/* The requête under the stamp: its ruled lines. */}
        <div className="absolute flex flex-col gap-3" style={{ top: 24, left: 24, right: 24, opacity: 0.55 }}>
          {[92, 78, 88, 64, 82, 70].map((w, i) => <span key={i} className="block h-1.5 rounded-full bg-rule" style={{ width: `${w}%` }} />)}
        </div>
        <div className="relative mx-auto flex w-fit flex-col items-center gap-1 px-6 py-3 text-[color:var(--t)]"
             style={{ borderRadius: 14, transform: 'rotate(-4deg)', border: '3px solid currentColor', outline: '1.5px solid currentColor', outlineOffset: 3,
                      background: 'color-mix(in srgb, var(--color-sheet) 82%, transparent)', mixBlendMode: 'var(--blend-ink, multiply)' as React.CSSProperties['mixBlendMode'] }}>
          <span lang={lang} className="text-meta font-bold">{caption}</span>
          <span dir={lang === 'fr' ? 'ltr' : 'rtl'} lang={lang} className="whitespace-nowrap text-h2 font-bold leading-none tabular-nums">
            {fmt({ day: 'numeric', month: 'long' })}
          </span>
          <span lang={lang} className="text-body font-semibold tabular-nums">{fmt({ weekday: 'long', year: 'numeric' })}</span>
          {foot ? <span lang={lang} className="pt-1 text-meta" style={{ borderTop: '1px solid currentColor' }}>{foot}</span> : null}
        </div>
      </div>
    </figure>
  );
}
