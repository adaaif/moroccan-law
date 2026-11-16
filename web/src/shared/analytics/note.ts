import type { Kind, MeasureName, Props } from './measures';

/** What the site counts, noted where it happens (the analytics review, 15 Nov 2026: tasks are counted, never people). A
 *  few bytes, safe in the first load: a note waits in memory until the engine (engine.ts, loaded when the browser is
 *  idle, in a production build only) takes it, checks it against the registry and sends it with the page's others.
 *  Nothing is noted where there is no window (the prerender, the drawing service), and nothing waits on the device. */

export type Noted = { name: MeasureName; props?: object; path: string; kind?: Kind; flow?: number };
type Take = (noted: Noted) => void;

// Until the engine comes. A browser a program drives has them dropped by the engine; a development build loads no engine,
// and keeps its few in memory.
const waiting: Noted[] = [];
let take: Take = (noted) => { waiting.push(noted); };

/** One measure, on this page unless `path` says another. */
export function note<N extends MeasureName>(name: N, props?: Props[N], opts: { path?: string; kind?: Kind; flow?: number } = {}): void {
  if (typeof window !== 'undefined') take({ name, props, path: window.location.pathname, ...opts });
}

/** The engine takes what waited, then every note as it comes. */
export function hand(to: Take): void {
  take = to;
  for (const noted of waiting.splice(0)) to(noted);
}
