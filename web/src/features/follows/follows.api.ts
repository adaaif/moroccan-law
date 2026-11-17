import { useQuery } from '@tanstack/react-query';
import { api } from '@/shared/services/api';

/** A change to what one follows, as the links pipeline read it; or, for a topic, a new text of it. */
export type NewsItem = {
  key: string;
  on: string;
} & ({
  kind: 'changed';
  by: { kind: string; number: string; path: string | null; title: string };
  issue: { number: number | null; bis: boolean; page: number | null; path: string | null };
  articles: string[];
  verbs: string[];
  settled: boolean;
  effective_on: string | null;
} | {
  kind: 'new_text';
  text: { path: string; title: string; type: string; date: string; issue: string };
} | {
  /** A dated line of a topic's reform record (F12 of the family plan), with its official page when it has one (a
   *  date the law itself sets has none; a Bulletin issue may be named with no address). */
  kind: 'reform';
  text: { ar: string; fr: string };
  source?: { name: { ar: string; fr: string }; url?: string } | null;
});

export type News = {
  path: string;
  kind: 'text' | 'article' | 'topic' | 'reform' | 'place' | 'where';
  name: { ar: string; fr: string };
  article?: string;
  items: NewsItem[];
  total: number;
};

export const fetchNews = (paths: string[]) =>
  api<{ news: News[] }>(`/follows/news/?${paths.map((p) => `path=${encodeURIComponent(p)}`).join('&')}`);

export const useNews = (paths: string[]) =>
  useQuery({ queryKey: ['follows', 'news', paths], queryFn: () => fetchNews(paths), enabled: paths.length > 0, staleTime: 3_600_000 });

export const useAccountFollows = (enabled: boolean) =>
  useQuery({ queryKey: ['follows', 'mine'], queryFn: () => api<{ following: (Omit<News, 'items' | 'total'> & { since: string })[] }>('/follows/'),
             enabled });

/** An account follows too, for a letter when it changes. */
export const accountFollow = (path: string, on: boolean) =>
  api<unknown>('/follows/', { method: on ? 'POST' : 'DELETE', json: { path } });
