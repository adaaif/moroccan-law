/** How long the first page of a visit took to show its main content on this device (row 20): one load in five,
 *  the kind of page and the milliseconds, nothing else. Read by the weekly report. */
function kindOf(path: string): string {
  if (path === '/') return 'home';
  if (path.startsWith('/search')) return 'search';
  if (path.startsWith('/ma/')) return /\/art_[^/]+\/?$/.test(path) ? 'article' : 'text';
  if (/^\/bo\/[^/]+\/[^/]+/.test(path)) return 'issue';
  return 'other';
}

export function measurePageTiming(sample = 0.2) {
  if (typeof PerformanceObserver === 'undefined' || Math.random() >= sample) return;
  const kind = kindOf(location.pathname);
  let lcp = 0;
  let sent = false;
  try {
    new PerformanceObserver((list) => {
      for (const e of list.getEntries()) lcp = e.startTime;
    }).observe({ type: 'largest-contentful-paint', buffered: true });
  } catch {
    return;
  }
  const send = () => {
    if (sent || !lcp) return;
    sent = true;
    navigator.sendBeacon?.('/api/quality/timing/', new Blob([JSON.stringify({ kind, ms: Math.round(lcp) })], { type: 'application/json' }));
  };
  addEventListener('visibilitychange', () => { if (document.visibilityState === 'hidden') send(); }, { once: true });
  addEventListener('pagehide', send, { once: true });
  setTimeout(send, 15_000);
}
