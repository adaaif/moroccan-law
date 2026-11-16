/** A life topic's colour (`t-<slug>`) as a CSS variable, for `text-[var(--t)]` and its washes. */
export const topicColour = (slug: string) => ({ '--t': `var(--color-t-${slug})` }) as React.CSSProperties;
