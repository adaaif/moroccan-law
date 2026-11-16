import { topicColour } from './colour';
import { Scene } from './TopicCover';
import { TopicIcon } from './TopicIcon';

/* The door (U1 of the Moroccan-design review, 25 Oct 2026): the Maghrebi horseshoe arch, whose curve goes past its
   widest point and narrows to the opening, as on Bab Boujloud or Bab Mansour. It marks the ways in and nothing else:
   the topics' doors, a topic's window, the bar's «المواضيع», the icon. Never a card, a button or an article. */

/** The arch on a 120 × 132 grid: jambs at 16 and 104, the circle's centre at (60, 58), radius 48. */
export const ARCH = 'M16 132V77.2A48 48 0 1 1 104 77.2V132Z';

/** A topic's door: its pale tone inside the arch, its line icon low in the opening. */
export function ArchDoor({ slug, className = '' }: { slug: string; className?: string }) {
  return (
    <span style={topicColour(slug)} data-door className={`relative block aspect-[124/136] ${className}`}>
      <svg aria-hidden="true" viewBox="-2 -2 124 136" className="absolute inset-0 size-full">
        <path d={ARCH} strokeWidth="2" className="fill-[color-mix(in_srgb,var(--t)_15%,var(--color-sheet))] stroke-[color-mix(in_srgb,var(--t)_40%,transparent)]" />
      </svg>
      <span className="absolute inset-x-0 top-[44%] flex justify-center text-[color:var(--t)]">
        <TopicIcon slug={slug} size={26} />
      </span>
    </span>
  );
}

/** Where each scene's subject stands on its 320-wide grid: the window looks there. */
const FOCUS: Record<string, number> = { road: 172, work: 135, housing: 200, consumer: 150, land: 155, tax: 125, health: 215 };

/** A topic's window: its scene seen through the arch, 150 of its 320 wide around its subject. */
export function ArchWindow({ slug, className = '' }: { slug: string; className?: string }) {
  const clip = `arch-${slug}`;
  const x = (FOCUS[slug] ?? 160) - 75;
  // Where a door opened from the home lands (U7 of the Moroccan-design review).
  return (
    <svg aria-hidden="true" viewBox="0 0 120 132" data-vt="topic-arch" style={{ ...topicColour(slug), viewTransitionName: 'topic-arch' }}
         className={`block shrink-0 ${className}`}>
      <defs><clipPath id={clip}><path d={ARCH} /></clipPath></defs>
      <g clipPath={`url(#${clip})`}>
        <rect width="120" height="132" className="fill-[color-mix(in_srgb,var(--t)_16%,var(--color-sheet))]" />
        <svg width="120" height="132" viewBox={`${x} -5 150 165`} preserveAspectRatio="xMidYMax meet"><Scene slug={slug} /></svg>
      </g>
      <path d={ARCH} fill="none" strokeWidth="2.5" className="stroke-[color-mix(in_srgb,var(--t)_45%,transparent)]" />
    </svg>
  );
}
