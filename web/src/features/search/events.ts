/** What a reader did with what a search answered (B3 of the search plan): which answer it led to and how long it stayed
 *  open, whether it was saved, shared or copied, and whether the reader found it. Each says only the search's own
 *  anonymous log row and the answer's address: nothing about the reader. Loaded by the search page, and by an article's
 *  buttons only when used, so a first visit downloads none of it. */

const READING = 'law.search.reading';
const RECENT_MS = 30 * 60 * 1000;

type Reading = { log: number; path?: string; at: number };

function post(body: Record<string, unknown>, url = '/api/search/event/') {
  void fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, keepalive: true, body: JSON.stringify(body) })
    .catch(() => undefined);
}

function recent(): Reading | null {
  try {
    const r = JSON.parse(sessionStorage.getItem(READING) ?? 'null') as Reading | null;
    return r && Date.now() - r.at < RECENT_MS ? r : null;
  } catch {
    return null;
  }
}

/** Which answer a search led to (row 20): its place (0 for the citation card) and its address. */
export function noteOpened(log: number | null, rank: number, path?: string) {
  if (log === null) return;
  post({ log, rank, path }, '/api/search/opened/');
  try { sessionStorage.setItem(READING, JSON.stringify({ log, path, at: Date.now() })); } catch { /* nothing kept */ }
}

/** How long the answer stayed open: said when the reader comes back to the answers, or leaves the site. */
export function finishReading() {
  const r = recent();
  try { sessionStorage.removeItem(READING); } catch { /* nothing kept */ }
  if (r?.path) post({ log: r.log, kind: 'read', path: r.path, seconds: Math.round((Date.now() - r.at) / 1000) });
}

/** An answer saved, shared or copied within half an hour of the search that led to it, in this tab. */
export function noteFromSearch(kind: 'saved' | 'shared' | 'copied', path: string) {
  const r = recent();
  if (r) post({ log: r.log, kind, path });
}

/** «لقيت الجواب؟» */
export function noteFound(log: number | null, found: boolean) {
  if (log !== null) post({ log, kind: found ? 'found' : 'not_found' });
}

if (typeof window !== 'undefined') window.addEventListener('pagehide', finishReading);
