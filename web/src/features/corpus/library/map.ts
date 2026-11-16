/** Every issue the site holds (GET /api/corpus/issues/map/, LB13 of the every-code review): the answer's columns read back
 *  into issues, and what the library, /bo and the box ask of them: a number, a day, the days around one, a year. Pure:
 *  `npm run test:library`. */

export type MapColumns = { n: number[]; d: number[]; t: number[]; p: number[]; f: number[]; s: [number, number][]; l: [number, number][]; z: number[] };
export type RawMap = { epoch: string; ar: MapColumns; fr: MapColumns };

export type Held = {
  edition: 'general_ar' | 'translation_fr';
  number: number;
  suffix: '' | 'bis' | 'ter';
  /** The issue's address part: «7555-bis». */
  key: string;
  /** Its day, YYYY-MM-DD. */
  date: string;
  y: number;
  /** 0–11 */
  m: number;
  d: number;
  /** Its day of the year, 0 first, and the year's days: a tick's place on a year's strip. */
  doy: number;
  dim: number;
  texts: number;
  pages: number;
  /** The printed number of its first page, 0 when unknown. */
  first: number;
  /** The last number its cover bears when it bears several («عدد 610 — 637»), else 0. */
  last: number;
  /** Held without a text cut from it (its pages only: a report, an issue the cutting missed; LB10). */
  pagesOnly: boolean;
};

export type Year = { year: number; ar: Held[]; fr: Held[]; min: number; max: number; texts: number; pagesOnly: number };

const DAY = 86_400_000;
const SUFFIX = ['', 'bis', 'ter'] as const;

export const iso = (ms: number) => new Date(ms).toISOString().slice(0, 10);
export const dayOf = (date: string) => Date.parse(`${date}T00:00:00Z`);

function columns(col: MapColumns, epoch: number, edition: Held['edition']): Held[] {
  const out: Held[] = [];
  const suffix = new Map(col.s), last = new Map(col.l), pagesOnly = new Set(col.z);
  let number = 0, day = 0, first = 0, pages = 0;
  for (let i = 0; i < col.n.length; i++) {
    number += col.n[i];
    day += col.d[i];
    first = (col.f[i] ?? 0) + (first && pages ? first + pages : 0);
    pages = col.p[i];
    const ms = epoch + day * DAY;
    const at = new Date(ms);
    const y = at.getUTCFullYear();
    const start = Date.UTC(y, 0, 1);
    const sfx = SUFFIX[suffix.get(i) ?? 0];
    out.push({
      edition, number, suffix: sfx, key: sfx ? `${number}-${sfx}` : String(number), date: iso(ms), y, m: at.getUTCMonth(),
      d: at.getUTCDate(), doy: (ms - start) / DAY, dim: (Date.UTC(y + 1, 0, 1) - start) / DAY, texts: col.t[i], pages,
      first, last: last.get(i) ?? 0, pagesOnly: pagesOnly.has(i),
    });
  }
  return out;
}

/** The answer's columns as issues, oldest first. The French rows carry no first page. */
export function decode(raw: RawMap): { ar: Held[]; fr: Held[] } {
  const epoch = dayOf(raw.epoch);
  return { ar: columns(raw.ar, epoch, 'general_ar'), fr: columns({ ...raw.fr, f: raw.fr.f ?? [] }, epoch, 'translation_fr') };
}

export type Archive = {
  ar: Held[];
  fr: Held[];
  years: Map<number, Year>;
  /** «7555:bis» → the issue. */
  byNumber: Map<string, Held>;
  /** The same for the French edition's issues the site holds (W10 of the library-search review: a French reference opens them). */
  frByNumber: Map<string, Held>;
  /** A number printed on another issue's cover → that issue. */
  covered: Map<number, Held>;
  byDay: Map<string, Held[]>;
  days: string[];
  maxNumber: number;
};

/** What every reader of the map needs, built once. */
export function archive(raw: RawMap): Archive {
  const { ar, fr } = decode(raw);
  const years = new Map<number, Year>();
  for (const x of [...ar, ...fr]) {
    let y = years.get(x.y);
    if (!y) years.set(x.y, (y = { year: x.y, ar: [], fr: [], min: 0, max: 0, texts: 0, pagesOnly: 0 }));
    (x.edition === 'general_ar' ? y.ar : y.fr).push(x);
    y.texts += x.texts;
  }
  for (const y of years.values()) {
    y.min = y.ar.reduce((n, x) => Math.min(n, x.number), Infinity);
    y.max = y.ar.reduce((n, x) => Math.max(n, x.last || x.number), 0);
    if (!y.ar.length) y.min = 0;
    y.pagesOnly = y.ar.filter((x) => x.pagesOnly).length;
  }
  const byNumber = new Map<string, Held>(), covered = new Map<number, Held>(), byDay = new Map<string, Held[]>();
  let maxNumber = 0;
  for (const x of ar) {
    byNumber.set(`${x.number}:${x.suffix}`, x);
    for (let k = x.number + 1; k <= x.last; k++) covered.set(k, x);
    byDay.set(x.date, [...(byDay.get(x.date) ?? []), x]);
    maxNumber = Math.max(maxNumber, x.last || x.number);
  }
  const frByNumber = new Map<string, Held>(fr.map((x) => [`${x.number}:${x.suffix}`, x]));
  return { ar, fr, years, byNumber, frByNumber, covered, byDay, days: [...byDay.keys()].sort(), maxNumber };
}

/** The issue a number names, or the cover it was printed on. */
export function issueByNumber(a: Archive, number: number, suffix: Held['suffix'] = ''): { issue: Held | null; cover: boolean } {
  const own = a.byNumber.get(`${number}:${suffix}`);
  if (own) return { issue: own, cover: false };
  const cover = suffix ? undefined : a.covered.get(number);
  return cover ? { issue: cover, cover: true } : { issue: null, cover: false };
}

/** The issues of the days nearest before and after a day that has none. */
export function around(a: Archive, date: string): { before: Held[]; after: Held[] } {
  let lo = 0, hi = a.days.length;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (a.days[mid] < date) lo = mid + 1;
    else hi = mid;
  }
  const after = a.days[lo] === date ? a.days[lo + 1] : a.days[lo];
  const before = a.days[lo - 1];
  return { before: before ? a.byDay.get(before) ?? [] : [], after: after ? a.byDay.get(after) ?? [] : [] };
}

/** The issues printed with a year's numbers, and the neighbours of a year among those held. */
export function neighbours<T>(list: T[], at: number): { older?: T; newer?: T } {
  return { older: at > 0 ? list[at - 1] : undefined, newer: at >= 0 && at < list.length - 1 ? list[at + 1] : undefined };
}
