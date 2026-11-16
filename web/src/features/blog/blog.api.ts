import { useQuery } from '@tanstack/react-query';
import { api } from '@/shared/services/api';

type Both = { ar: string; fr: string };

/** A post as the blog lists it (apps/blog: a folder per post, its meta written and its figures counted). */
export type PostSummary = {
  slug: string;
  number: number;
  status: 'draft' | 'published';
  date: string | null;
  counted_on: string;
  title: Both;
  lead: Both;
  /** A short post's long one: the post whose figures it tells in words. */
};

/** «الجريدة الرسمية من العدد 1 في صورة واحدة» (until 6 Nov 2026 «سبعون سنة», from 1956): the figures `manage.py
 *  blog_figures from-no-1` counted, and what a person read on the Bulletin's pages (No. 1, the days, the prices, what the
 *  thickest issues carry). */
export type SeventyFigures = {
  span: [number, number];
  year_fields: string[];
  years: number[][];
  /** Monday … Sunday: the regular issues of each year. */
  weekdays: Record<string, number[]>;
  issue_fields: string[];
  /** Each year's issues in the order they came out: [number, bis, monthday, pages, texts, report]. */
  issues: Record<string, number[][]>;
  thickest: { key: string; date: string; pages: number; texts: number; report: boolean }[];
  totals: Record<string, number>;
  /** The French edition apart, a year at a time: [issues, texts only it printed] (1912–1925 read). */
  french: Record<string, [number, number]>;
  /** The Arabic texts with a title and no words on the site, a year at a time. */
  bare: Record<string, number>;
  /** Issues whose file online is another issue's, a year at a time: not counted. */
  copies: Record<string, number>;
  counted: { on: string; database: string };
};

export type SeventyPost = PostSummary & {
  span: [number, number];
  founded: number;
  first: { issue: string; date: string; hijri: string; pages: number; of: Both; contents: Both[]; second: { issue: string; date: string } };
  french: { first: { issue: string; date: string }; before: number };
  weekdays: { from: string; issue: string; days: number[] }[];
  prices: { from: string; issue: string; price: number; unit: 'centime' | 'franc' | 'dirham' }[];
  price_last_read: { date: string; issue: string };
  subscription: { date: string; issue: string; price: number; unit: string };
  issues: Record<string, Both>;
  figures: SeventyFigures;
};

export const fetchPosts = () => api<{ posts: PostSummary[] }>('/blog/');
/** The posts, the newest first: kept an hour, as the server keeps them. */
export const usePosts = () => useQuery({ queryKey: ['blog'], queryFn: fetchPosts, staleTime: 3600_000 });
export const fetchPost = <T extends PostSummary>(slug: string) => api<T>(`/blog/${slug}/`);

/** «ستة دساتير في صفحة واحدة»: each constitution as issued, its titles and articles, what became of each article
 *  since the one before (0 first, 1 the same words, 2 rewritten, 3 unsure, 4 nothing before it), words counted. */
export type SixConstitution = {
  year: number;
  path: string;
  referendum: string;
  signed: string;
  published: string;
  issue: string;
  page: number;
  articles: number;
  words: number;
  preamble: number;
  titles: { name: string; theme: string; articles: number; words: number }[];
  squares: [string, number, number][];
  terms: Record<string, number>;
  quotes: [string, string][];
};

export type SixPost = PostSummary & {
  themes: { key: string; ar: string; fr: string }[];
  terms: { key: string; ar: string; fr: string }[];
  figures: { constitutions: SixConstitution[] };
};

/** A word's stop, read on its printed page: its first mention, the first text on the subject, or a later step; with its
 *  issue and page, and its article (or its issue, for a text not cut yet: a path under /bo/). */
export type WordStop = {
  date: string; kind: 'first' | 'subject' | 'step'; ar: string; fr: string; title: string; issue: string;
  page: number | null; path: string;
};
/** «كلمات دخلت القانون»: for each word, the texts that carry it each year from the post's first year, its first counted
 *  text, its stops, and what the stops do not reach yet. */
export type WordCount = {
  key: string;
  years: number[];
  first: { date: string; title: string; issue: string; page: number | null; path: string } | null;
  stops?: WordStop[];
  open?: { ar: string; fr: string };
};
export type WordsPost = PostSummary & {
  span: [number, number];
  groups: { key: string; ar: string; fr: string; words: { key: string; ar: string; fr: string; part_of?: string }[] }[];
  figures: { span: [number, number]; texts: number[]; words: WordCount[] };
};

/** «من يكتب القواعد التي نعيش بها؟»: texts by author year by year, orders by ministry and subject, laws by kind. */
type Named = { key: string; ar: string; fr: string };
export type WhoPost = PostSummary & {
  span: [number, number];
  authors: (Named & { what: { ar: string; fr: string } })[];
  ministries: Named[];
  subjects: Named[];
  laws: Named[];
  figures: {
    span: [number, number];
    authors: Record<string, number[]>;
    ministries: Record<string, number>;
    subjects: Record<string, number[]>;
    laws: Record<string, number[]>;
    decades: number[];
    decree_laws: number[];
  };
};

/** «دجنبر، شهر الأعداد المكررة، ومارس، شهر القوانين»: each year's months, texts by kind a month, the Hijri months. */
export type MonthsPost = PostSummary & {
  figures: {
    span: [number, number];
    /** A year a row, a month a cell: [issues, bis, pages, texts]. */
    months: [number, number, number, number][][];
    kinds: { laws: number[]; decrees: number[]; orders: number[] };
    hijri_since: number;
    /** A Hijri month a row: [regular issues, texts, pages]. */
    hijri: [number, number, number][];
  };
};

/** «الحد الأدنى للأجر، مرسوما بعد مرسوم»: each raise as its articles print it, each decree with its issue and page. */
export type WageStep = {
  decree: string; issue?: string; from?: string; from_published?: boolean; hourly?: number; daily?: number;
  daily_francs?: number; hourly_raise_francs?: number; zones?: number[]; note?: { ar: string; fr: string };
};
export type WagePost = PostSummary & {
  steps: WageStep[];
  hours_a_year: number;
  figures: { decrees: Record<string, { title: string; path: string; page: number | null; issue: string; published: string }> };
};

/** «أعيادنا بمرسوم»: the holiday lists as their texts print them, each text tied to its issue and page. */
type Both2 = { ar: string; fr: string };
export type HolidaysPost = PostSummary & {
  holidays: (Both2 & { key: string; date?: string; hijri?: boolean })[];
  private: { text: string; days: string[] }[];
  administration: { text: string; days?: string[]; adds?: string[]; two_days?: string[] }[];
  jan1: Both2;
  once: { text: string };
  figures: { texts: Record<string, { title: string; path: string; page: number | null; issue: string; published: string }> };
};

/** «من التوقيع إلى الجريدة»: each law's wait, the medians by kind and decade, the laws that waited over a year. */
export type WaitsPost = PostSummary & {
  figures: {
    span: [number, number];
    bands: number[];
    kept: number;
    left_out: { no_date: number; after: number; erratum: number };
    /** [published, days, agreement (0/1), number, issue key, path] */
    laws: [string, number, number, string, string, string][];
    decades: number[];
    medians: Record<string, (number | null)[]>;
    overall: Record<string, number>;
    counts: Record<string, number>;
    late: { number: string; signed: string; published: string; days: number; issue: string; page: number | null; path: string; title: string; agreement: boolean }[];
    same_day: number;
  };
};

export type ErrataKind = 'names' | 'law' | 'decree' | 'order' | 'other' | 'index';
export type ErrataNotice = { printed: string; printed_issue: string; corrected: string; corrected_issue: string; days: number; kind: ErrataKind };

export type ErrataPost = PostSummary & {
  examples: { corrected_issue: string; printed_issue: string; what: { ar: string; fr: string }; wrong: string; right: string; gloss: string }[];
  figures: {
    span: [number, number];
    notices: number;
    timed: number;
    left_out: { no_issue?: number; after?: number; misread?: number };
    decades: number[];
    kinds: ErrataKind[];
    per_decade: Record<'notices' | 'texts' | 'issues' | ErrataKind, number[]>;
    /** The corrections each year, from the span's first. */
    years: number[];
    median_days: number;
    decade_median_days: (number | null)[];
    bands: number[];
    band_counts: number[];
    /** [corrected issue's day, printing issue's day, corrected issue, printing issue, kind's index in `kinds`] */
    arcs: [string, string, string, string, number][];
    longest: ErrataNotice[];
    most_corrected: { issue: string; date: string; times: number }[];
  };
};

export type PartnerName = { ar: string; fr: string; short_ar?: string; short_fr?: string };
export type Counted = { key: string; n: number };

export type AgreementsPost = PostSummary & {
  edition: { decree: string; issue: string; date: string; page: number; path: string; words: string };
  figures: {
    span: [number, number];
    texts: number;
    sorted: Record<'money' | 'treaty' | 'law' | 'domestic' | 'other', number>;
    decades: number[];
    names: Record<string, PartnerName>;
    kinds: ('loan' | 'guarantee' | 'grant')[];
    /** [the decree's issue day, the kind's index in `kinds`, the lender, the decree's address, its number] */
    money: [string, number, string, string, string][];
    money_per_decade: Record<'loan' | 'guarantee' | 'grant', number[]>;
    lenders: { key: string; n: number; since_2000: number; first: string; last: string }[];
    borrowers: Counted[];
    treaties_per_decade: number[];
    treaty_regions: Record<string, number[]>;
    treaty_partners: Counted[];
    topics: Counted[];
    last_publication: string | null;
    ages: { aged: number[]; median: (number | null)[]; over_10: number[]; over_20: number[] };
    oldest: { published: string; signed: number; years: number; title: string; path: string }[];
    laws_per_decade: number[];
    law_regions: Record<string, number[]>;
    law_partners: Counted[];
  };
};

/** A state as «العالم في الجريدة الرسمية» counts it (apps/blog/services/countries.py): its texts period by period (`c`),
 *  per 1,000 texts of the period (`s`), the same without the diploma lists (`x`), its kinds, first and last years. */
export type CountryRow = {
  slug: string;
  gone: boolean;
  ar: string;
  fr: string;
  en: string;
  lat: number | null;
  lon: number | null;
  successor: string | null;
  region: string;
  n: number;
  c: number[];
  s: number[];
  x: number[];
  kinds: Record<string, number>;
  first: { year: number; date: string; issue: string; edition: string; page: number | null; form: string; title: string } | null;
  last: number;
  spellings: string[];
};

export type CountriesPost = PostSummary & {
  periods: [number, number][];
  figures: {
    periods: [number, number][];
    texts: number[];
    foreign: number[];
    baseline: number[];
    states: CountryRow[];
    moves: { rose: string[]; fell: string[] };
    moves_nodip: { rose: string[]; fell: string[] };
    climb: { from: number; counts: number[] };
    never: { ar: string; fr: string }[];
    kinds: Record<string, number>;
    totals: { states: number; gone: number; texts: number; foreign: number; never: number; studies: number; conventions: number };
  };
};

/** A city as «المغرب في الجريدة الرسمية» counts it (apps/blog/services/cities.py), with its province of the same name. */
export type CityRow = {
  slug: string;
  ar: string;
  fr: string;
  lat: number | null;
  lon: number | null;
  pop: number | null;
  n: number;
  c: number[];
  s: number[];
  kinds: Record<string, number>;
  old: { forms: string[]; c: number[] } | null;
  first: { year: number; date: string; issue: string; page: number | null; form: string } | null;
};

export type CitiesPost = PostSummary & {
  periods: [number, number][];
  /** Texts read on their printed pages: the north's names (1959), the Sahara's provinces and Errachidia (1976, 1979). */
  stops: { key: string; text: string; issue: string; date: string; page: number; ar: string; fr: string }[];
  figures: {
    periods: [number, number][];
    texts: number[];
    cities: CityRow[];
    moves: { rose: string[]; fell: string[] };
    five: { slugs: string[]; top: number[]; rest: number[] };
    people: { slug: string; v: number }[];
    people_low: { slug: string; v: number }[];
    totals: { cities: number; texts: number; zone?: number };
  };
};

/** «من غرينيتش إلى غرينيتش» (the thirteenth post): every text that set or moved Morocco's legal time, each move as its
 *  article words it, read on its printed page; the figures tie each text to its issue, its page and its address, and
 *  give Ramadan's and Shawwal's first days as the Bulletin's own Hijri dates set them. */
export type ClockText = {
  key: string;
  kind: 'dahir' | 'royal' | 'decree' | 'decision' | 'court';
  number?: string;
  signed: string;
  edition: string;
  issue: number;
  bis?: boolean;
  page: number;
};
export type ClockPrinted = { issue: string; edition: string; published: string; page: number; viewer: string | null };
export type ClockPost = PostSummary & {
  before: {
    rabat: { issue: number; page: number; minutes: number; seconds: number; date: string; fr: string };
    safi: { issue: number; page: number; fr: string };
    eiffel: { issue: number; page: number; fr: string };
  };
  legal_from: string;
  texts: ClockText[];
  moves: { at: string; to: 0 | 60; text: string; rule?: boolean }[];
  unknown: { from: string; to: string }[];
  undone: { at: string; set: string; by: string }[];
  words: Record<string, { ar: string; fr: string; translated?: boolean }>;
  figures: {
    texts: Record<string, ClockPrinted & { path: string | null; also?: ClockPrinted }>;
    hijri: { ramadan: Record<string, string>; shawwal: Record<string, string> };
  };
};

/** «ماركيز، قرارا بعد قرار» (the fourteenth post): the soft pack's price in every order that printed it, read in its
 *  row; the levy for the Palestinian people (dahir 1.70.16); the verb of the orders; the figures tie each text to its
 *  page and take the minimum wage from the sixth post. */
type MqRef = { date: string; issue: number; bis?: boolean; page: number; number?: string; akn?: string };
export type MarquisePrice = MqRef & { price: number; unit: 'franc' | 'dirham'; name: string; company?: number; palestine?: number; kind: string };
export type MarquisePost = PostSummary & {
  prices: MarquisePrice[];
  renamed: MqRef & { old: string; new: string };
  gap: { from: string; to: string };
  approve: MqRef & { from: string; words: { ar: string; fr: string } };
  delegate: MqRef;
  palestine: {
    dahir: MqRef & { signed: string; from: string };
    ordinary: number;
    premium: number;
    cinema: [number, number];
    theatre: [number, number];
    words: { ar: string; fr: string };
    changed: (MqRef & { law?: string })[];
    applied: MqRef;
  };
  hours_a_year: number;
  figures: {
    texts: Record<string, ClockPrinted & { path: string | null }>;
    wage: { from: string; hourly: number; decree: string; issue: string | null; path: string | null }[];
    orders: [string, 'set' | 'approve'][];
  };
};

/** «الخبز والغازوال، يوم كانت الجريدة الرسمية تكتب ثمنهما» (the fifteenth post): the five staples of three issues (1980,
 *  28 May and 10 June 1981), gasoil a litre order by order (1975–2014), and the orders that took the price out of the
 *  Bulletin; the figures tie each order to its page and take the minimum wage from the sixth post. */
type SpRef = { number: string; issue: number; bis?: boolean; page: number; akn?: string };
export type StaplesGasoil = SpRef & { from: string; printed?: boolean; price: number; name: string; date: string };
export type StaplesPost = PostSummary & {
  issues: { key: string; issue: number; bis?: boolean; date: string; from: string }[];
  basket: { key: string; values: number[]; orders: SpRef[] }[];
  bread_1975: SpRef & { value: number; date: string };
  june_words: { ar: string; fr: string };
  gasoil: StaplesGasoil[];
  last: SpRef & { from: string; price: number; date: string };
  away: { key: string; from: string; to?: string; text: SpRef; words: { ar: string; fr: string } }[];
  figures: {
    texts: Record<string, ClockPrinted & { path: string | null }>;
    wage: { from: string; hourly: number; decree: string; issue: string | null; path: string | null }[];
  };
};

type AgRef = { issue: number; bis?: boolean; page: number; akn?: string };
export type AgesItem = {
  key: string; age: number; side: 'start' | 'end'; from: number; to?: number | null; echo?: boolean;
  law: string; art?: string; article_in?: string; ref: AgRef; text: { ar: string; fr: string };
};
export type AgesPost = PostSummary & {
  laws: Record<string, { ar: string; fr: string; art: 'article' | 'chapter' | 'single' }>;
  ages: AgesItem[];
  moves: { key: string; steps: { age: number; year: number; law: string; art?: string; ref: AgRef }[] }[];
  equal: { ar: string; fr: string; ref: AgRef };
  retire: { steps: { born: number; age: number; before?: boolean; after?: boolean }[]; unknown_day: { ar: string; fr: string; ref: AgRef } };
  figures: { texts: Record<string, ClockPrinted & { path: string | null }>; articles: Record<string, string> };
};

type DrRef = { number: string; issue: number; page: number; akn?: string };
export type DrCrop = { left: number; top: number; right: number; bottom: number; ratio: number };
export type DrinksPost = PostSummary & {
  order: DrRef & { last: number; articles: number; signed: string; published: string };
  art28: { page: number; crop: DrCrop; ar: string[]; fr: string[]; marks: { key: string; p: number; ar: string; fr: string }[] };
  articles: { n: number; page: number }[];
  chain: { key: string; year: number; text: DrRef; words?: string }[];
  repealed: string;
  first: { issue: number; page: number; hijri: string; akn: string; crop: DrCrop; art1: string; reason: string; vizier: { ar: string; fr: string } };
  pairs: { key: string; a1913: string; p1913: number; a1967: string; n1967: number }[];
  fines: { art: number; lo: number; hi: number; prison?: [number, number]; or?: boolean }[];
  drunk: { text: DrRef; words: string };
  figures: {
    texts: Record<string, ClockPrinted & { path: string | null }>;
    articles: Record<string, string>;
    wage: { from: string; hourly: number; decree: string; issue: string | null; path: string | null }[];
  };
};

type StRef = { issue: number; bis?: boolean; page: number; akn?: string };
export type StrikePost = PostSummary & {
  constitutions: (StRef & { year: number; n: number; art: string; date: string; words: string; crop: DrCrop })[];
  deadline: StRef & { art: string; words: string };
  law: StRef & { number: string; signed: string; published: string; articles: number };
  decision: StRef & { number: string; date: string };
  opinion: StRef & { date: string };
  path: { key: string; date: string }[];
  ruling: string;
  numbers: { key: string; n: string; art: string; page: number }[];
  nostrike: string;
  stop: string;
  bulletin: string;
  organic: (StRef & { number: string; ar: string; fr: string; date: string })[];
  election: StRef & { date: string };
  figures: { texts: Record<string, ClockPrinted & { path: string | null }>; articles: Record<string, string> };
};


type WaRef = { issue: number; bis?: boolean; page: number; akn?: string; date?: string };
export type WaCount = { key: string; texts: number; standing: number; newest: { date: string; path: string } | null; decades: number[] };
export type WhatsappPost = PostSummary & {
  machines: { key: string; ar: string; fr: string; example: WaRef & { number: string; words: string; art?: string } }[];
  cese: WaRef & { title_page: number };
  apps: { key: string; ar: string; fr: string; pct?: string; first: WaRef & { kind: 'opinion' | 'report' | 'quote'; by: string } }[];
  clippings: (WaRef & { key: string; words: string; number?: string; crop: DrCrop })[];
  words: Record<string, string>;
  telegraph: WaRef & { words: string };
  mediator: { reports: (WaRef & { year: number })[]; years: { year: number; fax: number; whatsapp?: number; total: number; files?: boolean }[] };
  naming: {
    formula: WaRef & { number: string; words: string; parts: string[]; art: string };
    group: WaRef & { number: string; words: string };
    doctor: WaRef & { number: string; words: string };
    council: WaRef & { words: string };
  };
  figures: {
    texts: Record<string, ClockPrinted & { path: string | null }>;
    articles: Record<string, string>;
    decades: number[];
    read: number[];
    machines: WaCount[];
    generics: WaCount[];
    apps: { key: string; texts: number; pages: number; issues: number; first: { issue: string; page: number; date: string } | null; years: Record<string, number> }[];
    formula: number;
    checks: unknown[];
  };
};

type DpRef = { issue: number; bis?: boolean; page: number; akn?: string; date?: string };
export type DeathPost = PostSummary & {
  code: { akn: string; issue: number; bis: boolean; signed: string; printed: string };
  groups: { key: string; from: string }[];
  articles: { n: string; kind: 'death' | 'rule'; page: number; since?: number; issue?: number; was?: string }[];
  others: {
    military: { akn: string; number: string; issue: number; date: string; arts: { n: string; page: number; words: string }[] };
    railway: DpRef & { number: string; art: string; words: string };
    food: DpRef & { number: string; signed: string; art1: string; art2: string; crop: DrCrop };
    victims: DpRef & { number: string; words: string };
  };
  steps: (DpRef & { key: string; art: string; words: string; since?: number; was?: DpRef & { art: string; year: number; words: string } })[];
  witnesses: string[];
  cndh: {
    years: (DpRef & { year: number; n: number })[];
    halt: DpRef & { words: string };
    pardons: DpRef & { n: number; words: string };
    vote: DpRef & { words: string };
  };
  figures: {
    texts: Record<string, ClockPrinted & { path: string | null }>;
    cells: { n: string; g: string; clause?: string }[];
    articles: Record<string, string>;
    checks: unknown[];
  };
};

type PlRef = { issue: number; bis?: boolean; page: number; akn?: string; date?: string };
export type ParliamentPost = PostSummary & {
  span: [number, number];
  hands: { key: string; re: string }[];
  constitutions: (PlRef & { year: number; art: string; words: string })[];
  exception: { decree: PlRef & { number: string; words: string }; indemnities: PlRef & { number: string; words: string } };
  reading: { wpm: number; layers: { key: string; types: string[] }[] };
  figures: {
    forms: Record<string, number>;
    ratio: { decrees: number; orders: number; share: number };
    years: { year: number; rdl: number; dfl: number; voted: number; dlaw: number }[];
    reading: { key: string; words: number; texts: number }[];
    texts: Record<string, ClockPrinted & { path: string | null }>;
  };
};

export type SpeedPost = PostSummary & {
  eras: { key: string; year: number; kmh: number; marks?: number[]; kind: 'news' | 'rule'; edition?: 'fr'; issue: number; page: number; akn?: string; words: string }[];
  first_rule: { issue: number; page: number; words: string };
  orders: { from: number; to: number };
  today: { key: string; kmh: number; art: string; page: number }[];
  code: { akn: string; issue: number; number: string };
  figures: { texts: Record<string, ClockPrinted & { path: string | null }>; orders: { year: number; kmh: number }[] };
};

export type DeadlinesPost = PostSummary & {
  examples: string[];
  figures: {
    total: number;
    deadlines: { unit: 'h' | 'd' | 'w' | 'm' | 'y'; n: number; count: number; days: number; example?: { path: string; akn: string; eid: string; words: string } }[];
  };
};

export type ExpropriationPost = PostSummary & {
  span: [number, number];
  purposes: { key: string; re: string }[];
  law: { number: string; issue: number; page: number; akn: string; words: string };
  constitution: { year: number; art: string; issue: number; bis?: boolean; page: number; akn: string; words: string };
  figures: {
    years: ({ year: number } & Record<string, number>)[];
    examples: Record<string, { title: string; akn: string }>;
    texts: Record<string, ClockPrinted & { path: string | null }>;
  };
};

export type MokriPost = PostSummary & {
  residents: { key: string; re: string; ar: string; fr: string }[];
  clip: { issue: number; page: number; words: string; crop: DrCrop };
  signed: { year: number; issue: number; page: number; akn: string; title: string }[];
  figures: {
    years: { year: number; dahir: number; order: number; other: number; resident: string | null }[];
    total: number;
    first: { date: string; title: string; path: string };
    last: { date: string; title: string; path: string };
    texts: Record<string, ClockPrinted & { path: string | null }>;
  };
};

export type MinistryPost = PostSummary & {
  figures: { names: { name: string; texts: number; from: number; to: number }[]; texts: number; longest: string };
};

type EmRef = { akn: string; number: string; issue: number; bis?: boolean; page: number };
export type EmergencyPost = PostSummary & {
  declaration: EmRef;
  decree_law: EmRef & { art2: string; art4: string };
  settlement: EmRef & { words: string };
  on_the_spot: EmRef & { words: string };
  ratified: EmRef;
  figures: {
    declared_until: string;
    terms: { key: string; number: string; until: string; printed: string; changes?: boolean }[];
    texts: Record<string, ClockPrinted & { path: string | null }>;
  };
};
