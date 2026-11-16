import type { Props } from '@/shared/analytics/measures';
import { note } from '@/shared/analytics/note';

/** One step on a tool's page (M1 of the road tools review; since the analytics review of 15 Nov 2026 a `tool.step`
 *  measure, shared/analytics): the page without its query and what happened there — opened, the reader's first answer,
 *  the tool's first result for it, shared, a picture, a reminder, read aloud, a scene answered, a step ticked, a door
 *  taken from the search. Never an input. Each opening of a tool is one flow: a random number drawn in memory when it
 *  opens, which its later steps carry, never kept. The page's kind is the engine's to read from the page. */
export type UseEvent = 'open' | 'share' | 'picture' | 'remind' | 'listen' | 'right' | 'wrong' | 'door' | 'tick' | 'answered' | 'result';

type Step = NonNullable<Props['tool.step']['step']>;

/** The counter's words as the measure says them. */
const STEP: Partial<Record<UseEvent, Step>> = { open: 'opened', share: 'shared' };
/** Steps counted once in an opening. */
const ONCE = new Set<Step>(['answered', 'result', 'copied', 'saved']);

let flow: { page: string; id: number; done: Set<Step> } | null = null;

/** The page a step counts on, as the topics' counter has always written it: the address without its last slash, a
 *  tool's own sub-addresses (the inheritance calculator's families) counted as the tool; null for a page that is
 *  neither a topic's nor the search's. */
export function toolPage(path: string): string | null {
  const page = path.replace(/\/+$/, '').replace(/^(\/topics\/[a-z-]+\/tools\/[a-z-]+)\/.*$/, '$1');
  return /^\/topics\/|^\/search$/.test(page) ? page : null;
}

export function noteUse(event: UseEvent, path?: string) {
  if (typeof window === 'undefined') return;
  const page = toolPage(path ?? window.location.pathname);
  if (!page) return;
  const step = STEP[event] ?? (event as Step);
  // A flow is a whole number from 1 to 2^53 − 1, within the registry's FLOW_MOST.
  if (step === 'opened') flow = { page, id: 1 + Math.floor(Math.random() * Number.MAX_SAFE_INTEGER), done: new Set() };
  const open = flow?.page === page ? flow : null;
  if (ONCE.has(step)) {
    // Only in an opening of a tool, once each, and a result only once the reader answered: a tool shows an example or
    // a prompt before anything is asked of it.
    if (!open || open.done.has(step) || (step === 'result' && !open.done.has('answered'))) return;
    open.done.add(step);
  }
  note('tool.step', { step }, { path: page, flow: open?.id });
}
