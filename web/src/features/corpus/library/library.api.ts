import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { api } from '@/shared/services/api';
import { archive, type Archive, type RawMap } from './map';

/** A book of the library's piles (GET /api/corpus/library/, LB3–LB7 of the every-code review). */
export type Book = {
  key: string;
  name: { ar: string; fr: string };
  /** The other names people give it: the box reads them. */
  aliases: string[];
  /** The general text of its branch, at the base of the pile. */
  base: boolean;
  /** On the shelf of twenty before the library had 67. */
  shelf: boolean;
  path: string | null;
  state: 'in_corpus' | 'title_only' | 'not_in_corpus';
  type: string | null;
  number: string;
  status: string | null;
  articles: number;
  /** The version a reader opens: from when, and who brought it up to date (as_published, adala, sgg, dgi, machine). */
  version: { from: string; kind: string } | null;
  /** How many texts changed it, and the newest change shown as fact that has taken effect. */
  changes: number;
  last_change: string | null;
  /** A change on record after the version a reader opens (LB5). */
  stale: boolean;
  issue: { number: number; suffix: string; key: string; date: string } | null;
  page: number | null;
  /** A page of its own beside the law (the finance law's figures). */
  extra: string | null;
};
export type Branch = {
  key: string;
  name: { ar: string; fr: string };
  base: string | null;
  books: Book[];
  /** The texts the branch's books replaced, drawn dashed under the pile (LB7). */
  replaced: { name: { ar: string; fr: string }; path: string; years: string }[];
};

/** A book's card (LB6): how courts cite it, where it was printed, its parts, its newest change, its French. */
export type BookCard = {
  path: string;
  citation: string;
  issue: { number: number; suffix: string; key: string; date: string } | null;
  page: number | null;
  articles: number;
  parts: { heading: string; eid: string; number: string; articles: number }[];
  version: { from: string; kind: string; as_of: string | null } | null;
  changes: number;
  last: { on: string; path: string | null; type: string | null; number: string; title: string;
          issue: { number: number; bis: boolean; page: number | null } | null } | null;
  french: { issue: number; suffix: string; date: string; to: string | null } | null;
};

const KEPT = { staleTime: 600_000, refetchOnWindowFocus: false } as const;

/** One of the newest issues as it is (W9 of the library-search review): what it holds, and for an issue kept by its pages
 *  alone the line its own contents table prints. */
export type Newest = { number: number; suffix: string; key: string; date: string; hijri: string; texts: number; pages: number; about: string };
export type Library = {
  branches: Branch[];
  /** The dozen under the box (C5): keys of books, the most asked first. */
  most: string[];
  newest: Newest[];
  /** When the nightly fetch last asked the SGG's list, and the newest issue the list named. */
  asked: { at: string; newest: string; newest_date: string } | null;
};

export const useLibrary = () => useQuery({ queryKey: ['library'], queryFn: () => api<Library>('/corpus/library/'), ...KEPT });

/** A text the server's reader found (GET /api/corpus/find/, W3–W6): sure or not, and why it was offered. */
export type FoundBrief = {
  path: string; type: string; number: string; name: { ar: string; fr: string | null }; subject: string;
  signed_on: string | null; hijri: string; status: string;
  issue: { number: number; suffix: string; key: string; date: string } | null; page: number | null;
  /** Its key among the library's books, when it is one. */
  book: string | null;
};
export type FoundText = FoundBrief & { kind: 'text'; sure: boolean; why: string; former: string; cited: number | null };
export type FoundArticle = { kind: 'article'; sure: boolean; path: string; label: string; state: 'found' | 'text_only'; asked?: string; text: FoundBrief };
export type FoundIssue = { kind: 'issue'; sure: boolean; key: string; edition: string; date: string; path: string; number: number; suffix: string };
export type FoundNote = { kind: 'note'; code: string; year?: number; date?: string; n?: number; number?: string; type?: string };
export type Understood = {
  read_as?: string; short?: boolean; finance?: number; bill?: boolean; article?: string; number?: string; promulgated_by?: string;
  year?: number; kind?: string; newest?: boolean;
  day?: { date: string; hijri: string; estimate: boolean; kind: string };
};
export type Found = { query: string; understood: Understood; answers: (FoundText | FoundArticle | FoundIssue | FoundNote)[] };

/** What the words name, read on the server: asked once the reader pauses, kept ten minutes. */
export const findQuery = (q: string) => ({ queryKey: ['find', q], ...KEPT, retry: 1, queryFn: () => api<Found>(`/corpus/find/?q=${encodeURIComponent(q)}`) });
export const useFind = (q: string) => useQuery({ ...findQuery(q), enabled: q.length >= 2 });

/** A year's laws and dahirs (GET /api/corpus/years/<year>/, W8). */
export type YearText = { path: string; type: string; number: string; name: { ar: string; fr: string | null } | null; subject: string;
  signed_on: string | null; status: string; cited: number; issue: { number: number; suffix: string; key: string } | null; page: number | null };
export type YearTexts = { year: number; counts: Record<string, number>; texts: YearText[]; most_cited: string[] };
export const useYearTexts = (year: number | null) => useQuery({
  queryKey: ['year-texts', year], enabled: year !== null, ...KEPT,
  queryFn: () => api<YearTexts>(`/corpus/years/${year}/`),
});

export const useBookCard = (path: string | null) => useQuery({
  queryKey: ['library-card', path], enabled: !!path, ...KEPT,
  queryFn: () => api<BookCard>(`/corpus/library/card/?path=${encodeURIComponent(path!)}`),
});

/** Every issue held, decoded once (LB13): the strata, /bo, an issue's neighbours and the box read it. */
export const useArchive = () => useQuery({
  queryKey: ['issue-map'], ...KEPT,
  queryFn: async (): Promise<Archive> => archive(await api<RawMap>('/corpus/issues/map/')),
});

/** A count as the Bulletin prints it: «7.734» in Arabic, «7 734» in French (never an issue's number or a year). */
export function useNum() {
  const { i18n } = useTranslation();
  const nf = new Intl.NumberFormat(i18n.language === 'fr' ? 'fr-MA' : 'ar-MA');
  return (n: number) => nf.format(n);
}

/** A range of numbers inside Arabic words, kept left to right as printed («5801–5904», never «5904–5801»). */
export const span = (from: number | string, to: number | string) => `${String.fromCharCode(0x2066)}${from}–${to}${String.fromCharCode(0x2069)}`;

/** What a reader will read, in words: «محيَّن إلى 2026» or «كما نُشر سنة 2018» (W7: no glyph to learn). */
export function state(book: Book, t: (k: string, o?: Record<string, unknown>) => string): string {
  if (!book.version) return '';
  const year = book.version.from.slice(0, 4);
  return t(book.version.kind === 'as_published' ? 'pages:lib4.index.printed' : 'pages:lib4.index.updated', { year });
}

/** Whether the shelves show each text's number, size and state: the reader's choice, kept on the device. */
export function useDetail(): [boolean, () => void] {
  const KEY = 'law.library.detail';
  const [on, setOn] = useState(() => { try { return localStorage.getItem(KEY) === '1'; } catch { return false; } });
  return [on, () => setOn((was) => { try { localStorage.setItem(KEY, was ? '0' : '1'); } catch { /* not kept */ } return !was; })];
}
