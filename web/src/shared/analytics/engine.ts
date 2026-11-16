import { onCLS, onINP, onLCP, onTTFB } from 'web-vitals';
import { forgetDay, keepDay, lastDay, refused, staffDevice } from '@/shared/analytics/device';
import { MOST_BYTES, MOST_EVENTS, type MeasureEvent, type MeasureName, type Props } from '@/shared/analytics/measures';
import type { Noted } from '@/shared/analytics/note';
import { endpointOf, frameAt, hostOf, kindOf } from '@/shared/analytics/paths';
import { fit, fitPath } from '@/shared/analytics/rules';
import { backOf, freshOf } from '@/shared/analytics/visit';
import { todayIso } from '@/shared/services/today';

/** The measures' engine (the analytics review, 15 Nov 2026: tasks are counted, never people), loaded when the browser is
 *  idle by main.tsx, in a production build only, never part of the first load. It notes each page the app shows, the
 *  landing page's speed (web-vitals) and the errors no one caught, takes what note.ts kept waiting, fits each event to
 *  the registry's rules (rules.ts), and sends them in one batch when the page is hidden, or sooner once twenty wait.
 *
 *  A batch goes to POST /api/measure/ with `fetch`, `keepalive`, and `credentials: 'omit'`: never a cookie, never the
 *  account's token (not through shared/services/api.ts), and not with sendBeacon, which always sends cookies. A batch
 *  that fails is lost: nothing is tried again or kept on the device.
 *
 *  Nothing is sent, ever, from a browser a program drives (navigator.webdriver), nor while the reader refused on
 *  /privacy, nor under Global Privacy Control, nor from a device a team account signed in on (device.ts); a refusal, the
 *  signal and a team device also lose the day kept for the measures. */

declare const __BUILD__: string;

type Navigation = Navigator & { globalPrivacyControl?: boolean; connection?: { effectiveType?: string; saveData?: boolean } };
type Missing = Props['page.missing'];

const nav = navigator as Navigation;
const BUILD = /^[A-Za-z0-9]{1,8}$/.test(__BUILD__) ? __BUILD__ : 'unknown';
const SOON = 20;
const NETS = ['slow-2g', '2g', '3g', '4g'];

const waiting: MeasureEvent[] = [];

/** Whether this device is not counted now: the reader's refusal and Global Privacy Control lose the kept day too. */
function quiet(): boolean {
  if (nav.webdriver) return true;
  if (nav.globalPrivacyControl === true || refused() || staffDevice()) {
    forgetDay();
    return true;
  }
  return false;
}

function push(event: MeasureEvent): void {
  if (quiet()) {
    waiting.length = 0;
    return;
  }
  waiting.push(event);
  if (waiting.length >= SOON) flush();
}

/** An event as the door reads it: its address fitted, its kind from the address unless given, its properties fitted. */
function event<N extends MeasureName>(name: N, path: string, props: object | undefined, kind?: MeasureEvent['kind'], flow?: number): MeasureEvent {
  const at = fitPath(path);
  const fitted = fit(name, props as Record<string, unknown> | undefined);
  return { name, kind: kind ?? kindOf(at), path: at, ...(flow ? { flow } : {}), ...(Object.keys(fitted).length ? { props: fitted } : {}) } as MeasureEvent;
}

function send(events: MeasureEvent[]): void {
  const width = window.innerWidth;
  const body = JSON.stringify({
    lang: document.documentElement.lang === 'fr' ? 'fr' : 'ar',
    screen: width < 640 ? 'phone' : width < 1024 ? 'tablet' : 'desk',
    build: BUILD,
    events,
  });
  if (body.length > MOST_BYTES && events.length > 1) {
    const half = Math.ceil(events.length / 2);
    send(events.slice(0, half));
    send(events.slice(half));
    return;
  }
  try {
    void fetch('/api/measure/', { method: 'POST', keepalive: true, credentials: 'omit', headers: { 'Content-Type': 'application/json' }, body })
      .catch(() => { /* a measure lost never troubles the page */ });
  } catch { /* the same */ }
}

function flush(): void {
  if (quiet()) {
    waiting.length = 0;
    return;
  }
  while (waiting.length) send(waiting.splice(0, MOST_EVENTS));
}

/** The engine starts: `hand` gives it what note.ts kept and every note after. */
export function start(hand: (take: (noted: Noted) => void) => void): void {
  // A browser a program drives (a test, a crawler that runs scripts) is never counted, and nothing is read or kept:
  // what note.ts holds, and every note after, is dropped.
  if (nav.webdriver) {
    hand(() => {});
    return;
  }

  const loaded = performance.getEntriesByType('navigation')[0] as PerformanceNavigationTiming | undefined;
  const landing = loaded ? new URL(loaded.name).pathname : window.location.pathname;
  const from = hostOf(document.referrer);
  // The first page of this load starts a visit when the reader came from another site or from nowhere, not by
  // reloading it or by the back and forward buttons.
  const arrived = (!loaded || loaded.type === 'navigate' || loaded.type === 'prerender') && from !== window.location.hostname;

  // ── page.shown: each page the app shows, by its path (a tool's inputs in the query are the same page) ─────────────
  let last = '';
  let shown = 0;
  // The missing page last counted: once for each time it is shown, however often its component draws.
  let missed = '';
  const show = (path: string) => {
    if (path === last) return;
    last = path;
    missed = '';
    const first = shown++ === 0;
    const props: Props['page.shown'] = {};
    if (window.matchMedia?.('(display-mode: standalone)').matches) props.installed = true;
    if (!quiet()) {
      const today = todayIso();
      const stored = lastDay();
      const starts = first && arrived;
      if (stored === undefined) {
        // The device keeps nothing: only this load's own start is known.
        if (starts) Object.assign(props, { entry: true, back: 'unknown', fresh: 'x' });
      } else if (starts || stored !== today) {
        // A visit starts, or a tab left open is used on a new Moroccan day: that is a visit too, from no site.
        Object.assign(props, { entry: true, back: backOf(stored, today), fresh: freshOf(stored, today) });
        keepDay(today);
      }
      if (props.entry && starts && from) props.ref = from;
    }
    push(event('page.shown', path, props));
  };
  show(landing);
  if (window.location.pathname !== landing) show(window.location.pathname);    // reached before the engine came
  for (const name of ['pushState', 'replaceState'] as const) {
    const original = history[name].bind(history);
    history[name] = (...args: Parameters<History['pushState']>) => {
      original(...args);
      show(window.location.pathname);
    };
  }
  window.addEventListener('popstate', () => show(window.location.pathname));

  // ── page.speed: the landing page's, once, when it is first hidden (web-vitals' values are final then) ───────────────
  const vitals: Props['page.speed'] = {};
  onLCP((m) => { vitals.lcp = m.value; });
  onINP((m) => { vitals.inp = m.value; });
  onCLS((m) => { vitals.cls = m.value; });
  onTTFB((m) => { vitals.ttfb = m.value; });
  let timed = false;
  const speed = () => {
    if (timed || (vitals.lcp === undefined && vitals.ttfb === undefined)) return;
    timed = true;
    const link = nav.connection;
    const net = link?.effectiveType && NETS.includes(link.effectiveType) ? link.effectiveType : '';
    push(event('page.speed', landing, { ...vitals, net, ...(link ? { saver: Boolean(link.saveData) } : {}) }));
  };

  // ── app.error: what no one caught, by its name and the place in a built file; never its message ────────────────────
  const errors = new Set<string>();
  const caught = (error: unknown, fallback?: string) => {
    if (errors.size >= 5) return;
    const name = error instanceof Error && /^[A-Za-z]{1,40}$/.test(error.name) ? error.name : 'Error';
    const at = frameAt(error instanceof Error ? error.stack : fallback, window.location.origin);
    const key = `${name} ${at ?? ''}`;
    if (errors.has(key)) return;
    errors.add(key);
    push(event('app.error', window.location.pathname, { error: name, at }));
  };
  window.addEventListener('error', (e) => caught(e.error, e.filename ? `@${e.filename}:${e.lineno}:${e.colno}` : undefined));
  window.addEventListener('unhandledrejection', (e) => caught(e.reason));

  // ── what note.ts kept, and every note after it ─────────────────────────────────────────────────────────────────────
  hand((noted) => {
    let props = noted.props as Record<string, unknown> | undefined;
    if (noted.name === 'api.failed') {
      // api.ts notes the path it asked; only its endpoint leaves.
      const endpoint = endpointOf(String(props?.endpoint ?? ''));
      if (!endpoint || endpoint.startsWith('/measure')) return;
      props = { ...props, endpoint };
    } else if (noted.name === 'page.missing') {
      if (noted.path === missed) return;
      missed = noted.path;
      // A dead link on this site (a page reached inside the app, or from one of its pages), else where it was.
      const missing: Missing = {};
      if (fitPath(noted.path) !== fitPath(landing) || from === window.location.hostname) missing.inside = true;
      else if (from) missing.ref = from;
      props = missing;
    }
    push(event(noted.name, noted.path, props, noted.kind, noted.flow));
  });

  // ── one batch when the page is hidden; web-vitals reads its final values first (its listener is on the window, in
  //    the capture phase, before this one on the document) ─────────────────────────────────────────────────────────
  const leave = () => { speed(); flush(); };
  document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'hidden') leave(); });
  window.addEventListener('pagehide', leave);
}
