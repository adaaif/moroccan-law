import type { ComponentProps, CSSProperties, ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { buttonClass, TONE, type Variant } from './buttons';

/* The kit (P4 of the polish review, 19 Oct 2026): three surfaces (Sheet, Card, Note), four buttons, one chip, one row,
   one section head, an empty state and a skeleton. Each replaces a class string features had copied 10 to 128 times
   (59 kinds of button, 18 kinds of card, 10 corner radii). Corners: `rounded-control` (10 px) for controls,
   `rounded-card` (18 px) for cards and sheets, `rounded-full` only for chips and pills. */

type ButtonProps = { variant?: Variant; className?: string; children: ReactNode };

/** A button, or a link that looks like one when it has `to` (on the site) or `href` (elsewhere). */
export function Button({ variant = 'secondary', className = '', children, ...rest }: ButtonProps &
  (({ to: string } & Omit<ComponentProps<typeof Link>, 'className' | 'children'>)
    | ({ href: string } & Omit<ComponentProps<'a'>, 'className' | 'children'>)
    | ({ to?: undefined; href?: undefined } & Omit<ComponentProps<'button'>, 'className' | 'children'>))) {
  const cls = buttonClass(variant, className);
  if ('to' in rest && rest.to !== undefined) return <Link {...(rest as ComponentProps<typeof Link>)} className={cls}>{children}</Link>;
  if ('href' in rest && rest.href !== undefined) return <a {...(rest as ComponentProps<'a'>)} className={cls}>{children}</a>;
  return <button type="button" {...(rest as ComponentProps<'button'>)} className={cls}>{children}</button>;
}

/** A card: white, 18 px corners, no ring; a page's sections sit on the paper as cards. */
export function Card({ as: Tag = 'section', className = '', children, id, style, ...aria }: {
  as?: 'section' | 'div' | 'article' | 'li' | 'aside';
  className?: string;
  children: ReactNode;
  id?: string;
  style?: CSSProperties;
  'aria-labelledby'?: string;
  'aria-label'?: string;
}) {
  return <Tag id={id} style={style} {...aria} className={`rounded-card bg-sheet px-5 py-5 sm:px-8 sm:py-7 ${className}`}>{children}</Tag>;
}

/** A note beside the main thing: people's words (saffron), the conversation (teal), a warning (amber). `quiet` draws
 *  it as a 3 px rule on its start side, for a note that must not outshout what it sits under (P5). */
export function Note({ tone, quiet = false, className = '', children, ...rest }: {
  tone: keyof typeof TONE;
  quiet?: boolean;
  className?: string;
  children: ReactNode;
} & Omit<ComponentProps<'section'>, 'className' | 'children'>) {
  const t = TONE[tone];
  const look = quiet ? `border-s-[3px] ${t.rule} ps-4` : `rounded-card ${t.fill} px-4 py-3.5 sm:px-5`;
  return <section {...rest} className={`flex flex-col gap-2 ${look} ${className}`}>{children}</section>;
}

/** A row of a list that leads somewhere: 56 px at least, its words, a chevron that points onward. */
export function ListRow({ to, href, icon, title, lead, end, lang, className = '' }: {
  to?: string;
  href?: string;
  icon?: ReactNode;
  title: ReactNode;
  lead?: ReactNode;
  end?: ReactNode;
  lang?: string;
  className?: string;
}) {
  const inner = (
    <>
      {icon ? <span className="shrink-0">{icon}</span> : null}
      <span className="flex min-w-0 flex-1 flex-col gap-0.5">
        <span lang={lang} className="text-lead leading-snug">{title}</span>
        {lead ? <span className="text-meta text-ink-soft">{lead}</span> : null}
      </span>
      {end}
      {to || href ? <Chevron /> : null}
    </>
  );
  const cls = `flex min-h-14 items-center gap-3 py-3 text-ink no-underline hover:text-stamp ${className}`;
  if (to) return <Link to={to} className={cls}>{inner}</Link>;
  if (href) return <a href={href} target="_blank" rel="noreferrer" className={cls}>{inner}</a>;
  return <div className={cls}>{inner}</div>;
}

/** A section's head: its title, an optional line on what it holds, and the way to all of it, at the end (44 px). */
export function SectionHeader({ id, title, lead, to, more, level = 2 }: {
  id?: string;
  title: ReactNode;
  lead?: ReactNode;
  to?: string;
  more?: string;
  level?: 2 | 3;
}) {
  const H = level === 2 ? 'h2' : 'h3';
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
      <H id={id} className={`m-0 font-bold ${level === 2 ? 'text-h3' : 'text-lead'}`}>{title}</H>
      {to && more ? <Link to={to} className="ms-auto inline-flex min-h-11 items-center text-body font-medium no-underline">{more}</Link> : null}
      {lead ? <p className="m-0 basis-full text-body text-ink-soft">{lead}</p> : null}
    </div>
  );
}

/** A place where something will be, while it loads: no words, its shape (P17). Still with reduced motion. */
export function Skeleton({ className = '' }: { className?: string }) {
  return <span aria-hidden="true" className={`block rounded-control bg-rule-soft motion-safe:animate-pulse ${className}`} />;
}

/** A page while it loads, in its own shape (P17 of the polish review): a text (its title, its source line, a summary,
 *  an article) or a list of cards. «جارٍ التحميل…» used to sit pressed under the header on an empty page. */
export function PageSkeleton({ kind = 'list' }: { kind?: 'text' | 'list' }) {
  if (kind === 'text') {
    return (
      <div aria-busy="true" className="flex min-h-svh flex-col gap-4 rounded-card bg-sheet px-5 py-7 sm:px-10">
        <Skeleton className="h-10 w-2/3" />
        <Skeleton className="h-4 w-11/12" />
        <Skeleton className="h-4 w-3/4" />
        <div className="flex gap-2"><Skeleton className="h-8 w-24 rounded-full" /><Skeleton className="h-8 w-20 rounded-full" /></div>
        <Skeleton className="h-24 w-full rounded-card" />
        <Skeleton className="mt-4 h-11 w-32 rounded-full" />
        <div className="flex flex-col gap-3 border-s-[3px] border-stamp-line ps-4">
          <Skeleton className="h-5 w-full" /><Skeleton className="h-5 w-11/12" /><Skeleton className="h-5 w-3/5" />
        </div>
      </div>
    );
  }
  return (
    // A screen's height (HM11): the footer under a loading page was pushed away when the page came.
    <div aria-busy="true" className="flex min-h-svh flex-col gap-4">
      <Skeleton className="h-9 w-1/2" />
      <Skeleton className="h-4 w-3/4" />
      {[0, 1, 2].map((i) => (
        <div key={i} className="flex flex-col gap-3 rounded-card bg-sheet px-5 py-5">
          <Skeleton className="h-5 w-2/3" /><Skeleton className="h-4 w-11/12" /><Skeleton className="h-4 w-1/2" />
        </div>
      ))}
    </div>
  );
}

/** Lines of a list while they load, inside a card that is already drawn. */
export function LinesSkeleton({ lines = 3 }: { lines?: number }) {
  return (
    <div aria-busy="true" className="flex flex-col gap-3 py-1">
      {Array.from({ length: lines }, (_, i) => <Skeleton key={i} className={`h-5 ${i % 2 ? 'w-3/4' : 'w-11/12'}`} />)}
    </div>
  );
}

/** Nothing here yet: a small drawing, what will be here, and the next step. */
export function EmptyState({ art, title, lead, children }: { art?: ReactNode; title: ReactNode; lead?: ReactNode; children?: ReactNode }) {
  return (
    <div className="flex flex-col items-start gap-3 rounded-card bg-sheet px-5 py-6 sm:px-8">
      {art}
      <p className="m-0 text-lead font-semibold">{title}</p>
      {lead ? <p className="m-0 max-w-[60ch] text-body text-ink-soft">{lead}</p> : null}
      {children}
    </div>
  );
}

/** One grid (P4): every page inside the header's own width (1104 px of content). A reading page keeps its words in a
 *  720 px column at the start, where the header's name is, with a 300 px side column on a desk when it has one. */
export function Page({ width = 'wide', aside, className = '', children }: {
  width?: 'wide' | 'reading';
  aside?: ReactNode;
  className?: string;
  children: ReactNode;
}) {
  // A page fades in after its skeleton (P19 of the polish review), still with reduced motion.
  const shell = 'mx-auto w-full max-w-6xl px-4 pb-14 pt-6 sm:px-6 sm:pt-10 motion-safe:animate-[fade-in_180ms_ease-out]';
  if (width === 'wide') return <main className={`${shell} flex flex-col gap-5 ${className}`}>{children}</main>;
  return (
    <main className={`${shell} lg:grid lg:grid-cols-[minmax(0,45rem)_300px] lg:justify-between lg:gap-12`}>
      <div className={`flex min-w-0 flex-col gap-5 ${className}`}>{children}</div>
      {aside ? <aside className="mt-8 flex min-w-0 flex-col gap-4 lg:mt-0">{aside}</aside> : null}
    </main>
  );
}

const Chevron = () => (
  <svg aria-hidden="true" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"
       className="shrink-0 text-ink-soft ltr:rotate-180"><path d="m15 6-6 6 6 6" /></svg>
);
