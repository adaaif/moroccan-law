/* The access desk (/data/desk), as the page reads it: the shapes /api/access/desk/ answers, and the rules the page says
   things by (the day an answer is due, what an act did, what accepting or changing will give, a door's name). No imports,
   so tests/desk.test.ts runs it as it is; each sentence is made with the `t` it is given, in the desk's words. */

export type Size = 'try' | 'app' | 'partner';
export type Limits = { minute: number; calls: number; articles: number };
export type Position = 'closed' | 'request' | 'open';
export type RequestState = 'waiting' | 'more' | 'accepted' | 'declined';
/** `t` from i18next, or any function that says a key in words. */
export type T = (key: string, options?: Record<string, unknown>) => string;

/** A request as the desk's lists show it. */
export type RequestRow = {
  id: number;
  name: string;
  kind: string;
  username: string;
  wants_api: boolean;
  wants_data: boolean;
  volume: string;
  commercial: boolean;
  state: RequestState;
  created_at: string;
  waiting_since: string;
  due_on: string | null;
  /** Working days until `due_on`: 0 on the day, negative once it passed; null unless it waits for the staff. */
  days_left: number | null;
  /** It waits again after its account answered the line asked. */
  answered: boolean;
  /** The access a change request asks to change. */
  change_of: number | null;
  wanted_size: '' | Size;
  reason: string;
};

/** An access as the desk's lists show it. */
export type AccessRow = {
  id: number;
  name: string;
  kind: string;
  username: string;
  api: boolean;
  data: boolean;
  size: Size;
  limits: Limits;
  ends_on: string;
  state: 'live' | 'ended';
  ended_reason: string;
  last_used_on: string | null;
  /** Its live keys. */
  keys: number;
  calls_30: number;
  articles_30: number;
  /** Calls a day over 30 days, oldest first, today last. */
  spark: number[];
};

/** One act on a request or an access. */
export type DeskEvent = {
  at: string;
  by: string | null;
  act: 'sent' | 'answered' | 'asked' | 'accepted' | 'declined' | 'changed' | 'renewed' | 'ended' | 'key_made' | 'key_ended';
  request: number | null;
  access: number | null;
  /** The name given in the request behind it. */
  name: string;
  details: Record<string, unknown>;
};

export type Figures = {
  received: number; accepted: number; declined: number; median_days: number | null; waiting: number;
  oldest_days: number | null; ending: number; live: number; keys: number;
};

/** How the programme stands. */
export type Programme = {
  position: Position;
  letter_to: string[];
  terms: string;
  answer_days: number;
  sizes: Record<'try' | 'app', Limits>;
  edition: { date: string; sha256: string } | null;
  next_edition_on: string;
};

/** GET desk/: the state, what waits, what ends soon, the month's figures. */
export type Overview = { state: Programme; waiting: RequestRow[]; asked: RequestRow[]; ending: AccessRow[]; figures: Figures };

export type ListPage<Row, State extends string> = { results: Row[]; next: string | null; counts: Record<State, number> };
export const REQUEST_FILTERS = ['waiting', 'more', 'accepted', 'declined', 'all'] as const;
export const ACCESS_FILTERS = ['live', 'ending', 'ended', 'unused', 'all'] as const;
export type RequestFilter = (typeof REQUEST_FILTERS)[number];
export type AccessFilter = (typeof ACCESS_FILTERS)[number];

/** The account behind a request or an access, with its standing in the discussion. */
export type Account = {
  id: number; username: string; display_name: string; email: string; email_proven: boolean; joined: string;
  days: number; posts: number; removed: number; paused: boolean;
};

export type Grant = { api: boolean; data: boolean; size: Size; ends_on: string | null };

/** GET desk/requests/<id>/: what deciding needs. */
export type RequestSheet = {
  request: RequestRow & {
    purpose: string; runs_at: string; terms: string; asked: string; answer: string; decided_at: string | null;
    decided_by: string | null; holds: { api: boolean; data: boolean; size: Size } | null;
  };
  account: Account;
  earlier: { id: number; state: RequestState; created_at: string; decided_at: string | null; reason: string;
             wants_api: boolean; wants_data: boolean; change_of: number | null }[];
  access: AccessRow | null;
  proposed: Grant;
  questions: string[];
  history: DeskEvent[];
  may_decide: boolean;
};

export type KeyRow = { id: number; name: string; prefix: string; created_at: string; last_used_on: string | null; ended_at: string | null };
export type UseDay = { day: string; calls: number; articles: number };

/** GET desk/accesses/<id>/: an access with its use, keys, downloads and history. */
export type AccessSheet = {
  access: AccessRow & { created_at: string; renewed_at: string | null; ended_at: string | null; ended_by: string | null };
  request: { id: number; name: string; kind: string; purpose: string; runs_at: string; volume: string; commercial: boolean; terms: string };
  account: Account;
  keys: KeyRow[];
  days: (UseDay & { doors: Record<string, number>; limits: Record<string, number> })[];
  doors: Record<string, number>;
  downloads: { edition: string; file: string; by: 'account' | 'key'; at: string }[];
  history: DeskEvent[];
};

/** GET desk/use/: use across every access. */
export type Use = {
  days: UseDay[];
  doors: Record<string, number>;
  busiest: { access: number; name: string; calls: number; articles: number }[];
  limited_today: { access: number; name: string; limits: Partial<Limits> }[];
  totals: { calls: number; articles: number; accesses: number };
};

/** GET desk/editions/. */
export type Editions = {
  editions: {
    date: string; sha256: string; texts: number | null; articles: number | null; versions: number | null;
    bytes: number | null; on_disk: boolean; files: { name: string; bytes: number; taken: number }[];
    downloads: { access: number; name: string; file: string; by: 'account' | 'key'; at: string }[];
  }[];
  next_on: string;
};

/** A letter exactly as its person will read it. */
export type Letter = { language: string; subject: string; body: string };

/** The desk's five parts, each an address (`?part=`); the first is the page itself. */
export const PARTS = ['waiting', 'accesses', 'use', 'editions', 'log'] as const;
export type Part = (typeof PARTS)[number];
export const partOf = (value: string | null): Part => (PARTS as readonly string[]).includes(value ?? '') ? (value as Part) : 'waiting';

export const SIZES: Size[] = ['try', 'app', 'partner'];
/** Why a request may be declined, and why the staff may end an access. */
export const REASONS = ['unclear', 'identity', 'scope', 'terms', 'later'] as const;
export const END_REASONS = ['terms', 'leaked', 'unused'] as const;
/** The doors a call is counted on (back/apps/opendata/services/usage.py DOORS), in the order the page names them. */
export const DOORS = ['v1.search', 'v1.text', 'v1.articles', 'v1.references', 'v1.bulletin', 'v1.changes', 'mcp', 'site', 'open'];
/** The most characters a line asked holds, as the server checks it. */
export const LINE_MOST = 300;

/** Text a person typed, or a username, kept in its own direction inside a sentence. */
export const iso = (s: string) => `\u2068${s}\u2069`;

const locale = (lang: string) => (lang === 'fr' ? 'fr-MA' : 'ar-MA');
const ZONE = 'Africa/Casablanca';

/** The calendar day a moment falls on in Morocco, as YYYY-MM-DD. */
export function dayIn(at: Date): string {
  const parts = new Intl.DateTimeFormat('en-CA', { timeZone: ZONE, year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(at);
  const get = (type: string) => parts.find((p) => p.type === type)?.value ?? '';
  return `${get('year')}-${get('month')}-${get('day')}`;
}

/** A day (YYYY-MM-DD) or a moment, said as a date of Morocco's calendar: «16 نونبر 2027», «16 novembre 2027». */
export function dateOf(value: string | null | undefined, lang: string): string {
  if (!value) return '';
  const day = value.length > 10 ? dayIn(new Date(value)) : value;
  return new Intl.DateTimeFormat(locale(lang), { dateStyle: 'long', timeZone: 'UTC' }).format(new Date(`${day}T00:00:00Z`));
}

/** A day said in words, or the dash. */
export const dayOr = (value: string | null | undefined, lang: string) => (value ? dateOf(value, lang) : '—');

/** A moment with its hour, in Morocco. */
export function momentOf(value: string, lang: string): string {
  return new Intl.DateTimeFormat(locale(lang), { day: 'numeric', month: 'long', year: 'numeric', hour: '2-digit', minute: '2-digit',
    hourCycle: 'h23', timeZone: ZONE }).format(new Date(value));
}

/** A count with its group separator, digits Western. */
export const num = (n: number, lang: string) => new Intl.NumberFormat(locale(lang)).format(n);

/** A file's size in kB, MB or GB, kept left to right inside an Arabic line. */
export function bytes(n: number): string {
  const s = n < 1e6 ? `${Math.max(1, Math.round(n / 1e3))} kB` : n < 1e9 ? `${(n / 1e6).toFixed(1)} MB` : `${(n / 1e9).toFixed(2)} GB`;
  return `\u2066${s}\u2069`;
}

/** A day `n` days after an ISO day (before, when negative). */
export function shift(day: string, n: number): string {
  const [y, m, d] = day.split('-').map(Number);
  return new Date(Date.UTC(y, m - 1, d + n)).toISOString().slice(0, 10);
}

/** The last `n` days up to `today`, oldest first, each with its use; a day without use counts nothing. */
export function lastDays(days: UseDay[], today: string, n = 30): UseDay[] {
  const used = new Map(days.map((d) => [d.day, d]));
  return Array.from({ length: n }, (_, i) => {
    const day = shift(today, i - n + 1);
    const d = used.get(day);
    return { day, calls: d?.calls ?? 0, articles: d?.articles ?? 0 };
  });
}

/** The day an answer is due, in words, from the working days left: «بقي 3 أيام», «اليوم», «تأخر يوما». `late` once it
 *  passed, `today` on the day. Nothing for a request that does not wait for the staff. */
export function due(t: T, daysLeft: number | null): { words: string; mark: '' | 'today' | 'late' } {
  if (daysLeft === null) return { words: '', mark: '' };
  if (daysLeft === 0) return { words: t('due.today'), mark: 'today' };
  if (daysLeft < 0) return { words: t('due.late', { count: -daysLeft }), mark: 'late' };
  return { words: t('due.left', { count: daysLeft }), mark: '' };
}

/** What an access grants, or a request asks for, in words. */
export const granted = (t: T, api: unknown, data: unknown) => t(`granted.${api && data ? 'both' : api ? 'api' : data ? 'data' : 'none'}`);

/** A size's name. */
export const sizeName = (t: T, size: unknown) => (size ? t(`sizes.${size}`, { defaultValue: String(size) }) : '');

/** What an access holds (or will), in one line: «الواجهة البرمجية، حجم «تطبيق»، حتى 16 نونبر 2027». A partner's three
 *  numbers follow when they are given; the end date when it is. */
export type Held = { api?: unknown; data?: unknown; size?: unknown; ends_on?: unknown; minute?: unknown; calls?: unknown; articles?: unknown };

export function heldWords(t: T, g: Held, lang: string): string {
  let out = t('held.size', { granted: granted(t, g.api, g.data), size: sizeName(t, g.size) });
  if (g.size === 'partner' && (g.minute || g.calls || g.articles)) {
    const n = (v: unknown) => (typeof v === 'number' ? num(v, lang) : t('held.asApp'));
    out += t('held.numbers', { minute: n(g.minute), calls: n(g.calls), articles: n(g.articles) });
  }
  if (typeof g.ends_on === 'string' && g.ends_on) out += t('held.until', { date: dateOf(g.ends_on, lang) });
  return out;
}

/** What accepting will give, said once more before it goes: «ستعطي: …». For a change request, what its access becomes. */
export function restateAccept(t: T, g: Grant & { minute?: number | null; calls?: number | null; articles?: number | null },
                              lang: string, change = false): string {
  return t(change ? 'restate.change' : 'restate.accept', { held: heldWords(t, g, lang) });
}

/** What changing an access will do, said before it goes: what it holds after, in place of what it held. */
export function restateChange(t: T, before: Record<string, unknown>, after: Record<string, unknown>, lang: string): string {
  return t('restate.changed', { after: heldWords(t, after, lang), before: heldWords(t, before, lang) });
}

/** A door's name in words; a door the page does not know is said by its code. */
export const doorName = (t: T, door: string) => t(`doors.${door.replace('.', '_')}`, { defaultValue: door });

/** What one act did, in one sentence: «قبل chief طلب مختبر القانون الرقمي: الواجهة البرمجية، حجم «تطبيق»، حتى …». The names
 *  people typed and the usernames keep their own direction. */
export function eventLine(t: T, e: DeskEvent, lang: string): string {
  const d = e.details ?? {};
  const name = iso(e.name || t('log.noName'));
  const by = e.by ? iso(e.by) : '';
  const reason = (kind: 'reasons' | 'ended') => t(`${kind}.${String(d.reason ?? '')}`, { defaultValue: String(d.reason ?? '') });
  switch (e.act) {
    case 'sent':
      return e.access
        ? t('log.sentChange', { name, what: heldWords(t, { api: d.api, data: d.data, size: d.size }, lang) })
        : t('log.sent', { name, what: granted(t, d.api, d.data) });
    case 'answered':
      return t('log.answered', { name });
    case 'asked':
      return t('log.asked', { by, name, line: iso(String(d.line ?? '')) });
    case 'accepted':
      return t(d.before ? 'log.acceptedChange' : 'log.accepted', { by, name, held: heldWords(t, d, lang) });
    case 'declined':
      return t('log.declined', { by, name, reason: reason('reasons') });
    case 'changed': {
      const before = (d.before ?? {}) as Record<string, unknown>;
      const after = (d.after ?? {}) as Record<string, unknown>;
      return t('log.changed', { by, name, after: heldWords(t, after, lang), before: heldWords(t, before, lang) });
    }
    case 'renewed':
      return t(d.before ? 'log.renewed' : 'log.renewedFirst', { by, name, date: dateOf(String(d.ends_on ?? ''), lang),
        before: dateOf(String(d.before ?? ''), lang) });
    case 'ended':
      if (!e.by) return t('log.endedItself', { name, reason: reason('ended') });
      if (d.reason === 'asked') return t('log.endedOwn', { name });
      return t('log.ended', { by, name, reason: reason('ended') });
    case 'key_made':
      return t('log.keyMade', { name });
    case 'key_ended':
      return e.by ? t('log.keyEnded', { by, name }) : t('log.keyEndedItself', { name });
    default:
      return t('log.other', { name, act: String(e.act) });
  }
}

/** The sentence a refusal of the server is said in: `errors.<field>.<code>`, else a generic one. */
export function refusalKey(errors: { field: string; code: string }[], status: number): string {
  const e = errors[0];
  if (e) return `errors.${e.field}.${e.code}`;
  if (status === 429) return 'errors.request.throttled';
  return 'errors.unknown';
}

/** A request's answers checked before a letter is asked for: the field and code the server would refuse, or null. */
export function checkAccept(g: { api: boolean; data: boolean; size: string; ends_on: string | null }, today: string):
  [string, string] | null {
  if (!g.api && !g.data) return ['wants', 'required'];
  if (!SIZES.includes(g.size as Size)) return ['size', 'invalid'];
  if (g.ends_on && g.ends_on <= today) return ['ends_on', 'past'];
  return null;
}

/** The line asked, checked as the server checks it: folded to one line, 1 to LINE_MOST characters. */
export function checkLine(line: string): [string, string] | null {
  const folded = line.split(/\s+/).filter(Boolean).join(' ');
  if (!folded) return ['line', 'required'];
  if (folded.length > LINE_MOST) return ['line', 'too_long'];
  return null;
}

/** A partner's number as typed: a whole number from 1, or null for the app size's; NaN when it is not one. */
export function partnerNumber(typed: string): number | null {
  const s = typed.trim();
  if (!s) return null;
  return /^\d+$/.test(s) && Number(s) >= 1 && Number(s) <= 2 ** 31 - 1 ? Number(s) : Number.NaN;
}

/** A link for an address a request named, when it is one a browser can open; null otherwise. */
export function linkOf(runsAt: string): string | null {
  const s = runsAt.trim();
  if (!s || /\s/.test(s)) return null;
  const withScheme = /^https?:\/\//i.test(s) ? s : /^[\w-]+(\.[\w-]+)+(\/.*)?$/.test(s) ? `https://${s}` : '';
  try {
    return withScheme ? new URL(withScheme).href : null;
  } catch {
    return null;
  }
}
