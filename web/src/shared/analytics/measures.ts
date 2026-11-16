// Written by `manage.py write_measure_types` from back/apps/analytics/registry.py: do not edit it by hand.
// Change the registry, run the command and commit both; a backend test fails while they differ.

/** The kinds of page an event is shown on (registry.KINDS says which addresses each holds). */
export const KINDS = ['home', 'law', 'article', 'issue', 'library', 'budget', 'search', 'topic', 'journey', 'tool', 'blog', 'post', 'talk', 'account', 'page', 'embed', 'other'] as const;
export type Kind = (typeof KINDS)[number];
export const LANGS = ['ar', 'fr'] as const;
export type Lang = (typeof LANGS)[number];
/** The width the browser saw: under 640 px, under 1024 px, wider. */
export const SCREENS = ['phone', 'tablet', 'desk'] as const;
export type Screen = (typeof SCREENS)[number];

/** The door: events a batch, bytes a body, an address without its query, a build, a flow. */
export const MOST_EVENTS = 40;
export const MOST_BYTES = 16384;
export const PATH = '^/[A-Za-z0-9_\\-./]{0,199}$';
export const BUILD = '^[A-Za-z0-9]{1,8}$';
export const FLOW_MOST = 9007199254740992;
/** page.shown's properties that only a visit's first page carries. */
export const ENTRY_ONLY = ['source', 'back'] as const;

/** Each measure's properties, every one optional. */
export interface Props {
  'page.shown': {
    entry?: boolean;
    source?: 'direct' | 'search' | 'assistant' | 'social' | 'site';
    /** ^[a-z0-9-]+(\.[a-z0-9-]+)+$, at most 60 characters, lowercased */
    ref?: string;
    back?: 'first' | 'today' | 'day' | 'week' | 'month' | 'more' | 'unknown';
    fresh?: 'none' | 'd' | 'dw' | 'dm' | 'dwm' | 'x';
    installed?: boolean;
  };
  'tool.step': {
    step?: 'opened' | 'answered' | 'result' | 'copied' | 'shared' | 'saved' | 'picture' | 'remind' | 'listen' | 'right' | 'wrong' | 'door' | 'tick';
  };
  'page.speed': {
    /** from 0 to 60000, rounded to 50 */
    lcp?: number;
    /** from 0 to 60000, rounded to 50 */
    inp?: number;
    /** from 0 to 60000, rounded to 50 */
    ttfb?: number;
    /** from 0 to 5, rounded to 0.01 */
    cls?: number;
    net?: 'slow-2g' | '2g' | '3g' | '4g' | '';
    saver?: boolean;
  };
  'app.error': {
    /** ^[A-Za-z]{1,40}$, at most 40 characters */
    error?: string;
    /** ^[A-Za-z0-9_./-]+:[0-9]+:[0-9]+$, at most 80 characters */
    at?: string;
  };
  'api.failed': {
    /** ^/[a-z0-9_/-]+$, at most 60 characters */
    endpoint?: string;
    /** from 0 to 599, rounded to 1 */
    status?: number;
  };
  'page.missing': {
    source?: 'direct' | 'search' | 'assistant' | 'social' | 'site';
    /** ^[a-z0-9-]+(\.[a-z0-9-]+)+$, at most 60 characters, lowercased */
    ref?: string;
    inside?: boolean;
  };
}
export type MeasureName = keyof Props;
export const MEASURES: readonly MeasureName[] = ['page.shown', 'tool.step', 'page.speed', 'app.error', 'api.failed', 'page.missing'];
export type MeasureEvent = {
  [N in MeasureName]: { name: N; kind: Kind; path: string; flow?: number; props?: Props[N] };
}[MeasureName];
export interface Batch {
  lang: Lang;
  screen: Screen;
  build: string;
  events: MeasureEvent[];
}

/** Each property's rule as the door checks it; a pattern is a regular expression's source. */
export const RULES = {
  'page.shown': {
    entry: { type: 'bool' },
    source: { type: 'choice', values: ['direct', 'search', 'assistant', 'social', 'site'] },
    ref: { type: 'pattern', pattern: '^[a-z0-9-]+(\\.[a-z0-9-]+)+$', most: 60, lower: true },
    back: { type: 'choice', values: ['first', 'today', 'day', 'week', 'month', 'more', 'unknown'] },
    fresh: { type: 'choice', values: ['none', 'd', 'dw', 'dm', 'dwm', 'x'] },
    installed: { type: 'bool' },
  },
  'tool.step': {
    step: { type: 'choice', values: ['opened', 'answered', 'result', 'copied', 'shared', 'saved', 'picture', 'remind', 'listen', 'right', 'wrong', 'door', 'tick'] },
  },
  'page.speed': {
    lcp: { type: 'number', lo: 0, hi: 60000, step: 50 },
    inp: { type: 'number', lo: 0, hi: 60000, step: 50 },
    ttfb: { type: 'number', lo: 0, hi: 60000, step: 50 },
    cls: { type: 'number', lo: 0, hi: 5, step: 0.01 },
    net: { type: 'choice', values: ['slow-2g', '2g', '3g', '4g', ''] },
    saver: { type: 'bool' },
  },
  'app.error': {
    error: { type: 'pattern', pattern: '^[A-Za-z]{1,40}$', most: 40, lower: false },
    at: { type: 'pattern', pattern: '^[A-Za-z0-9_./-]+:[0-9]+:[0-9]+$', most: 80, lower: false },
  },
  'api.failed': {
    endpoint: { type: 'pattern', pattern: '^/[a-z0-9_/-]+$', most: 60, lower: false },
    status: { type: 'number', lo: 0, hi: 599, step: 1 },
  },
  'page.missing': {
    source: { type: 'choice', values: ['direct', 'search', 'assistant', 'social', 'site'] },
    ref: { type: 'pattern', pattern: '^[a-z0-9-]+(\\.[a-z0-9-]+)+$', most: 60, lower: true },
    inside: { type: 'bool' },
  },
} as const;
