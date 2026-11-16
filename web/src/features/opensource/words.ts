/* The word checker of /open-source, as the page reads it: the shapes GET /api/quality/words/ and its next word answer,
   the calls themselves, and the few rules the checker runs by. No imports, so tests/opensource.test.ts runs it as it is.

   The calls go without the account's token: answering a word is public, and the server keeps the word, the answer and
   the time, nothing about the person (the page says so under the word). */

export type Says = 'word' | 'suggestion' | 'neither' | 'unclear';
export type Reading = { key: 'word' | 'suggestion'; text: string };
/** `mark`: where the word stands across the strip; `line`: its own line among the strip's three, down the strip. Shares. */
export type Strip = { url: string; width: number; height: number; mark: { x: number; w: number } | null;
  line?: { y: number; h: number } | null };
export type Source = {
  issue: { number: number; suffix: string; date: string } | null;
  page: number | null;
  document_id: number;
  page_index: number;
  language: string;
};
/** A doubtful word: its two readings in the order the server gives them, the words on either side of it, the cut of
 *  the printed page it stands on, and where that page is. */
export type Word = { id: number; readings: Reading[]; before: string; after: string; strip: Strip; source: Source };
/** How far everyone is: askable words, those that can be asked now, those settled, every answer, today's. */
export type Counts = { words: number; ready: number; settled: number; answers: number; today: number };

/** What a call came back with: a 429 is a pause the reader is thanked for; anything else that failed is an error. */
export type Failure = 'paused' | 'error';
export type Asked = { word: Word | null } | { failed: Failure };
export type Sent = 'ok' | 'gone' | Failure;

/** The ids sent as `not`: never more than the server reads. */
export const NOT_MAX = 100;

const failure = (status: number): Failure => (status === 429 ? 'paused' : 'error');

/** How far everyone is (public, kept a minute by the browser). */
export async function readCounts(): Promise<Counts> {
  const r = await fetch('/api/quality/words/');
  if (!r.ok) throw new Error(`words ${r.status}`);
  return (await r.json()) as Counts;
}

/** The next word to ask, never one of `not`; `{word: null}` when none is ready. */
export async function nextWord(not: number[]): Promise<Asked> {
  const q = not.length ? `?not=${not.slice(-NOT_MAX).join(',')}` : '';
  try {
    const r = await fetch(`/api/quality/words/next/${q}`, { cache: 'no-store' });
    if (!r.ok) return { failed: failure(r.status) };
    const body = (await r.json()) as { word: Word | null };
    return { word: body.word ?? null };
  } catch {
    return { failed: 'error' };
  }
}

/** One answer. A word no longer asked (another reader's answer settled it, or its page went) is `gone`: nothing to
 *  count and nothing to try again. */
export async function answer(id: number, says: Says): Promise<Sent> {
  try {
    const r = await fetch(`/api/quality/words/${id}/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ says }),
    });
    if (r.ok) return 'ok';
    if (r.status === 404) return 'gone';
    return failure(r.status);
  } catch {
    return 'error';
  }
}

/* ── The checker's state ─────────────────────────────────────────────────────────────────────────────────────────── */

/** `word`: one is on the sheet. `loading`: one is coming. `none`: none is ready. `paused` and `error`: the line that says
 *  so, which the reader presses to try again. */
export type Phase = 'loading' | 'word' | 'none' | Failure;
export type Pending = { id: number; says: Says };
export type State = {
  phase: Phase;
  /** The word on the sheet (kept behind a `paused` or `error` line, shown again once the reader tries again). */
  word: Word | null;
  /** The word after it, asked while the reader looks at this one, so a press shows it at once. */
  next: Word | null;
  /** The server said no word comes after `word`. */
  last: boolean;
  /** A GET is out. */
  asking: boolean;
  /** Answers that did not arrive: sent again when the reader presses the line. */
  retry: Pending[];
};

export type Event =
  | { type: 'asked' }
  | { type: 'got'; asked: Asked }
  | { type: 'pressed' }
  | { type: 'unsent'; answer: Pending; why: Failure }
  | { type: 'again' };

export const START: State = { phase: 'loading', word: null, next: null, last: false, asking: false, retry: [] };

export function step(s: State, e: Event): State {
  switch (e.type) {
    case 'asked':
      return { ...s, asking: true };
    case 'got': {
      const a = e.asked;
      const done = { ...s, asking: false };
      // While a line is shown (an answer did not arrive), it stays until the reader presses it.
      const waiting = s.phase === 'loading';
      if ('failed' in a) {
        // The word after this one could not come: a press will ask for it again. With none on the sheet, the line.
        return s.word || !waiting ? done : { ...done, phase: a.failed };
      }
      if (!a.word) return s.word ? { ...done, last: true } : waiting ? { ...done, phase: 'none' } : done;
      if (!s.word) return { ...done, phase: waiting ? 'word' : s.phase, word: a.word, last: false };
      if (a.word.id === s.word.id) return done;
      return { ...done, next: a.word, last: false };
    }
    case 'pressed':
      return { ...s, word: s.next, next: null, phase: s.next ? 'word' : s.last ? 'none' : 'loading' };
    case 'unsent':
      return { ...s, phase: e.why, retry: [...s.retry, e.answer] };
    case 'again':
      return { ...s, retry: [], phase: s.word ? 'word' : 'loading' };
  }
}

/** Whether to ask the server now: a word is wanted on the sheet, or the one after it. */
export const wantsWord = (s: State) =>
  !s.asking && (s.phase === 'loading' || (s.phase === 'word' && !s.next && !s.last));

/* ── What the device keeps ───────────────────────────────────────────────────────────────────────────────────────── */

/** The ids already seen, the newest last, at most a hundred: a word seen once is not asked again on this device. */
export function remember(seen: number[], id: number, max = NOT_MAX): number[] {
  return [...seen.filter((x) => x !== id), id].slice(-max);
}

/** The ids to send as `not`: the words in hand first (the one on the sheet, the one after it), then the newest seen, a
 *  hundred in all. */
export function notList(seen: number[], inHand: (number | undefined)[], max = NOT_MAX): number[] {
  const hand = [...new Set(inHand.filter((x): x is number => typeof x === 'number'))];
  const rest = seen.filter((x) => !hand.includes(x));
  return [...rest.slice(Math.max(0, rest.length - (max - hand.length))), ...hand];
}

/** The device's count and seen ids, as kept (`law.open.words`); anything unreadable is a fresh start. */
export type Kept = { mine: number; seen: number[] };
export function readKept(raw: string | null): Kept {
  try {
    const v = JSON.parse(raw ?? '') as Partial<Kept>;
    const mine = Number.isInteger(v.mine) && (v.mine as number) > 0 ? (v.mine as number) : 0;
    const seen = Array.isArray(v.seen) ? v.seen.filter((x): x is number => Number.isInteger(x)).slice(-NOT_MAX) : [];
    return { mine, seen };
  } catch {
    return { mine: 0, seen: [] };
  }
}

/* ── The words ───────────────────────────────────────────────────────────────────────────────────────────────────── */

/** A sentence cut at its {{names}}, so each number can be set in its place as the page sets figures: «… منذ 1913:
 *  {{issues}} عددا» → ['… منذ 1913: ', {name: 'issues'}, ' عددا']. */
export function slots(text: string): (string | { name: string })[] {
  return text.split(/\{\{\s*(\w+)\s*\}\}/).map((part, i) => (i % 2 ? { name: part } : part)).filter((p) => p !== '');
}

/* ── The keys and the bar ────────────────────────────────────────────────────────────────────────────────────────── */

/** The reading an arrow key chooses: the key on that side. The two keys follow the row's direction, so the first
 *  reading is on the right of an Arabic page and on the left of a French one. */
export function sideOf(key: string, dir: 'rtl' | 'ltr'): 0 | 1 | null {
  if (key !== 'ArrowLeft' && key !== 'ArrowRight') return null;
  return (key === 'ArrowLeft') === (dir === 'ltr') ? 0 : 1;
}

/** The share of the askable words settled, between 0 and 1. */
export function share(settled: number, words: number): number {
  if (!(words > 0) || !(settled > 0)) return 0;
  return Math.min(1, settled / words);
}

/** The share as the site writes one: «39٪» with the sign on the number's right in Arabic (kept so by an isolate),
 *  «39 %» in French; one decimal under 10 %. Rounded down: it says 100 only when every word is settled. */
export function percent(settled: number, words: number, lang: string): string {
  const p = share(settled, words) * 100;
  const v = p < 10 ? Math.floor(p * 10) / 10 : Math.floor(p);
  const n = new Intl.NumberFormat(lang === 'fr' ? 'fr-MA' : 'ar-MA', { maximumFractionDigits: 1 }).format(v);
  return lang === 'fr' ? `${n}\u202f%` : `\u2066${n}٪\u2069`;
}

/** An address as a reader writes it: no scheme, no slash at its end. */
export const bare = (url: string): string => url.replace(/^https?:\/\//, '').replace(/\/$/, '');
