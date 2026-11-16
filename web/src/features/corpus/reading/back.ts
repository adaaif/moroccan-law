/** Where the reader was in a law, kept for the history entry they left it from, in this tab only (PX1 of
 *  the where-it-trips review): back from a page opened in the law (its printed page, a discussion, a word, a cited law) puts them there
 *  again. Before, the law opened again at its address's article, the browser put back a scroll past the window's end,
 *  and the window loaded on and on until the whole code was on the page. Written by `KeepPlace` (Place.tsx).
 *  `path` is the entry's own address: a tab's first entry has the same key at every load («default»), and a link to
 *  another article of the law, opened in the tab, is not a return to the place kept there. */
export const BACK = 'law.back.';

export type Kept = { path: string; eid: string; dy: number };

export function keptBack(key: string): Kept | null {
  try {
    return JSON.parse(sessionStorage.getItem(BACK + key) ?? 'null') as Kept | null;
  } catch {
    return null;
  }
}
