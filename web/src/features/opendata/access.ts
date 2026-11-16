/* Access on request, as the pages read it: the shapes /api/access/ and /api/open/ answer, and the few rules the pages
   draw by. No imports, so tests/access.test.ts runs it as it is. */

export type Position = 'closed' | 'request' | 'open';
export type Limits = { minute: number; calls: number; articles: number };
export type SizeName = 'try' | 'app' | 'partner';

export type RequestRow = {
  id: number;
  state: 'waiting' | 'more' | 'accepted' | 'declined';
  name: string;
  kind: string;
  purpose: string;
  wants_api: boolean;
  wants_data: boolean;
  runs_at: string;
  volume: string;
  commercial: boolean;
  terms: string;
  asked: string;
  answer: string;
  reason: string;
  created_at: string;
  decided_at: string | null;
  /** The day a declined account may ask again, while it is still ahead. */
  ask_again_on: string | null;
  /** The day the answer is due, while the request waits for the staff. */
  due_on: string | null;
  /** For a request to change an access already held: that access's id. */
  change_of: number | null;
  /** The size a change request asks for; '' keeps the size held. */
  wanted_size: '' | SizeName;
};

export type AccessRow = {
  id: number;
  api: boolean;
  data: boolean;
  size: SizeName;
  limits: Limits;
  ends_on: string;
  state: 'live' | 'ended';
  ended_reason: string;
  created_at: string;
};

/** GET /api/access/: where access on request stands, and the account's newest request and access (null for a visitor). */
export type AccessBody = {
  position: Position;
  terms: string;
  answer_days: number;
  sizes: Record<'try' | 'app', Limits>;
  request: RequestRow | null;
  access: AccessRow | null;
  /** For a superuser, the requests waiting for an answer; null for everyone else. */
  desk?: { waiting: number } | null;
};

export type KeyRow = { id: number; name: string; prefix: string; created_at: string; last_used_on: string | null };
export type Day = { day: string; calls: number; articles: number };
/** GET /api/access/keys/: the live keys (never a key itself), the limits, today's use and the last 30 days with use. */
export type Keys = { keys: KeyRow[]; limits: Limits; today: { calls: number; articles: number }; days: Day[] };
/** POST /api/access/keys/: the only answer that holds the key. */
export type NewKey = { key: string; id: number; name: string; prefix: string };

export type EditionFile = { bytes: number; sha256: string; lines?: number; entries?: number };
/** GET /api/open/: the newest edition's manifest, its own hash, and every edition's dated hash, newest first. */
export type Manifest = {
  date: string;
  texts: number;
  articles: number;
  versions: number;
  files: Record<string, EditionFile>;
  sha256: string;
  editions: { date: string; sha256: string }[];
};

/** The answers the form offers, as the server's codes. */
export const KINDS = ['person', 'school', 'newsroom', 'association', 'public', 'company'] as const;
export const VOLUMES = ['small', 'medium', 'large'] as const;
/** Why a request may be declined, and why an access may end. */
export const REASONS = ['unclear', 'identity', 'scope', 'terms', 'later'] as const;
export const ENDED = ['asked', 'terms', 'leaked', 'unused', 'expired', 'account'] as const;

/** The most characters each typed answer holds, as the server checks them. */
export const MOST = { name: 120, purpose: 600, runs_at: 200, answer: 600, key: 60, why: 600 } as const;
/** The live keys an access may hold (the server's ACCESS_KEYS): one can replace the other without a break. */
export const KEYS_MOST = 2;
/** The three sizes, smallest first. */
export const SIZES = ['try', 'app', 'partner'] as const;
/** The terms' date is their version: the words of /data/terms are these terms. */
export const TERMS_DATE = '2026-11-16';

/** The files that hold the data, in the order the page lists them; the files that describe an edition go to anyone. */
export const DATA_FILES = ['texts.jsonl.gz', 'versions.jsonl.gz', 'french.jsonl.gz', 'changes.jsonl.gz', 'issues.jsonl.gz',
  'aliases.jsonl.gz', 'akn.zip'];
export const DESCRIBE_FILES = ['manifest.json', 'README.md', 'schema.json', 'CHANGELOG.md', 'LICENCE.txt'];

/** Where an account stands, which decides what its door and its page «وصولي» say first:
 *  - `none`: nothing asked (or a visitor);
 *  - `more`: the staff asked a line and waits for the account's answer (a change request's too, beside a live access);
 *  - `waiting`: a request waits for the staff;
 *  - `declined`: declined, and the day it may ask again is still ahead;
 *  - `again`: declined, and it may ask again now;
 *  - `live`: it holds an access (a change request waiting or declined beside it is said by `changing`);
 *  - `ended`: its access ended; it may ask again. */
export type Standing = 'none' | 'waiting' | 'more' | 'declined' | 'again' | 'live' | 'ended';

export function standing(body: Pick<AccessBody, 'request' | 'access'>): Standing {
  const { request, access } = body;
  // A question waits for the account whatever it holds: it is the one thing to do.
  if (request?.state === 'more') return 'more';
  if (access?.state === 'live') return 'live';
  if (request?.state === 'waiting') return 'waiting';
  // The newest request is newer than any access (an access comes from an accepted request): a decline after an
  // ended access is what stands.
  if (request?.state === 'declined') return request.ask_again_on ? 'declined' : 'again';
  if (access?.state === 'ended') return 'ended';
  return 'none';
}

/** Whether the form may be sent from where the account stands. */
export const mayAsk = (s: Standing) => s === 'none' || s === 'again' || s === 'ended';

/** The request to change the live access, when it is the account's newest request (waiting, asked, declined or
 *  accepted); null otherwise. */
export function changing(body: Pick<AccessBody, 'request' | 'access'>): RequestRow | null {
  const { request, access } = body;
  return access?.state === 'live' && request?.change_of != null && request.change_of === access.id ? request : null;
}

/** Whether a holder may ask to change its access now, as the server decides it: a live access, requests not closed, no
 *  request open, and no decline in the last 30 days. */
export function mayChange(body: Pick<AccessBody, 'position' | 'request' | 'access'>): boolean {
  const { position, request, access } = body;
  if (access?.state !== 'live' || position === 'closed') return false;
  if (request?.state === 'waiting' || request?.state === 'more') return false;
  return !request?.ask_again_on;
}

/** What a change request asks: what the access is to hold afterwards, a size ('' keeps the one held), and why. */
export type Change = { api: boolean; data: boolean; size: '' | SizeName; why: string };

/** A change request's answers, checked as the server checks them before it is asked: the fields first, then whether it
 *  asks for anything the access does not hold already (a partner may ask for the partner size again: its numbers are
 *  its own). */
export function checkChange(held: Pick<AccessRow, 'api' | 'data' | 'size'>, f: Change): [string, string][] {
  const out: [string, string][] = [];
  if (!f.api && !f.data) out.push(['wants', 'required']);
  const why = f.why.trim();
  if (!why) out.push(['why', 'required']);
  else if (why.length > MOST.why) out.push(['why', 'too_long']);
  if (out.length) return out;
  const sameSize = f.size === '' || (f.size === held.size && held.size !== 'partner');
  if (f.api === held.api && f.data === held.data && sameSize) out.push(['change', 'nothing']);
  return out;
}

/** The body POST /api/access/change/ takes. */
export const changeBody = (f: Change) => ({ wants_api: f.api, wants_data: f.data, size: f.size, why: f.why });

/** The two files most holders come for; the other five open on demand. */
export const BIG_FILES = ['texts.jsonl.gz', 'akn.zip'];

/** The bytes of an edition's data files. */
export const editionBytes = (m: Pick<Manifest, 'files'>) =>
  DATA_FILES.reduce((n, name) => n + (m.files[name]?.bytes ?? 0), 0);

/** A day `n` days after an ISO day (before, when negative), counted on the calendar alone. */
export function shift(day: string, n: number): string {
  const [y, m, d] = day.split('-').map(Number);
  return new Date(Date.UTC(y, m - 1, d + n)).toISOString().slice(0, 10);
}

/** The last `n` days up to `today`, oldest first, each with its use; a day without use counts nothing. */
export function lastDays(days: Day[], today: string, n = 30): Day[] {
  const used = new Map(days.map((d) => [d.day, d]));
  return Array.from({ length: n }, (_, i) => {
    const day = shift(today, i - n + 1);
    return used.get(day) ?? { day, calls: 0, articles: 0 };
  });
}

/** A share of a limit, 0 to 100, never past it. */
export const share = (used: number, limit: number) => (limit > 0 ? Math.min(100, (used / limit) * 100) : 0);

/** A file's size in kB or MB, kept left to right inside an Arabic line. */
export const size = (n: number) =>
  `⁦${n < 1e6 ? `${Math.max(1, Math.round(n / 1e3))} kB` : `${(n / 1e6).toFixed(1)} MB`}⁩`;

/** A file's name as a key of the words («texts.jsonl.gz» → «texts_jsonl_gz»). */
export const fileKey = (name: string) => name.replace(/\W/g, '_');

/** The form's answers, checked as the server checks them, before it is asked: the fields to say and their codes. The
 *  server checks again and has the last word. */
export type Form = {
  name: string; kind: string; purpose: string; wants_api: boolean; wants_data: boolean; runs_at: string;
  volume: string; commercial: boolean | null; terms: boolean; consent: boolean;
};

export function check(f: Form): [string, string][] {
  const out: [string, string][] = [];
  const name = f.name.split(/\s+/).filter(Boolean).join(' ');
  if (!name) out.push(['name', 'required']);
  else if (name.length > MOST.name) out.push(['name', 'too_long']);
  if (!f.kind) out.push(['kind', 'required']);
  const purpose = f.purpose.trim();
  if (!purpose) out.push(['purpose', 'required']);
  else if (purpose.length > MOST.purpose) out.push(['purpose', 'too_long']);
  if (!f.wants_api && !f.wants_data) out.push(['wants', 'required']);
  if (f.runs_at.trim().length > MOST.runs_at) out.push(['runs_at', 'too_long']);
  if (!f.volume) out.push(['volume', 'required']);
  if (f.commercial === null) out.push(['commercial', 'required']);
  if (!f.terms) out.push(['terms', 'required']);
  if (!f.consent) out.push(['consent', 'required']);
  return out;
}

/** The body POST /api/access/request/ takes: the terms sent are the version GET /api/access/ gave. */
export function body(f: Form, terms: string) {
  return {
    name: f.name, kind: f.kind, purpose: f.purpose, wants_api: f.wants_api, wants_data: f.wants_data,
    runs_at: f.runs_at, volume: f.volume, commercial: f.commercial, terms: f.terms ? terms : '', consent: f.consent,
  };
}

/** What the examples ask, in the reader's language: the search reads both, and a reference is read as it is written. */
const ASKED = {
  ar: { q: 'الحد الأدنى للأجر', reference: 'المادة 53 من القانون رقم 65.99' },
  fr: { q: 'salaire minimum', reference: 'article 53 de la loi n° 65-99' },
};

/** Example curl lines for the six reads and the edition, on the site's own address. `since` is a day a month back, so
 *  the example stays inside the window the changes read allows; `apiKey` is the key to send, or its placeholder. */
export function examples(origin: string, since: string, lang = 'ar', apiKey = '$API_KEY'): Record<string, string> {
  const key = `-H "X-Api-Key: ${apiKey}"`;
  const asked = lang === 'fr' ? ASKED.fr : ASKED.ar;
  return {
    search: `curl -G ${key} --data-urlencode "q=${asked.q}" ${origin}/api/v1/search`,
    texts: `curl ${key} ${origin}/api/v1/texts/ma/loi/65-99/art_53`,
    articles: `curl ${key} "${origin}/api/v1/articles/ma/loi/65-99?start=51&count=5"`,
    references: `curl ${key} -H "Content-Type: application/json" -d '{"references": ["${asked.reference}"]}' ${origin}/api/v1/references`,
    bulletin: `curl ${key} ${origin}/api/v1/bulletin/`,
    changes: `curl ${key} "${origin}/api/v1/changes?since=${since}"`,
    edition: `curl -OJ ${key} ${origin}/api/open/latest/texts.jsonl.gz`,
  };
}

/** A new key's first call, the key already in it: a search when the access holds the API, else the edition's main
 *  file. */
export const firstCall = (origin: string, apiKey: string, held: Pick<AccessRow, 'api'>, lang = 'ar') =>
  examples(origin, '', lang, apiKey)[held.api ? 'search' : 'edition'];

/** The six reads of /api/v1/: their key in the words, and their method and address as a program writes it. */
export const READS: [string, 'GET' | 'POST', string][] = [
  ['search', 'GET', '/api/v1/search?q='],
  ['texts', 'GET', '/api/v1/texts/<path>'],
  ['articles', 'GET', '/api/v1/articles/<path>?start=&count=&on=&french='],
  ['references', 'POST', '/api/v1/references'],
  ['bulletin', 'GET', '/api/v1/bulletin/<issue>'],
  ['changes', 'GET', '/api/v1/changes?since='],
];
