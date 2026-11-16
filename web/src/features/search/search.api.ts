import { keepPreviousData, useQuery, type QueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { api } from '@/shared/services/api';
import type { TextName } from '@/features/corpus/names';

export type TextBrief = {
  /** A corpus row's id; search answers name a text by its address alone (B24 of the search plan). */
  id?: number;
  path: string;
  type: string;
  title: string;
  /** What people call it, else its title cut by words (P6 of the polish review). */
  name?: TextName | null;
  number_as_printed: string;
  status: string;
  in_corpus: boolean;
  year?: number | null;
};

/** A citation matched to the corpus (apps/corpus/services/citations.py). */
export type Resolved = {
  citation: { kind: string; raw: string; article: string | null; text_number: string | null; code: string | null; issue: number | null };
  state: 'found' | 'text_only' | 'not_in_corpus' | 'issue' | 'repealed' | 'unknown';
  name: { ar: string; fr: string } | null;
  text: TextBrief | null;
  article: { label: string; eid: string; path: string } | null;
  issue: { key: string; edition: string; date: string; path: string } | null;
  changes: { action: string; label: string; by: TextBrief; published: string | null; issue: string | null }[];
  /** Where to read a code the site does not hold yet (Adala, the Ministry of Justice's portal). */
  official?: string | null;
  /** A famous article offered while typing: the names the public debate gives it (famous.py, F7). */
  known_as?: { ar: string[]; fr: string[] };
};

/** An article people know by its number or a name (back/apps/search/services/famous.py, 9 Nov 2026): its law's own
 *  words, the public's names for it, its changes as the Bulletin printed them, a bill's proposal, the articles citing it. */
export type FamousCard = {
  path: string; label: string; number: string; code: string; page: number | null; heading_path: string[];
  text: (TextBrief & { issue: string | null; consolidation: string | null }) | null;
  body: string;
  french: { label: string; body: string } | null;
  known_as: { ar: string[]; fr: string[] };
  changes: { verb: string; by: TextBrief | null; published: string | null; issue: string | null; page: number | null }[];
  proposed: { by: TextBrief | null; verb: string }[];
  cited_by: { label: string; path: string; text: TextBrief | null }[];
  cited_more: number;
};

/** `num`: a number the law states, in bold in the box that answers first (B15 of the search plan). */
export type Segment = { t: string; hit: boolean; num?: boolean };

/** How an article was found: by the question's words, by its meaning, or both (B15). */
export type FoundBy = 'words' | 'meaning' | 'both';

/** An article an amending article changes, as the index read it from the sound changes (B16 of the search plan). */
export type Changed = { path: string; label: string; verb: string; name: TextName };

export type SearchResponse = {
  query: string;
  jump: Resolved | null;
  /** The famous articles a number or a name asks for, shown first (F5, F6). Absent from an answer kept before. */
  famous?: FamousCard[];
  /** A word the law uses for an article that everyday speech reads otherwise («الفساد»): «did you mean». */
  maybe?: { path: string; label: string; body: string; text: TextBrief | null; known_as: { ar: string[]; fr: string[] } }[];
  /** An article number asked without its code: the shelf's codes holding one, those on a card apart (F3). */
  choices?: { number: string; texts: { label: string; path: string; text: TextBrief }[]; more: number };
  understood_as: 'words' | 'citation' | 'repaired' | 'everyday' | 'some_words' | 'arabizi' | 'meaning' | 'spelling' | 'exact';
  /** The question in Arabic letters, when it was Darija typed in Latin letters (B6 of the search plan). */
  arabizi?: string;
  repaired: string | null;
  /** This search's anonymous row, to say which answer it led to. */
  log: number | null;
  /** The words searched once the asking words («واش», «est-ce que») were set aside; null when none were. */
  asked: string | null;
  /** The words typed between quotes, searched as typed and side by side (31 Oct 2026). Absent from an answer kept before. */
  exact?: string[];
  /** The life topics the question names in everyday words, Darija included: a hint above the results (R1–R2). */
  topics?: { slug: string; name: { ar: string; fr: string }; situations?: { slug: string; title: { ar: string; fr: string }; draft?: boolean }[] }[];
  /** The articles the first door's answer rests on (U17 of the Moroccan-design review), shown right under it. */
  door_articles?: { path: string; label: string; number: string; text: { ar: string; fr: string }; body: string;
    /** Its official French, on a French page, when the site holds it (RD12 of the readers review). */
    french?: { label: string; body: string } }[];
  /** The doors and tools the question names (X1 of the road tools review): answered above the texts. */
  /** A state or a Moroccan place the question names whole (apps/places, PL21). */
  place?: import('@/features/places/places.api').PlaceCard | null;
  doors?: { slug: string; title: { ar: string; fr: string }; lead?: { ar: string; fr: string } | null; icon?: string | null; topic: string; ref: string; path: string;
    /** The law's figure the door carries on its topic's page (17,92 درهم للساعة): drawn on the answer too (RD7). */
    mark?: { value?: string; unit?: { ar: string; fr: string } } | null }[];
  /** No door names the question: the nearest moments, asked back first (HM8 of the hard-moment review). */
  nearest?: { slug: string; title: { ar: string; fr: string }; lead?: { ar: string; fr: string } | null; topic: string; ref: string; path: string }[];
  /** The topic's words of the law, each with the article of its texts that holds it best (P9 of the polish review). */
  words?: TopicWord[];
  /** The question as typed, the law's words under its everyday forms (30 Oct 2026); empty when none is in it. */
  said?: { t: string; law?: string }[];
  /** Whether the words filled every entry a search reads: the counts by kind are then lower bounds (PX17). */
  capped?: boolean;
  /** The questions people asked already in the first topic's place, each with its best answer (30 Oct 2026). */
  people?: { id: number; title: string; body: string; path: string; created_at: string; answers: number; useful: number;
             answer: { body: string; accepted: boolean; useful: number } | null }[];
  /** The results hold some of the words, not all. */
  partial: boolean;
  /** The question asks for another country's law (RD11): the site says what it holds first. */
  foreign?: boolean;
  /** Words about violence: counted, never kept as typed, here or on the device (F14 of the family plan). */
  private?: boolean;
  texts: number;
  /** Texts found of each kind (`law`, `decree`…), for the filters' row (B15). */
  kinds?: Record<string, number>;
  /** The box that answers first (B15): the first article's sentence that answers the question best, in the law's
   *  words, the number in bold when it asks how much or how long; only when the words and the meaning agree. */
  answer?: {
    path: string; label: string; page: number | null; found_by: FoundBy; amount: boolean; sentence: Segment[];
    text: TextBrief & { issue: string | null; consolidation: string | null };
  } | null;
  articles: number;
  page: number;
  pages: number;
  results: {
    /** With its stamp: the BO issue that printed it, and its version (as published, or a consolidation). */
    text: TextBrief & { issue: string | null; consolidation: string | null };
    title_match: boolean;
    /** `page`: where an article as published was printed. */
    articles: { label: string; eid: string; path: string; heading_path: string[]; page: number | null; snippet: Segment[];
                french?: { label: string; snippet: Segment[] };
                found_by?: FoundBy;
                /** An amending article: the articles it changes (B16 of the search plan). */
                changes?: Changed[] }[];
    /** The text's other articles that hold the words. */
    more: number;
  }[];
};

export type TopicWord = {
  slug: string;
  term: { ar: string; fr: string };
  search: string;
  article: { label: string; path: string; text: TextBrief; snippet: Segment[] } | null;
};

type Both = { ar: string; fr: string };

/** As you type (P8 of the polish review): citations first, then six at most — the topics and guides the words name,
 *  texts by their everyday name, the word of the law they open. */
export type SuggestResponse = {
  query: string;
  citations: Resolved[];
  topics: { slug: string; name: Both; path: string }[];
  guides: { slug: string; title: Both; path: string; lead?: Both; topic?: string }[];
  texts: TextBrief[];
  words: { slug: string; term: Both; path: string }[];
  repaired: string | null;
  /** What the library's reader finds beyond these (W3): a text by its day, a short form, a finance law's year. */
  finds?: { path: string; name: { ar: string; fr: string | null }; type: string; number: string }[];
};

export type SearchParams = { q: string; type: string; year: string; repealed: boolean; page: number; lang?: string };

export const searchApi = {
  search: (p: SearchParams) => {
    const qs = new URLSearchParams({ q: p.q, page: String(p.page) });
    if (p.type) qs.set('type', p.type);
    if (p.year) {
      qs.set('from', p.year);
      qs.set('to', p.year);
    }
    if (p.repealed) qs.set('repealed', '1');
    // A French page is answered with each article's official French where the site holds it (N16).
    if (p.lang === 'fr') qs.set('lang', 'fr');
    return api<SearchResponse>(`/search/?${qs}`);
  },
  suggest: (q: string) => api<SuggestResponse>(`/search/suggest/?q=${encodeURIComponent(q)}`),
  resolve: (citations: unknown[], since: string | null) =>
    api<{ results: Resolved[] }>('/search/resolve/', { method: 'POST', json: { citations, since } }),
};

/** A question's first page asked at the tap (HM7 of the hard-moment review): on 3G the search page's code took
 *  2.7 s to come, and only then did the question leave. The page finds the answer on the way, under the same key. */
export function askEarly(client: QueryClient, q: string, lang: string) {
  const p: SearchParams = { q, type: '', year: '', repealed: false, page: 1, lang: lang === 'fr' ? 'fr' : 'ar' };
  void client.prefetchQuery({ queryKey: ['search', p], queryFn: () => searchApi.search(p) });
}

export const useSearchResults = (p: SearchParams) =>
  useQuery({
    queryKey: ['search', p],
    queryFn: () => searchApi.search(p),
    enabled: p.q.trim().length > 0,
    // The answer the box asked for with the tap is this one (HM7): not asked twice when the page mounts.
    staleTime: 30_000,
    placeholderData: keepPreviousData,
  });

/** The value once it has stopped changing for `ms`. */
export function useSettled<T>(value: T, ms = 180): T {
  const [settled, setSettled] = useState(value);
  useEffect(() => {
    const id = window.setTimeout(() => setSettled(value), ms);
    return () => window.clearTimeout(id);
  }, [value, ms]);
  return settled;
}

export const useSuggest = (q: string) =>
  useQuery({
    queryKey: ['suggest', q],
    queryFn: () => searchApi.suggest(q),
    enabled: q.trim().length > 1,
    staleTime: 60_000,
    placeholderData: keepPreviousData,
  });

/** Text kinds as the filter chips group them. */
export const TYPE_GROUPS: { key: string; types: string }[] = [
  { key: 'laws', types: 'law,organic_law' },
  { key: 'dahirs', types: 'dahir' },
  { key: 'decrees', types: 'decree,decree_law' },
  { key: 'orders', types: 'order' },
  { key: 'decisions', types: 'decision' },
];

/** A title cut on a word boundary: some BO titles run on for a paragraph. */
export function shortTitle(title: string, max = 160): string {
  if (title.length <= max) return title;
  const cut = title.slice(0, max);
  return `${cut.slice(0, cut.lastIndexOf(' ') > 80 ? cut.lastIndexOf(' ') : max)}…`;
}
