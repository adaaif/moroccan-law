import { useQuery } from '@tanstack/react-query';
import type { ShelfItem, Situation } from '@/features/corpus/corpus.api';
import { api } from '@/shared/services/api';
import type { Module } from '@/topics/kit/api';

export type Named = { ar: string; fr: string };
/** A life topic (R2 of the for-everyone review): how people name a part of life a law governs. */
export type TopicSummary = { slug: string; name: Named; short?: Named; lead: Named; counts: { situations: number; codes: number } };
/** A rule-making text of the last half year whose title holds one of the topic's words. */
export type RecentText = { path: string; title: string; type: string; number_as_printed: string; date: string; issue: string;
                           status: string };
/** An article's place, as the discussion names it: its label and its text by name. */
/** Its conversation (P16 of the polish review): the most discussed articles of its texts, two questions waiting. */
/** A topic's conversation on its page (29 Oct 2026): its place's liveliest posts, its questions waiting, its moderators. */
export type TalkPost = { id: number; kind: string; title: string; body: string; path: string; reply_count: number };
export type TopicTalk = {
  place: string;
  posts: TalkPost[];
  questions: TalkPost[];
  moderators: { username: string; name: string; karma: number }[];
};
export type TopicDetail = TopicSummary & {
  words: { slug: string; term: Named }[];
  situations: Situation[];
  codes: ShelfItem[];
  talk?: TopicTalk;
  recent: RecentText[];
  /** What the topic's own folder adds (F16 of the family plan): doors, tools, the reform's line; null without one. */
  module?: Module | null;
};

export const useTopics = () =>
  useQuery({ queryKey: ['topics'], queryFn: () => api<TopicSummary[]>('/topics/'), staleTime: 3_600_000 });
/** One topic's answer, as its page and a door's opening (open.ts) both ask for it. */
export const topicQuery = (slug: string) =>
  ({ queryKey: ['topic', slug], queryFn: () => api<TopicDetail>(`/topics/${slug}/`), staleTime: 600_000 });
export const useTopic = (slug: string) => useQuery({ ...topicQuery(slug), enabled: Boolean(slug) });
