import { useId, type ReactNode } from 'react';

/** A part of the account's pages: its title on a rule, what it holds under it. `more` sits at the rule's end. */
export function Part({ id, title, lead, more, children }: {
  id?: string; title: ReactNode; lead?: ReactNode; more?: ReactNode; children: ReactNode;
}) {
  const h = useId();
  return (
    <section id={id} className="ac-part" aria-labelledby={h}>
      <header className="ac-part-head"><h2 id={h}>{title}</h2>{more}</header>
      {lead ? <p className="ac-lead">{lead}</p> : null}
      {children}
    </section>
  );
}

/** A part with nothing in it: its title and one line, never a box. */
export function Line({ id, title, children }: { id?: string; title: ReactNode; children: ReactNode }) {
  return (
    <section id={id} className="ac-part ac-line">
      <h2>{title}</h2>
      <p>{children}</p>
    </section>
  );
}
