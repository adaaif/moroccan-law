import type { Kind } from './measures';

/** What the measures read of an address, a referrer, an API path and an error's stack (the analytics review, 15 Nov
 *  2026): pure, with no import, so `node --test` runs them as they are (tests/measure.paths.test.ts). Whatever they
 *  give is checked again against the registry's rules before it is sent (rules.ts). */

/** The kinds of page, from the routes (web/src/app/App.tsx, topics/kit/TopicArea.tsx), as KINDS in
 *  back/apps/analytics/registry.py lists them; the first that matches wins. */
const KIND: [RegExp, Kind][] = [
  [/^\/$/, 'home'],
  [/^\/ma\/.+\/art_[^/]+$/, 'article'],
  [/^\/(ma\/.+|constitution(\/.*)?|texts\/[^/]+)$/, 'law'],
  [/^\/(bo\/[^/]+\/[^/]+(\/quality)?|pages\/[^/]+\/[^/]+)$/, 'issue'],
  [/^\/(library|codes|bo|new|places(\/[^/]+)?|words(\/[^/]+)?)$/, 'library'],
  [/^\/budget(\/[^/]+)?$/, 'budget'],
  [/^\/search$/, 'search'],
  [/^\/topics\/[^/]+\/journeys\/[^/]+$/, 'journey'],
  [/^\/topics\/[^/]+\/tools\/[^/]+(\/.*)?$/, 'tool'],
  [/^\/topics\/[^/]+\/review$/, 'account'],
  [/^\/(topics(\/[^/]+(\/(pages|checklists|reform)\/[^/]+|\/(reform|changes))?)?|situations(\/[^/]+)?)$/, 'topic'],
  [/^\/blog$/, 'blog'],
  [/^\/blog\/[^/]+$/, 'post'],
  [/^\/(discussion|talk|explain)(\/.*)?$|^\/(questions|people\/[^/]+)$/, 'talk'],
  [/^\/(me(\/following)?|saved|account(\/settings)?|login|register|forgot|reset|connect|auth\/google|letters\/stop|review)$/, 'account'],
  [/^\/(about|data|rules|privacy|corrections|check|ai)$/, 'page'],
  [/^\/embed\/./, 'embed'],
];

/** The kind of page an address shows («/ma/loi/65-99/art_53» is an article); 'other' for one the app does not know. */
export function kindOf(path: string): Kind {
  const p = path.length > 1 ? path.replace(/\/+$/, '') || '/' : path;
  return KIND.find(([re]) => re.test(p))?.[1] ?? 'other';
}

/** An API path reduced to its first two segments after /api («/corpus/at/ma/loi/65-99?window=30» → «/corpus/at»),
 *  lowercased: the endpoint, never the law, the search or the person it was asked for. Undefined when what is left is
 *  not a plain endpoint. */
export function endpointOf(path: string): string | undefined {
  const parts = path.split(/[?#]/)[0].split('/').filter(Boolean);
  if (parts[0] === 'api') parts.shift();
  const endpoint = `/${parts.slice(0, 2).join('/')}`.toLowerCase();
  return endpoint.length > 1 && endpoint.length <= 60 && /^\/[a-z0-9_/-]+$/.test(endpoint) ? endpoint : undefined;
}

/** A URL's host, lowercased; '' for none (an empty referrer) or one that does not read. A phone's app gives its package
 *  («android-app://com.whatsapp/» → «com.whatsapp»). */
export function hostOf(url: string): string {
  try {
    return url ? new URL(url).hostname.toLowerCase() : '';
  } catch {
    return '';
  }
}

/** Where an error was thrown: the first frame of its stack in one of this site's built files, as «assets/<file>.js:
 *  line:column» (Chrome's «at f (https://…/assets/x.js:1:2)», Firefox's and Safari's «f@https://…/assets/x.js:1:2»);
 *  undefined when no frame is ours. Only the file and its place: never the message, which Chrome writes as the
 *  stack's first line, so only lines that are frames are read. */
export function frameAt(stack: string | undefined, origin: string): string | undefined {
  const lines = (stack ?? '').split('\n');
  const v8 = lines.some((line) => /^\s+at\s/.test(line));
  for (const frame of lines) {
    if (v8 && !/^\s+at\s/.test(frame)) continue;
    const found = /(https?:\/\/[^\s()@]+?):(\d+):(\d+)/.exec(frame);
    if (!found || !found[1].startsWith(`${origin}/assets/`)) continue;
    const at = `${found[1].slice(origin.length + 1).split(/[?#]/)[0]}:${found[2]}:${found[3]}`;
    return at.length <= 80 && /^[A-Za-z0-9_./-]+:[0-9]+:[0-9]+$/.test(at) ? at : undefined;
  }
  return undefined;
}
