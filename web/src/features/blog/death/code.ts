/** The plain arithmetic of «الإعدام في القانون المغربي» (post 20), kept apart from the drawing so it can be tested: the
 *  code's articles in runs by group, the ones that punish with death and the ones that rule on it, those written since
 *  1962, and the next marked article a key reaches. */

export type Cell = { n: string; g: string; clause?: string };
export type Marked = { n: string; kind: 'death' | 'rule'; since?: number };

/** The code's articles in runs of consecutive articles of one group, in the code's order. */
export function runs(cells: Cell[]): { g: string; cells: Cell[] }[] {
  const out: { g: string; cells: Cell[] }[] = [];
  for (const c of cells) {
    const last = out[out.length - 1];
    if (last && last.g === c.g) last.cells.push(c); else out.push({ g: c.g, cells: [c] });
  }
  return out;
}

/** How many articles punish with death, how many rule on it, and how many of the first stand in the 1962 code. */
export function tally(marked: Marked[]): { death: number; rule: number; since1962: number } {
  const death = marked.filter((m) => m.kind === 'death');
  return { death: death.length, rule: marked.length - death.length, since1962: death.filter((m) => !m.since).length };
}

/** The marked article a step of `by` reaches from `at` in the code's order (wrapping), for the arrow keys. */
export function step(order: string[], at: string, by: number): string {
  const i = order.indexOf(at);
  if (i < 0) return order[0];
  return order[(i + by + order.length) % order.length];
}

/** «70 شخصا», the people under a death sentence after a number as Arabic agrees them; French by its plural. */
export function peopleKey(n: number): 'one' | 'two' | 'few' | 'many' {
  if (n === 1) return 'one';
  if (n === 2) return 'two';
  const r = n % 100;
  return r >= 3 && r <= 10 ? 'few' : 'many';
}
