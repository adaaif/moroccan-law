import type { ReactNode } from 'react';

/** A tool's inputs on their sheet. */
export function Sheet({ children }: { children: ReactNode }) {
  return <section className="flex flex-col gap-4 rounded-card bg-sheet px-5 py-5 sm:px-7">{children}</section>;
}

export type Message = { key: string; who: 'me' | 'them'; body: ReactNode; time?: string; chip?: ReactNode; warn?: boolean };

/** The law, or the administration, answering in a conversation (the digital review): the reader's own messages
 *  at the end side (left in Arabic, as a phone's thread sets them), the answers at the start side, each its time and its
 *  article under it; the reader's carry the two read ticks. A list, read in order by a screen reader. */
export function Thread({ messages, label }: { messages: Message[]; label: string }) {
  return (
    <ol aria-label={label} className="m-0 flex list-none flex-col gap-2.5 rounded-card px-3 py-4 sm:px-5"
        style={{ background: 'color-mix(in srgb, var(--t) 6%, var(--color-paper))' }}>
      {messages.map((m) => {
        const mine = m.who === 'me';
        return (
          <li key={m.key} className={`flex ${mine ? 'justify-end' : 'justify-start'}`}>
            <div className="flex flex-col gap-1 px-3.5 py-2.5 text-body"
                 style={{
                   maxWidth: '86%', borderRadius: 16,
                   [mine ? 'borderStartEndRadius' : 'borderStartStartRadius']: 4,
                   background: mine ? 'color-mix(in srgb, var(--t) 17%, var(--color-sheet))' : 'var(--color-sheet)',
                   border: `1px solid ${m.warn ? 'var(--color-amended)' : 'color-mix(in srgb, var(--t) 22%, transparent)'}`,
                 }}>
              <div>{m.body}</div>
              {m.chip ? <div>{m.chip}</div> : null}
              {m.time ? (
                <span className="flex items-center gap-1 self-end text-meta text-ink-soft tabular-nums">
                  {m.time}
                  {mine ? <svg aria-hidden="true" width="18" height="11" viewBox="0 0 18 11"><path d="M1 6l3 3 6-7M7 9l1 0.5 7-8" fill="none" stroke="var(--t)" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" /></svg> : null}
                </span>
              ) : null}
            </div>
          </li>
        );
      })}
    </ol>
  );
}

/** A letter on paper, its lines as the reader's language writes them, the law's own name kept as printed. Paper in both
 *  themes is the sheet; the letter is text a person copies, so it is selectable. */
export function LetterSheet({ lines, dir }: { lines: string[]; dir: 'rtl' | 'ltr' }) {
  return (
    <article dir={dir} className="flex flex-col gap-2 rounded-card bg-sheet px-6 py-6 text-body"
             style={{ boxShadow: 'inset 0 0 0 1px var(--color-rule)', userSelect: 'text' }}>
      {lines.map((l, i) => (l === '' ? <span key={i} aria-hidden="true" style={{ height: 6 }} /> : <p key={i} className="m-0">{l}</p>))}
    </article>
  );
}
