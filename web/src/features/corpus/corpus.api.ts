import { useQuery } from '@tanstack/react-query';
import { api } from '@/shared/services/api';
import type { TextName } from './names';
import { firstWords } from './format';

export type TextRef = {
  id: number;
  akn_uri: string;
  /** The text's address on the site: /ma/loi/60-24. */
  path: string;
  type: string;
  type_label: string;
  number: string;
  number_as_printed: string;
  title: string;
  /** What people call it, else its title cut by words (P6 of the polish review). */
  name?: TextName | null;
  in_corpus: boolean;
};

export type IssueRef = {
  edition: string;
  edition_label: string;
  number: number;
  suffix: string;
  key: string;
  date: string;
  hijri_date: string;
  document_id: number;
  page_count: number | null;
  first_page_number: number | null;
  /** The last number the issue's cover bears, when it bears several («عدد 610 — 637»); in lists and the issue page. */
  last_number?: number | null;
};

export type IssueSummary = IssueRef & { texts: number };

export type IssueText = TextRef & {
  rubric: string;
  section: string;
  page: number | null;
  authority: string;
  signed_on: string | null;
  articles: number;
  amends: number;
};

export type IssuePage = { index: number; printed_number: number | null; kind: string; text_source: string };

/** `asked_for`: the number the address named when it is one of the numbers a cover bears beside its own («عدد 610 — 637»:
 *  /bo/general_ar/611 shows BO 610; C1 of the mended-Bulletin review). */
export type IssueDetail = IssueRef & { pages: IssuePage[]; texts: IssueText[]; asked_for?: string | null;
  /** For an issue kept by its pages alone: its own contents table as its first page prints it (W9 of
   *  the library-search review): a rubric («تقارير»), a heading, an entry led to its page. */
  contents?: { kind: 'rubric' | 'heading' | 'entry'; text: string; page: number | null }[] };

/** Where the body's words carry something: a citation (a link, or a text the corpus does not hold) or a term
 *  the text defines (`term` indexes `definitions`). Offsets are in the body's characters. */
export type Mark =
  | { kind: 'link'; start: number; end: number; href: string | null; state: string; title: string }
  | { kind: 'term'; start: number; end: number; term: number }
  /** A word that opens the law (R9 of the for-everyone review), its page at /words/<slug>: marked only once its meaning was
   *  checked, the meaning by register (HM35). */
  | { kind: 'word'; start: number; end: number; slug: string; means: Partial<Record<'ar' | 'fr' | 'darija', string>> };

export type ArticleItem = {
  id: number;
  order: number;
  label: string;
  number: string;
  heading_path: string[];
  body: string;
  eid: string;
  path: string;
  page: number | null;
  page_index: number | null;
  marks: Mark[];
  /** The reference as cited: «المادة 2 من القانون رقم 12.26 …، الجريدة الرسمية عدد … ص. …». */
  citation: string;
  /** How its page was read: from the PDF's own text, confirmed by it, not confirmed, or from a scan. */
  reading: 'layer' | 'confirmed' | 'unconfirmed' | 'scan' | 'short' | 'none' | null;
  /** The file its page belongs to: the BO issue, or the SGG's consolidated text. */
  document_id: number | null;
  /** Its history, oldest first: the SGG's notes and our readings of the amending texts. */
  changes: ArticleChange[];
  /** The texts that cite this article, and those that apply it (a decree «بتطبيق» the law, «ولا سيما المادة 5»). */
  cited_by: { from: LinkText; eid: string }[];
  applied_by: { from: LinkText; eid: string }[];
  /** What this version changed in it against the version before, word by word; null when nothing did. */
  diff: [op: '=' | '-' | '+', words: string][] | null;
  /** Its official French translation, from the BO's translation edition, when the corpus has it. */
  french: { label: string; body: string; page: number | null; older?: boolean } | null;
  /** The names the public debate gives it, for an article people know by its number (famous.py, F10). */
  known_as?: { ar: string[]; fr: string[] } | null;
  /** What a bill filed in Parliament proposes for it (the finance-bill review, P2): never part of its history. */
  proposed?: { bill: string; name: { ar: string; fr: string } | null; article: string; verb: string; effective_on: string | null; partial?: boolean } | null;
};

/** What the evidence allows a link (row L9 of the links review): checked, confirmed and read are shown as fact. */
export type LinkState = 'checked' | 'confirmed' | 'read' | 'conflict' | 'unclear' | '';
export const SHOWN_STATES: LinkState[] = ['checked', 'confirmed', 'read'];

export type ArticleChange = {
  /** Shown as fact, and its words are not in the copy shown (RD2 of the readers review): said under the article. */
  missing?: boolean;
  on: string | null;
  verb: 'modified' | 'added' | 'replaced' | 'repealed' | 'words';
  sources: ('sgg' | 'adala' | 'dgi' | 'reading')[];
  verdict: '' | 'agrees' | 'partly' | 'disagrees' | 'absent';
  score: number | null;
  by_article: string;
  by: { kind: string; number: string; path: string | null; title: string };
  issue: { number: number | null; bis: boolean; page: number | null; path: string | null };
  /** Our reading: its state, the day it takes effect and how that day was found, and why it is not placed. */
  state: LinkState;
  effective_on: string | null;
  rule: '' | 'publication' | 'stated' | 'after' | 'condition';
  when: string;
  waiting: null | 'no_base' | 'condition' | 'official';
  placed: boolean | null;
};

/** A text a link names: its page when the site holds it, else its kind and number. */
export type LinkText = { path: string | null; title: string; type: string; number: string; status: string; in_corpus: boolean };
export type IssueStamp = { number: number | null; bis: boolean; page: number | null; key: string | null };
export type AmendedBy = {
  by: LinkText; issue: IssueStamp; published_on: string | null; effective_on: string | null;
  rule: ArticleChange['rule']; when: string; articles: string[]; verbs: ArticleChange['verb'][]; whole: boolean; state: LinkState;
  /** Its changes not shown as fact: a conflict with another source, or one the code could not read. */
  held_back: number;
};
export type LinkFrom = { from: LinkText; articles: string[]; count: number; words: string };
export type RepealNote = {
  by: LinkText; by_article: string; issue: number | null; issue_bis: boolean; page: number | null; on: string | null;
  rule: ArticleChange['rule']; words: string; state: LinkState;
};
/** Where a text stands (rows L5–L7): its status from what the site has read, and how much of the BO that is. */
export type Standing = {
  status: 'in_force' | 'repealed' | 'partly_repealed' | 'not_yet_in_force' | 'unknown';
  repealed?: RepealNote;
  repeal_pending?: RepealNote;
  in_force_on?: string;
  in_force_when?: string;
  changes: number;
  last: AmendedBy | null;
  /** What the site has read since the text: the first unread issues (`missing`, up to 40), how many in all, and
   *  `partial` when too many to call it «in force» (UX3 of the phone-test review). */
  /** Whether «in force» may be said when no repeal was found: an official portal's copy, or printed since 2019 (RD6). */
  sure?: boolean;
  coverage: { before: boolean; from: string; latest: { key: string; date: string } | null; missing: { key: string; date: string }[];
    missing_count?: number; partial?: boolean; unfound: number; waiting: number };
};

export type VersionKind = 'as_published' | 'sgg' | 'adala' | 'dgi' | 'machine' | 'checked' | 'bill' | 'translation';
export type VersionItem = { valid_from: string; valid_to: string | null; consolidation: VersionKind; current: boolean; as_of: string | null };

export type Definition = { term: string; eid: string; definition: string };

export type IssueQuality = IssueRef & {
  pages: { index: number; printed: number | null; reading: string; suspect: number }[];
  counts: Record<'layer' | 'confirmed' | 'unconfirmed' | 'scan' | 'short' | 'none', number>;
  not_found: { title: string; page: number | null }[];
  texts: number;
  open_reports: number;
};

export type Preview = {
  text: TextRef; label: string | null; path: string; heading_path: string[]; excerpt: string;
  /** Its stamp: the BO issue and page, or the consolidation it comes from. */
  issue: string | null; consolidation: VersionKind | null; page: number | null;
};

export type TextDetail = TextRef & {
  /** Its name in the browser's title, a search result's too (IX8 of the search-engines review): the everyday name, else the
   *  title without its date clause, as the server's head says it. */
  title_name?: string;
  /** What people call it, when it is a code or one of the shelf's texts (R4 of the for-everyone review). */
  everyday_name: { ar: string; fr: string } | null;
  /** The texts a code has been, oldest first, when this is one of them: the constitutions since 1962. */
  eras?: Era[] | null;
  /** What a constitution's opening says (C2 of the constitution review): its referendum, dahir and printing. */
  constitution?: {
    name: { ar: string; fr: string }; year: number; referendum: string; signed: string; published: string;
    issue: string; page: number; dahir: string; cited_as: string;
    /** Its chapter of the short history (C4), and who read it against the texts (empty: a draft). */
    story?: { ar: string; fr: string } | null; checked?: string;
  } | null;
  /** A shelf text the site has not loaded: its file on Adala (P7 of the polish review). */
  official: string | null;
  /** The article the address opened on (…/art_8), or ''. */
  focus: string;
  citation: string;
  definitions: Definition[];
  signed_on: string | null;
  signed_on_hijri: string;
  authority: string;
  promulgating_dahir: string;
  rubric: string;
  status: string;
  issue: IssueRef | null;
  page: number | null;
  page_index: number | null;
  version: {
    language: string;
    valid_from: string;
    valid_to: string | null;
    consolidation: VersionKind;
    consolidation_label: string;
    /** A copy of the text as first issued (a constitution before 2011), not assembled from amendments. */
    as_issued?: boolean;
    /** Its words were read by a model from the images of an archive issue's pages (1956–2018). */
    read_from_scans?: boolean;
    /** The language a model translated this version from (BO 7410's texts, from the official French); '' when not. */
    translated_from?: string;
    translated_at?: string | null;
    source_pages: string;
    preamble: string;
    closing: string;
    /** The SGG's file a consolidation was read from, and where the text first appeared. */
    source: { document_id: number; url: string; as_of: string | null; first_issue: number | null; first_page: number | null } | null;
    before: { valid_from: string; consolidation: VersionKind } | null;
  } | null;
  versions: VersionItem[];
  /** The official explanations beside the law: the bill's explanatory memorandum as filed with Parliament. */
  explanations: { kind: 'memorandum'; body: string; source_url: string; pages: string }[];
  /** The official French translation: the translation edition's issue that printed it. */
  french: { title: string; issue_number: number; issue_suffix: string; issue_date: string; pages: string; document_id: number | null;
    /** A consolidation (Adala's French labour code) stands at this date; null for the BO's translation. */
    consolidated_to?: string | null } | null;
  /** The bill as filed with the Chamber of Representatives, and its page there. */
  bill: { url: string; document_id: number; page: string | null } | null;
  articles: ArticleItem[];
  /** All the text's articles: more than `articles` holds for a long text or an article's prerendered page. */
  total_articles: number;
  /** Where `articles` sit among all of them: [from, to). */
  range?: [number, number];
  /** Every article's anchor and label, when `articles` holds only some: its heading path where it changes. The API
   *  sends it at its own address (`outline_url`, kept for good); the prerender puts it here. */
  outline?: OutlineRow[] | null;
  outline_url?: string | null;
  standing: Standing;
  /** Changes to the whole text (a repeal, a swap of words throughout). */
  whole_changes: ArticleChange[];
  amends: { target: LinkText; changes: { number: string; verb: ArticleChange['verb']; state: LinkState; effective_on: string | null;
    rule: ArticleChange['rule']; placed: boolean | null; waiting: ArticleChange['waiting'] }[] }[];
  amended_by: AmendedBy[];
  cites: { to: LinkText; count: number }[];
  cited_by: LinkFrom[];
  cited_by_count: number;
  applied_by: LinkFrom[];
  redirected_by: LinkFrom[];
  kept_by: LinkFrom[];
  corrected_by: LinkFrom[];
  ruled_on_by: LinkFrom[];
};

export type PageDetail = {
  document_id: number;
  index: number;
  printed_number: number | null;
  page_count: number;
  kind: string;
  text: string;
  text_source: string;
  /** A file's own text layer (Adala's, the SGG's) after the repairs its articles had (P14 of the polish review). */
  repaired?: boolean;
  source?: string;
  language: string;
  layer_letters: number;
  /** Who read the page: «ai» for any model, never its name. */
  read_by: { engine: 'ai' | 'tesseract'; variant: 'page' | 'columns' | 'turned' } | null;
  check: (({ letters: number } | { amounts_read: number; amounts_in_layer: number }) & { suspect?: string[] }) | null;
  ocr_runs: { engine: 'ai' | 'tesseract'; variant: string; chars: number }[];
  issue: { edition: string; number: number; suffix: string; key: string; date: string } | null;
  texts: { id: number; path: string; title: string; number_as_printed: string; type_label: string }[];
};

export const ARTICLE_WINDOW = 30;

/** `w`: the article's first words (P12 of the polish review). */
/** One of the texts a code has been, with when it stood and how long it is (characters), for the drawing to scale. */
export type Era = { path: string; year: number | null; name: TextName; current: boolean; here: boolean;
                    from: string | null; until: string | null; size: number };

export type OutlineEntry = { eid: string; label: string; number: string; heading_path: string[]; w: string };
export type OutlineRow = { eid: string; label: string; number: string; w?: string; h?: string[] };

/** The whole text's outline: the API's when it sent only some articles (empty while it comes), else the articles'. */
export function outlineOf(d: TextDetail, sent?: OutlineRow[] | null): OutlineEntry[] {
  const rows = d.outline ?? sent;
  if (!rows) return d.outline_url ? [] : d.articles.map((a) => ({ eid: a.eid, label: a.label, number: a.number, heading_path: a.heading_path, w: firstWords(a.body) }));
  let last: string[] = [];
  return rows.map((o) => {
    if (o.h) last = o.h;
    return { eid: o.eid, label: o.label, number: o.number, heading_path: last, w: o.w ?? '' };
  });
}

/** One of the twenty texts readers look for most, and where it stands on the site (row 3). */
export type ShelfItem = {
  key: string;
  name: { ar: string; fr: string };
  /** Its articles on the site (a spine's width); 0 when the site does not hold it. */
  articles: number;
  state: 'in_corpus' | 'title_only' | 'not_in_corpus';
  path: string | null;
  number_as_printed: string;
  type: string | null;
  status: string | null;
  /** Where to read it while the site does not hold it: Adala, the Ministry of Justice's portal. */
  official: string | null;
};

/** A situation readers meet and the articles to read first (row 4), each said in a sentence. */
export type Situation = {
  slug: string;
  title: { ar: string; fr: string };
  intro: { ar: string; fr: string };
  /** Claude Haiku's draft no editor has approved yet (shown only while developing). */
  draft: boolean;
  articles: { path: string; label: string; says: { ar: string; fr: string };
              text: { title: string; path: string; number_as_printed: string; type: string } }[];
  shelf: ShelfItem[];
  /** Its life topic (R2 of the for-everyone review). */
  topic?: string;
  /** The step-by-step guide (R10), each line naming the articles it restates; null until someone wrote one. */
  guide?: { steps?: GuideLine[]; deadlines?: GuideLine[]; documents?: GuideLine[]; where?: GuideLine[]; costs?: GuideLine[];
            help?: GuideLine[] } | null;
};
export type GuideLine = { ar: string; fr: string; paths?: string[] };

export const corpusApi = {
  issues: () => api<IssueSummary[]>('/corpus/issues/'),
  issue: (edition: string, number: string) => api<IssueDetail>(`/corpus/issues/${edition}/${number}/`),
  text: (id: string) => api<TextDetail>(`/corpus/texts/${id}/`),
  /** A long text comes as a window of articles from the one asked for, the rest as the reader goes (row 7). */
  textAt: (address: string, on = '') =>
    api<TextDetail>(`/corpus/at${address}/?${new URLSearchParams({ window: String(ARTICLE_WINDOW), ...(on ? { on } : {}) })}`),
  articles: (textPath: string, from: number, count: number, on = '') =>
    api<{ articles: ArticleItem[]; range: [number, number]; total_articles: number }>(
      `/corpus/at${textPath}/?${new URLSearchParams({ from: String(from), count: String(count), ...(on ? { on } : {}) })}`),
  outline: (url: string) => api<{ outline: OutlineRow[] }>(url.replace(/^\/api/, '')),
  shelf: () => api<ShelfItem[]>('/corpus/shelf/'),
  situations: () => api<Situation[]>('/corpus/situations/'),
  issueQuality: (edition: string, key: string) => api<IssueQuality>(`/corpus/issues/${edition}/${key}/quality/`),
  preview: (path: string) => api<Preview>(`/corpus/preview/?path=${encodeURIComponent(path)}`),
  page: (documentId: string, index: string) => api<PageDetail>(`/sources/documents/${documentId}/pages/${index}/`),
};

/** Where an article stands on its page, as shares of it (U14 of the Moroccan-design review): null when its heading
 *  was not found. Asked after the page is drawn; the band comes when it answers. */
export type Region = { top: number; bottom: number; left: number; right: number };
export function useRegion(documentId: string, index: string, label: string | null) {
  return useQuery({
    queryKey: ['region', documentId, index, label], enabled: Boolean(label), staleTime: Infinity,
    queryFn: () => api<{ region: Region | null }>(`/sources/documents/${documentId}/pages/${index}/region/?label=${encodeURIComponent(label ?? '')}`),
  });
}

export const pageImageUrl = (documentId: number | string, index: number | string) =>
  `/api/sources/documents/${documentId}/pages/${index}/image/`;
/** The page for reading, WebP at a phone's or a desk's width (U16 of the Moroccan-design review). */
export const pageImageSet = (documentId: number | string, index: number | string) =>
  `${pageImageUrl(documentId, index)}?w=900 900w, ${pageImageUrl(documentId, index)}?w=1600 1600w`;

/** The phone asks for less data («Save-Data», a data saver): pages show their read text first, images on a tap. */
export const savingData = () =>
  typeof navigator !== 'undefined' && Boolean((navigator as Navigator & { connection?: { saveData?: boolean } }).connection?.saveData);
export const documentFileUrl = (documentId: number) => `/api/sources/documents/${documentId}/file/`;

/** The law changes with the Bulletin, not by the minute: its answers stay fresh ten minutes and coming back to the tab
 *  does not ask again (S18 of the performance audit: each return re-sent up to 320 KB). */
const LAW = { staleTime: 600_000, refetchOnWindowFocus: false } as const;

export const useIssues = () => useQuery({ queryKey: ['issues'], queryFn: corpusApi.issues, ...LAW });
export const useShelf = () => useQuery({ queryKey: ['shelf'], queryFn: corpusApi.shelf, staleTime: 600_000 });
export const useSituations = () => useQuery({ queryKey: ['situations'], queryFn: corpusApi.situations, staleTime: 600_000 });
export const useIssue = (edition: string, number: string) =>
  useQuery({ queryKey: ['issue', edition, number], queryFn: () => corpusApi.issue(edition, number), ...LAW });
export const useText = (id: string) =>
  useQuery({ queryKey: ['text', id], queryFn: () => corpusApi.text(id), enabled: Boolean(id), ...LAW });
/** A text by its address; the article part (…/art_8) only says where to open, so it shares the text's cache. */
export const useTextAt = (textPath: string, focus: string, on = '') =>
  useQuery({ queryKey: ['textAt', textPath, on], queryFn: () => corpusApi.textAt(focus ? `${textPath}/${focus}` : textPath, on), ...LAW });
export const usePreview = (path: string | null) =>
  useQuery({ queryKey: ['preview', path], queryFn: () => corpusApi.preview(path!), enabled: Boolean(path), staleTime: 300_000 });
export const useIssueQuality = (edition: string, key: string) =>
  useQuery({ queryKey: ['issueQuality', edition, key], queryFn: () => corpusApi.issueQuality(edition, key), ...LAW });
export const usePage = (documentId: string, index: string) =>
  useQuery({ queryKey: ['page', documentId, index], queryFn: () => corpusApi.page(documentId, index), ...LAW });
