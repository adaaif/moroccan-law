/* Class strings of the kit (shared/components/ui.tsx) for controls that cannot be one of its components. */
export type Variant = 'primary' | 'secondary' | 'quiet' | 'icon';

const VARIANT: Record<Variant, string> = {
  primary: 'h-12 px-6 bg-stamp font-semibold text-on-stamp hover:bg-stamp-deep hover:text-on-stamp',
  secondary: 'h-11 px-5 border border-rule bg-sheet text-ink hover:border-stamp hover:text-stamp',
  quiet: 'h-11 px-3 text-ink hover:bg-paper hover:text-stamp',
  icon: 'size-11 text-ink hover:bg-paper hover:text-stamp',
};

/** A button's classes, for the rare control that cannot be a <Button> (a <label>, a native <summary>). */
export function buttonClass(variant: Variant = 'secondary', className = ''): string {
  // Pressed, it gives a little under the finger (U7 of the Moroccan-design review).
  // Never wider than what holds it (PX8 of the where-it-trips review: a long French label laid a phone page out 468 px wide).
  return `inline-flex max-w-full shrink-0 items-center justify-center gap-2 rounded-control text-body no-underline transition-transform active:scale-[0.97] disabled:cursor-wait disabled:opacity-60 motion-reduce:transition-none motion-reduce:active:scale-100 ${VARIANT[variant]} ${className}`;
}

/** The two button strings features used before the kit (P4 of the polish review), now the kit's own. */
export const primaryButton = buttonClass('primary');
export const secondaryButton = buttonClass('secondary');

/** A chip: a filter or an example to tap (40 px), a kind of post, a word. `on` marks the chosen filter. */
export function chipClass(on = false, className = ''): string {
  return `inline-flex h-10 shrink-0 items-center gap-1.5 rounded-full border px-4 text-meta no-underline ${
    on ? 'border-stamp bg-stamp font-semibold text-on-stamp hover:text-on-stamp' : 'border-rule bg-sheet text-ink hover:border-stamp hover:text-stamp'} ${className}`;
}

export const TONE = {
  people: { fill: 'bg-people-wash', rule: 'border-people-fill', ink: 'text-people' },
  talk: { fill: 'bg-talk-wash', rule: 'border-talk', ink: 'text-talk' },
  warn: { fill: 'bg-amended-wash', rule: 'border-amended', ink: 'text-amended' },
  law: { fill: 'bg-wash', rule: 'border-stamp-line', ink: 'text-stamp' },
} as const;

/** The ink of a tone, for a note's label. */
export const toneInk = (tone: keyof typeof TONE) => TONE[tone].ink;

