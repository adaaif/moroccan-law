import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import i18n, { pct } from '@/shared/locales/i18n';
import { api } from '@/shared/services/api';
import ar from './locales/ar.json';
import fr from './locales/fr.json';

/** The topic kit (F16 of the family plan): what a topic's folder says beyond its texts — doors, journeys, papers,
 *  pages, the reform, series — served by /api/topics/<slug>/<kind>/<key>/ and drawn the same way for every topic. Its
 *  words load with its code, in both languages. */
export const NS = 'topicKit';
if (!i18n.hasResourceBundle('ar', NS)) {
  i18n.addResourceBundle('ar', NS, ar);
  i18n.addResourceBundle('fr', NS, fr);
}
export const useKitT = () => useTranslation(NS);

export type Named = { ar: string; fr: string };
/** A folder's words in the reader's language. Arabic keeps a percent's sign on the right of its number (HM34 of
 *  the hard-moment review: the folders' words never passed the translation layer's `pct`, and /topics/tax drew «%45» 16
 *  times of 29). */
export const pick = (n: Named | undefined | null, lang: string): string => (n ? (lang === 'fr' && n.fr) || pct(n.ar) : '');

/** An article an item rests on, as the server resolved it. */
export type Cite = { path: string; label: string; number: string; text: Named };
export type Checked = { by: string; on: string } | null;
/** Every item: drafts reach readers only once a person checked them (F17); `stale` when a cited article changed. */
export type Base = {
  key: string; kind: string; state: 'draft' | 'stale' | 'checked'; checked?: Checked; title: Named; lead?: Named;
  /** Whom the item speaks to, by the topic's «where do you work?» answers (T5 of the work plan). */
  for?: string[];
};
export type Note = Named & { cites?: Cite[] };
/** A limit the law sets; `rolls`: an end on a weekend or a public holiday moves to the next working day (decree 2.22.04,
 *  art. 40: births and deaths). */
export type Delay = { days?: number; months?: number; hours?: number; from: Named; on_day?: boolean; rolls?: boolean;
  /** A court's limit (58.25 art. 602, 22.01 art. 750): neither the first day nor the last counts, and a day off at its
   *  end moves it to the next working day. */
  complete?: boolean };
/** The office a passage ends at (G1 of the family-papers review), drawn as its mark: the adouls' act, the
 *  civil-status record, the family court, the consulate. */
export type Office = 'act' | 'record' | 'court' | 'consul' | 'registry' | 'commune' | 'council' | 'fund' | 'hospital' | 'police' | 'post' | 'bank' | 'bar' | 'privacy';
export type Step = {
  title: Named; body: Named; cites?: Cite[]; note?: Note; delay?: Delay; papers?: string; next?: string; tool?: string;
  /** The step in one sentence, said first; the law's words fold under it (J1 of the road tools review). */
  answer?: Named;
  /** The official services the step needs, linked where they are used (J6). */
  services?: { name: Named; url: string }[];
};
export type Journey = Base & {
  steps: Step[]; next?: string[];
  /** The day the journey's limits count from, asked once (J2). */
  day?: Named;
  /** The paper the reader leaves with, from its office (G1 of the family-papers review), or on a punch card with its
   *  pictogram (E12 of the work-counted review), and the list that says what to keep (`papers`). */
  ends?: { office?: Office; icon?: string; paper: Named; cites?: Cite[]; papers?: string };
};
export type Item = { label: Named; note?: Named; when?: Named; cites?: Cite[] };
/** A check (H17 of the housing plan): each item a condition an article sets; the verdict says which are missed. */
export type Verdict = { ok: Named; missing: Named };
export type Checklist = Base & { cites?: Cite[]; items: Item[]; verdict?: Verdict };
export type Fact = { text: Named; cites?: Cite[] };
/** A section's facts, and the table the law states as one (art. 99's points, the categories and their ages: the
 *  road plan), its rows as the law has them and the articles it rests on. */
export type Section = {
  title: Named; facts?: Fact[]; more?: string; tool?: string;
  /** Whom it concerns, by the topic's question's answers: the reader's own comes first. */
  for?: string[];
  /** Where what it answers was said (a claim's page), and the bill it speaks of (the finance-bill review, P7, P14). */
  source?: Source; bill?: string;
  table?: { head: Named[]; rows: (Named | string)[][] }; cites?: Cite[];
};
export type Table = {
  columns: { key: string; label: Named }[];
  rows: {
    key: string; title: Named; to?: string; cells: Record<string, Named>; cites?: Cite[];
    /** Who may ask for it, by the table's question's answers; `also` names the others it opens to, on a condition. */
    askers?: string[]; also?: Record<string, Named>;
    /** How often it is used, from the topic's series (G9 of the family-papers review). */
    count?: { n: number; year: number; unit: Named; series?: string };
  }[];
  /** One question the rows answer differently (G9): «شكون بغا يفارق؟». */
  ask?: { question: Named; options: { key: string; label: Named }[]; source?: Named };
};
export type AgeLine = {
  max: number;
  spans: { from: number; to: number; text: Named; cites?: Cite[] }[];
  points: { age: number; text: Named; cites?: Cite[] }[];
};
export type SeriesFile = { title: string; url: string; path: string; sha256: string };
export type Series = Base & {
  cites?: Cite[]; table: string; unit?: 'thousands' | 'dirhams' | 'percent'; lines: { key: string; label: Named }[];
  years: ({ year: number; from: string; page: number } & Record<string, number | string>)[];
  files: Record<string, SeriesFile>; notes?: Named[];
};
export type InfoPage = Base & {
  sections?: Section[]; table?: Table; contacts?: { name: Named; number: string; source?: Source }[]; contacts_title?: Named; series?: Series[];
  /** Official services by name and link (T12 of the work plan): cited and linked, never copied. */
  links?: { name: Named; url: string; note?: Named }[];
  discreet?: boolean; next?: string[]; line?: AgeLine;
  /** A page about a bill, never law: its band above it (the finance-bill review, P5). */
  bill?: string;
  /** How the page is drawn (the bill-page review): its changes as amendment lines, or claims beside the text;
   *  `reform` the change whose stops the band shows; `calendar` the bill's dates of effect. */
  layout?: 'changes' | 'claims' | 'press';
  reform?: string;
  /** What of Parliament's record the page opens on: the chamber's vote as its hemicycle, or the committee's amendments
   *  by who filed them. */
  chamber?: 'vote' | 'amendments';
  /** The committee's report the amendments are cited to: a row's `page` opens it there. */
  report?: Source;
  /** The bill-story review: the page of what is said about it (`press`), its story's drawings above its changes
   *  (`story`) and after them (`after`), by the names the topic's PAGE_WIDGETS gives them. */
  press?: string; story?: string[]; after?: string[];
  calendar?: { date: string; to?: string; for: string[]; text: Named }[];
};
/** One change as the page draws it (V2, V3): the bill's figure, today's, its unit, the day it would apply. */
export type ChangeRow = {
  headline: Named; then: Named | string; now?: Named | string; unit?: Named; from?: string; when?: Named; check?: boolean;
  announced?: boolean; same?: boolean; new?: boolean; detail?: Named; cites?: Cite[]; more?: string;
  /** What the thing is, in one plain sentence; a note under today's figure and under the bill's; the reader's own figure
   *  (a PAGE_WIDGETS name, given the row's slug). */
  plain?: Named; now_note?: Named; then_note?: Named; you?: string;
  /** A change Parliament made to the bill: the figure as the government filed it (`filed`, struck through beside the
   *  voted one; none when the deputies added the line), and the amendment behind it. `refused`: an amendment the
   *  committee did not take, `then` what it proposed. */
  filed?: Named | string; filed_note?: Named;
  amended?: Amendment; refused?: Amendment;
};
/** An amendment as the committee's report records it: who filed it (`by`: government, majority, committee, a group, or
 *  `groups` for several), its vote in committee (for, against, abstaining; or unanimous), its page in the report, and
 *  whether its authors took it back (`withdrawn`). */
export type Amendment = { by: string; vote?: 'unanimous' | [number, number, number]; page?: number; withdrawn?: boolean };
/** A reader's section of a `changes` page: its chip, its one folded line, its rows; a drawing (`widget`) under its first
 *  change and one (`aside`) in the side column. */
export type ChangeSection = {
  key: string; for?: string[]; chip: Named; title: Named; line: Named; rows: ChangeRow[]; widget?: string; aside?: string;
  tool?: string; more?: string;
  /** A sentence under the section's title: what Parliament left as it was, or refused, for this reader. */
  note?: Named; note_more?: string; note_link?: Named;
};
/** A claim beside the text (V13): its neutral marker and the text's figure first. */
export type Claim = Section & { mark: 'as' | 'if' | 'later' | 'not' | 'other'; mark_words: Named; figure: Named; repeated?: string[] };
export type Source = { name: Named; url: string; file?: string; sha256?: string };
export type Reform = Base & {
  stage: string; checked_on: string; line: Named; stages: { key: string; label: Named }[];
  timeline: { date: string; text: Named; source: Source; cites?: Cite[]; short?: Named }[];
  groups?: { key: string; label: Named }[];
  questions?: { n: number; group: string; subject: Named; answer?: Named; cites?: Cite[] }[];
  rumours?: { claim: Named; truth: Named; cites?: Cite[] }[];
  /** A bill's way through Parliament (the finance-bill review, P3): the stop it has reached (`at`) and each
   *  stop's rule with the organic law's article that sets it. */
  at?: string;
  path?: { key: string; rule: Named; cites?: Cite[] }[];
  /** What Parliament did to a bill (the Chamber-vote update, 15 Nov 2026): each vote as its record counts it, and
   *  the amendments a committee took, by who filed them. */
  votes?: Vote[];
  amendments?: {
    filed: number; accepted: number; page?: string; link?: Named; source?: Source; note?: Named;
    groups: { key: string; side: 'government' | 'majority' | 'opposition'; label: Named; filed: number; accepted: number; rejected: number; withdrawn: number }[];
  };
};
/** A vote as the chamber's record gives it; `seats` (the chamber's, by its organic law) only where the whole chamber
 *  voted: the page then draws its hemicycle. */
export type Vote = {
  key: string; date: string; body: Named; headline?: Named; for: number; against: number; abstain: number; seats?: number;
  note?: Named; source?: Source; cites?: Cite[];
};
/** A door on the topic's page: what is happening, in people's words, or a tool. */
export type Door = {
  key: string; title: Named; lead?: Named; to?: string; tool?: boolean; open?: boolean; discreet?: boolean; checked?: Checked;
  /** Its words for an answer to the topic's question that sees it from the other side (PX38): the landlord's. */
  title_by?: Record<string, Named>;
  for?: string[];
  /** Its pictogram (kit/icons.tsx), drawn on the topic's page (T1 of the road tools review). */
  icon?: string;
  /** Reached by the topic's red band only, never listed among the tools. */
  urgent_only?: boolean;
  /** The road sign's family that says what kind of moment a door is (A5 of the road-signposted review): something happened
   *  (tri), a penalty (ring), a duty (disc), a procedure (square). A topic without signs draws its icon on a tile. */
  sign?: 'tri' | 'ring' | 'disc' | 'square' | Office | 'shield';
  /** Reached another way (the red band, a journey), so not among the doors or tools (A9). */
  listed?: boolean;
  /** `whole`: a page among the topic's texts, under «القانون كامل» (A9). */
  place?: 'whole';
  /** The one number the law sets for the door, on a punch card with its unit (E1 of the work-counted review); `by` gives an
   *  answer to the topic's question its own number (the minimum by the day on a farm). */
  mark?: Mark;
  /** Listed only for the answers its `for` names, first for the one whose `first` it is (E2 of the work-counted review). */
  own?: boolean;
  /** The land's drawing of the door's plot (the land review, M2). */
  plot?: string;
  /** Why the door fades for an answer it does not concern, in the law's words (the land review, M4). */
  not?: Named;
};
export type Mark = { value: string; unit: Named; by?: Record<string, { value: string; unit: Named }> };
/** A figure that is the reader's once they answered the topic's question, with the articles that set it (A4). */
export type ProfileFact = { value: string | Named; label: Named; cites: string[] };
/** A number to call, shown only with the official page that gives it (C1 of the road-signposted review). */
export type Urgent = {
  title: Named; lead?: Named; to: string;
  /** `ink`: the band in ink navy, nobody hurt (E5 of the work-counted review); `soil`: the land's dark earth, rights that close
   *  (the land review); `ochre`: the tax's dark ochre, a penalty the day after (the tax review); else the road's red. */
  tone?: 'ink' | 'soil' | 'ochre' | 'deep' | 'umber' | 'indigo' | 'slate' | 'pine';
  /** The words of the link to `tool` (work's «شنو كيتسالك» when none). */
  tool_label?: Named;
  /** A topic's yearly dates, the next two for the reader's answer drawn as rows with the days left (
   *  the tax review, T9): due the day before `before` (month-day), within the month `in`, or each quarter's next month. */
  dates?: { key: string; what: Named; before?: string; in?: string; quarterly?: boolean; for?: string[]; article: Named; cites: string[]; to: string }[];
  /** The papers that start a clock, each with its limit and articles (the land review, M5), drawn as rows. */
  papers?: { key: string; paper: Named; limit: Named; for: Named; article?: Named; cites: string[]; to: string }[];
  /** Drawn whole for these answers and for a reader who has not answered; one line for the others (C1). */
  for?: string[];
  /** The tool its second link opens («شنو كيتسالك»). */
  tool?: string;
  /** The day its journey counts from, asked on the band until the reader gives it («نهار توصلت بالمقرر؟»). */
  day?: Named;
  /** Its first acts, the answers of the journey's steps it names (A7). */
  acts?: Named[];
  numbers?: { number: string; name: Named; source: Source }[];
};
/** A dated change still to come (A11): the timeline entry and the change it belongs to. */
export type NextChange = { date: string; text: Named; change: string; title: Named };
/** One change a topic follows (T14 of the work plan): its stage first, among in force, coming, bill, announced. */
export type ChangeLine = { key: string; title: Named; stage: string; checked_on: string; line: Named };
/** The question that says which of the topic's rules are the reader's (T5): «فين خدام؟». */
export type Profile = { question: Named; /** «حنا» for a topic whose answers speak as «we» (G3), else «أنا». */ we?: Named; options: { key: string; label: Named; law: Named; to?: string; main?: boolean; first?: string; facts?: ProfileFact[] }[] };
export type Module = {
  events: Door[]; tools: Door[]; reform: { stage: string; checked_on: string; line: Named } | null;
  changes?: ChangeLine[]; profile?: Profile | null;
  /** The emergency, in a red band on top of the topic's page (T6). */
  urgent?: Urgent | null;
  /** The next dated changes (A11), soonest first. */
  next?: NextChange[];
  /** The last dated change already passed (E9 of the work-counted review), said when none is ahead. */
  last?: NextChange | null;
  /** How the doors' numbers are drawn: `tag`, a price tag (the consumer's); `plot`, the land's plot; `stamp`, a fiscal stamp
   *  (the tax's); else a punch card. */
  marks?: 'tag' | 'plot' | 'stamp' | 'vignette' | 'card' | 'cachet' | 'file' | 'bubble' | 'receipt' | null;
  /** The stages the doors stand in, in order (the life of a purchase); `links`: another topic's doors, as links. */
  stages?: { key: string; title: Named; doors: string[]; links?: boolean }[] | null;
  /** Learning the topic as one path (T4). */
  learn?: { to: string; title: Named; icon?: string }[];
  /** The page's question over its doors («شنو وقع ليك؟»), else the kit's. */
  doors_title?: Named | null;
  /** What people believe and what the law says (D3 of the consumer plan), as short cards. */
  beliefs?: { claim: Named; truth: Named; to: string }[];
};
/** Figures by the dates they are in force (T17): the minimum wage, the CNSS's rates and ceiling…, each row with its
 *  decree. A tool reads the row in force on the day it is asked about. */
export type RateRow = { from: string; to?: string; values: Record<string, number>; cites?: Cite[]; note?: Named;
  /** A bill's figure, never the law in force (the finance-bill review, P6): only a bill's tool reads it, by `billRow`. */
  proposed?: string };
export type Rates = Base & { unit?: Named; rows: RateRow[] };
export const inForce = (rows: RateRow[], on: string): RateRow | undefined =>
  rows.filter((r) => !r.proposed && r.from <= on && (!r.to || on < r.to)).sort((a, b) => b.from.localeCompare(a.from))[0];
/** A bill's row for a day: what the bill would set, said as a bill wherever it is shown. */
export const billRow = (rows: RateRow[], on: string): RateRow | undefined =>
  rows.filter((r) => r.proposed && r.from <= on && (!r.to || on < r.to)).sort((a, b) => b.from.localeCompare(a.from))[0];

/** A rate table's row in force on a day (T17 of the work plan): undefined while it loads. */
export function useRateOn(slug: string, key: string, on: string): Record<string, number> | undefined {
  const q = useRates(slug, key);
  return q.data ? inForce(q.data.rows, on)?.values : undefined;
}

/** The first day a rate table answers for (PX22 of the where-it-trips review): a tool clamps an earlier day to it and
 *  says so, where it turned into a skeleton for good. */
export function useRateStart(slug: string, key: string): string | undefined {
  const q = useRates(slug, key);
  return q.data ? q.data.rows.filter((r) => !r.proposed).map((r) => r.from).sort()[0] : undefined;
}

/** Where a topic keeps an item on the phone for use without a network (A17; G14 of the family-papers review: the
 *  protection page). */
export const keptKey = (slug: string, kind: string, key: string) => `law.kept.${slug}.${kind}.${key}`;

export function useKitItem<T>(slug: string, kind: string, key: string) {
  return useQuery({
    queryKey: ['topic', slug, kind, key],
    // Without a network, an item the topic kept on the phone opens from there.
    queryFn: () => api<T>(`/topics/${slug}/${kind}/${key}/`).catch((e) => {
      let kept: string | null = null;
      try { kept = localStorage.getItem(keptKey(slug, kind, key)); } catch { /* private window */ }
      if (kept) return JSON.parse(kept) as T;
      throw e;
    }),
    enabled: Boolean(slug && key),
    staleTime: 600_000,
  });
}

export const useRates = (slug: string, key: string) => useKitItem<Rates>(slug, 'rates', key);

/** A reference in a topic's folder («journeys/marry», «tools/dates», «reform/reform») as an address on the site. */
/** An item's page; «family:journeys/divorce» is another topic's (H17 of the housing plan). */
export const refPath = (slug: string, ref: string): string => {
  const [other, own] = ref.includes(':') ? ref.split(':', 2) : [slug, ref];
  return own === 'reform/reform' ? `/topics/${other}/reform` : `/topics/${other}/${own}`;
};
