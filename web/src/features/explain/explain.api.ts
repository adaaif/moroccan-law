import { keepPreviousData, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '@/shared/services/api';
import { useSession } from '@/shared/stores/session';

/** How it is said: plain standard Arabic, Darija, French. The law stays as printed in every register. */
export type Register = 'ar' | 'darija' | 'fr';
export const REGISTERS: Register[] = ['ar', 'darija', 'fr'];

/** An explanation as a page beside the law shows it (R8 of the for-everyone review): checked by a reviewer. */
export type Short = {
  register: Register;
  headline: string;
  body: string;
  sources: string[];
  checked_on: string | null;
  helpful: number;
  /** The article changed after it was written. */
  outdated: boolean;
  editors: number;
};
export type Bundle = { text: Partial<Record<Register, Short>>; articles: Record<string, { registers: Partial<Record<Register, Short>> }> };

/** A state of an explanation. Readers see the checked ones; its author and the text's reviewers see the others too,
 *  with what the fixed patterns or the check found (the discussion's hold codes), and a reviewer its open reports. */
export type Revision = {
  id: number; body: string; headline: string; sources: string[]; note: string; created_at: string; author: string | null;
  state: 'checked' | 'waiting' | 'unchecked' | 'removed'; held_reasons?: string[]; rule?: string | null; reports?: number;
};
/** The edit that waits for a reviewer, for its author and the reviewers only. */
export type Pending = { id: number; headline: string; body: string; sources: string[]; note: string; created_at: string;
                        author: string | null; mine: boolean; held_reasons: string[] };
/** `waiting`: nothing checked yet, so the words above are the edit that waits (its author's and the reviewers' to
 *  read). `shown_id`: the state readers see, to report. */
export type Full = Short & { waiting: boolean; voted: boolean; shown_id: number | null; pending: Pending | null; history: Revision[] };
export type Detail = { path: string; kind: 'article' | 'text' | 'word'; text_path: string; registers: Partial<Record<Register, Full>>;
                       can_edit: boolean; can_review: boolean; can_report: boolean;
                       /** false: the first state asks for the agreement that the artificial intelligence reads it. */
                       consent: boolean };

export type Concept = {
  slug: string; term: { ar: string; fr: string } | null; search: string; topic: string; built_in?: boolean; written?: boolean;
  /** The checked meaning by register, sent with the list so it reads as a glossary. */
  means?: Partial<Record<'ar' | 'fr' | 'darija', string>> | null;
};

export const useBundle = (textPath: string) =>
  useQuery({ queryKey: ['explain', 'text', textPath], queryFn: () => api<Bundle>(`/explain/text/?path=${encodeURIComponent(textPath)}`),
             staleTime: 300_000 });

export function useDetail(path: string) {
  const signedIn = useSession((s) => s.tokens !== null);
  return useQuery({ queryKey: ['explain', 'at', path, signedIn], queryFn: () => api<Detail>(`/explain/at/?path=${encodeURIComponent(path)}`),
                    enabled: Boolean(path) });
}

export const useWords = () =>
  useQuery({ queryKey: ['explain', 'words'], queryFn: () => api<{ concepts: Concept[] }>('/explain/words/'), staleTime: 600_000 });
export const useWord = (slug: string) =>
  useQuery({ queryKey: ['explain', 'word', slug], queryFn: () => api<{ concept: Concept; registers: Partial<Record<Register, Short>> }>(`/explain/words/${slug}/`),
             enabled: Boolean(slug), retry: false });

export const explainApi = {
  save: (body: { path: string; register: Register; body: string; headline?: string; sources?: string[]; note?: string; consent?: boolean }) =>
    api<Detail>('/explain/save/', { method: 'POST', json: body }),
  check: (path: string, register: Register) => api<Detail>('/explain/check/', { method: 'POST', json: { path, register } }),
  report: (revision: number, reason: string, details: string) =>
    api<{ ok: boolean }>('/explain/report/', { method: 'POST', json: { revision, reason, details } }),
  act: (revision: number, act: 'remove' | 'keep', rule?: string) =>
    api<Detail>('/explain/act/', { method: 'POST', json: { revision, act, rule } }),
  helpful: (path: string, register: Register, on: boolean) =>
    api<{ helpful: number; voted: boolean }>('/explain/helpful/', { method: on ? 'POST' : 'DELETE', json: { path, register } }),
};

/** After a change, the page and the text's bundle are read again. */
export function useRefresh() {
  const client = useQueryClient();
  return () => client.invalidateQueries({ queryKey: ['explain'] });
}

/** The register a reader meets first: French for a French reader, else plain Arabic, else Darija. */
export function firstRegister(have: Partial<Record<Register, unknown>>, lang: string): Register | null {
  const order: Register[] = lang === 'fr' ? ['fr', 'ar', 'darija'] : ['ar', 'darija', 'fr'];
  return order.find((r) => have[r]) ?? null;
}

/** A week of the Bulletin (R13): the texts told in plain words first, the rest for specialists; since 1 Nov 2026 the
 *  special section's texts too, each series of one form marked (`series`, named in it by `part`), a text that makes
 *  rules with its first article's first words. */
export type WeekText = {
  path: string; type: string; title: string; title_fr: string; number: string; section: 'general' | 'special';
  issue: { number: number; suffix: string; date: string; key: string }; page: number | null;
  topic: { slug: string; name: { ar: string; fr: string } } | null;
  changes: { path: string; name: { ar: string; fr: string } }[];
  applies: { path: string; name: { ar: string; fr: string } }[];
  told: Partial<Record<Register, { headline: string; body: string }>> | null;
  series: string | null; part: string;
  first: { label: string; body: string } | null;
};
export type WeekSeries = { head: string; size: number; issuers: { name: string; count: number }[] };
export type WeekIssue = {
  number: number; suffix: string; date: string; key: string; edition: string; special: number;
  hijri: string; first_page: number | null; pages: number | null;
};
export type Week = {
  from: string; to: string; prev: string | null; next: string | null;
  issues: WeekIssue[];
  people: WeekText[]; rest: WeekText[]; special_texts: WeekText[]; series: Record<string, WeekSeries>;
  /** The weeks around this one, oldest first: each Monday, its issues and pages. */
  weeks: { from: string; issues: number; pages: number }[];
};
export const useWeek = (day: string) =>
  // Stepping to another week keeps the one read on screen until the next comes.
  useQuery({ queryKey: ['explain', 'week', day], queryFn: () => api<Week>(`/explain/week/${day ? `?day=${day}` : ''}`), staleTime: 600_000,
             placeholderData: keepPreviousData });
