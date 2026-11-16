import { useInfiniteQuery, useQuery, useQueryClient } from '@tanstack/react-query';
import { markStaff } from '@/shared/analytics/device';
import { api, ApiError } from '@/shared/services/api';
import { useSession } from '@/shared/stores/session';

/** A post is a question or a post (C4 of 29 Oct 2026); what is written under it is a comment. The other kinds are
 *  the article threads' of before, kept for their rows. */
export type Kind = 'question' | 'post' | 'comment' | 'explanation' | 'experience' | 'source' | 'remark';
export const POST_KINDS = ['question', 'post'] as const;
export type Sort = 'active' | 'new' | 'top' | 'open';
export const SORTS: Sort[] = ['active', 'new', 'top', 'open'];
/** «الأنفع» over the last week, month (its first), year, or since the start (31 Oct 2026). */
export type Period = 'week' | 'month' | 'year' | 'all';
export const PERIODS: Period[] = ['week', 'month', 'year', 'all'];
export type Rule = 'privacy' | 'respect' | 'soliciting' | 'lawful' | 'decent' | 'on_topic' | 'honest';
export const RULES: Rule[] = ['privacy', 'respect', 'soliciting', 'lawful', 'decent', 'on_topic', 'honest'];
export type Reason = 'exposing' | 'abuse' | 'soliciting' | 'fraud' | 'sexual' | 'off_topic';
export const REASONS: Reason[] = ['exposing', 'abuse', 'soliciting', 'fraud', 'sexual', 'off_topic'];

export type Voice = { id: string; src: string; expires_at: string; duration_ms: number; peaks: number[] };
export type Picture = { id: string; full: string; thumb: string; width: number; height: number };
/** A person beside their words, with their karma: how much people found what they wrote useful. */
export type Author = { username: string; name: string; form: '' | 'm' | 'f'; karma: number } | { deleted: true };
export type LinkSpan = { start: number; end: number; path: string };

export type Contribution = {
  id: number;
  parent: number | null;
  created_at: string;
  reply_count: number;
  /** On a post's page: how many comments answer it (the rest behind its door, `moreReplies`). */
  answers?: number;
  marker?: 'removed' | 'deleted';
  rule?: Rule | null;
  kind: Kind;
  /** A post's title; a comment has none. */
  title: string;
  body: string;
  links: LinkSpan[];
  quote: string;
  /** The article a post started from. */
  about: string;
  anonymous: boolean;
  author: Author | null;
  mine: boolean;
  edited_at: string | null;
  held: boolean;
  useful: number;
  voted: boolean;
  accepted: boolean;
  outdated: boolean;
  version_on: string | null;
  voice: Voice | null;
  pictures: Picture[];
  replies?: Contribution[];
  /** The answer this one follows (W7). */
  reply_to?: { id: number; name: string | null; anonymous: boolean } | null;
  duplicate_of?: number | null;
  /** The author's and a reviewer's: why it waits, a reviewer's note, hidden after reports. */
  held_reasons?: string[];
  review_note?: string;
  hidden?: boolean;
  /** A reviewer's: the rule its hold points to (M2). */
  suggested?: Rule | null;
  /** In a list: the post's own address, its topic's, its last sign of life, the articles it cites. */
  path?: string;
  place?: string;
  active_at?: string;
  cites?: Cited[];
  /** A question whose asker marked an answer «أفادني». */
  solved?: boolean;
};

/** An article a post cites, by name, and whether it changed since (D14). */
export type Cited = { path: string; label: Label; changed: boolean };

/** May this person write; and, the first time, the agreement that a model reads a post before it is published. */
export type Writing = { can: boolean; why: string | null; voice: boolean; pictures: boolean; consent?: boolean;
                        email_hint?: string; review_hours?: number | null };

/** A topic's place: /talk/family, and «general» for a law no topic holds. */
export type Moderator = { username: string; name: string; karma: number };
export type Place = { path: string; slug: string; name: { ar: string; fr: string }; count: number; open_questions: number;
                      locked: boolean; following: boolean; moderators: Moderator[] };

export type Article = {
  article: { label: string; number: string; body: string; eid: string; path: string; page: number | null;
             document_id: number | null; page_index: number | null; heading_path: string[]; citation: string;
             marks: never[] };
  text: { path: string; title: string; type: string; number_as_printed: string;
          issue: { key: string; number: number; suffix: string; date: string } | null };
  version: { valid_from: string; consolidation: string };
};

/** An answer that says the reader is staff: this device is a team's, and the site's measures never count it
 *  (shared/analytics/device.ts). The account's own answer (/auth/me/) does not say it; these do. */
export function staffSeen<T>(staff: boolean | undefined, answer: T): T {
  if (staff) markStaff();
  return answer;
}

export type Feed = {
  /** A topic's feed: its place; every topic's or what one follows (30 Oct 2026): none. */
  place: Place | null;
  scope: 'place' | 'all' | 'following';
  sort: Sort;
  period: Period;
  writing: Writing;
  review: { can: boolean; staff: boolean };
  posts: Contribution[];
  next_page: number | null;
};

export function useFeed(place: string, sort: Sort, period: Period = 'month') {
  const signedIn = useSession((s) => s.tokens !== null);
  const span = sort === 'top' ? period : 'month';
  return useInfiniteQuery({
    queryKey: ['discussion', 'feed', place, sort, span, signedIn],
    queryFn: ({ pageParam }) => api<Feed>(`/discussion/feed/?place=${encodeURIComponent(place)}&sort=${sort}${sort === 'top' ? `&period=${span}` : ''}&page=${pageParam}`)
      .then((d) => staffSeen(d.review?.staff, d)),
    initialPageParam: 1,
    getNextPageParam: (last) => last.next_page ?? undefined,
    staleTime: 60_000,
  });
}

export type PostPage = {
  place: Place;
  /** Its `replies` are a page of its first-level comments, each followed by its first replies (30 Oct 2026). */
  post: Contribution;
  about: Article | null;
  following: boolean;
  writing: Writing;
  review: { can: boolean; staff: boolean };
  conversations: number;
  /** How many people wrote its comments (30 Oct 2026). */
  people?: number;
  next_page: number | null;
};
export type CommentSort = 'best' | 'new' | 'old';
/** A door's page: the replies that answer one comment, oldest first, each saying how many answer it. */
export type DoorPage = { replies: Contribution[]; answers: number; next_page: number | null };

/** The next replies behind a comment's door (30 Oct 2026, a threaded forum's tree: one level per tap). */
export const moreReplies = (post: number, to: number, page: number) =>
  api<DoorPage>(`/discussion/posts/${post}/replies/?to=${to}&page=${page}`);

/** Where a link to one comment lands: the line of its conversation down to it, and its first replies. Under the post's
 *  key, so that a change reads it again. */
export function useAround(post: number, to: number | null) {
  const signedIn = useSession((s) => s.tokens !== null);
  return useQuery({
    queryKey: ['discussion', 'post', post, 'around', to, signedIn],
    queryFn: () => api<{ replies: Contribution[]; first: number }>(`/discussion/posts/${post}/replies/?around=${to}`),
    enabled: to !== null,
    retry: (n, e) => !(e instanceof ApiError) && n < 2,
    staleTime: 60_000,
  });
}

/** A post and its comments, a page of first-level comments at a time in the reader's order, each with its first
 *  replies (the load test of 30 Oct 2026: a post's tens of thousands of comments came at once); the sort asks the server again. */
export function usePost(id: number, sort: CommentSort) {
  const signedIn = useSession((s) => s.tokens !== null);
  return useInfiniteQuery({
    queryKey: ['discussion', 'post', id, signedIn, sort],
    queryFn: ({ pageParam }) => api<PostPage>(`/discussion/posts/${id}/?sort=${sort}&page=${pageParam}`).then((d) => staffSeen(d.review?.staff, d)),
    initialPageParam: 1,
    getNextPageParam: (last) => last.next_page ?? undefined,
    // The page stays while the reader changes the comments' order; another post never stands in for this one (it did:
    // a link from one post to another showed the first until the second came).
    placeholderData: (previous, query) => (query?.queryKey[2] === id ? previous : undefined),
    retry: (n, e) => !(e instanceof ApiError) && n < 2,
    staleTime: 60_000,
  });
}

export type CitedPage = Article & {
  posts: (Contribution & { label: Label })[];
  total: number;
  next_page: number | null;
  places: { path: string; slug: string; name: { ar: string; fr: string } }[];
  writing: Writing;
};

export function useCited(path: string) {
  const signedIn = useSession((s) => s.tokens !== null);
  return useInfiniteQuery({
    queryKey: ['discussion', 'cited', path, signedIn],
    queryFn: ({ pageParam }) => api<CitedPage>(`/discussion/cited/?path=${encodeURIComponent(path)}&page=${pageParam}`),
    initialPageParam: 1,
    getNextPageParam: (last) => last.next_page ?? undefined,
    staleTime: 60_000,
  });
}

export type PlaceSummary = { path: string; slug: string; name: { ar: string; fr: string };
                             /** Its door's name, as on the home. */ short?: { ar: string; fr: string };
                             count: number; open_questions: number; last_at: string | null; posts: Contribution[] };

export function usePlaces() {
  return useQuery({ queryKey: ['discussion', 'places'], queryFn: () => api<{ places: PlaceSummary[] }>('/discussion/places/'),
                    staleTime: 60_000 });
}

/** After a change, the topic's lists, the post and the article pages are read again. */
export function useRefreshTalk() {
  const client = useQueryClient();
  return () => {
    for (const key of ['feed', 'post', 'cited', 'places', 'questions', 'counts']) {
      void client.invalidateQueries({ queryKey: ['discussion', key] });
    }
  };
}

export type Counts = { open: boolean; articles: Record<string, { count: number }> };

export function useCounts(textPath: string) {
  return useQuery({
    queryKey: ['discussion', 'counts', textPath],
    queryFn: () => api<Counts>(`/discussion/counts/?text=${encodeURIComponent(textPath)}`),
    staleTime: 60_000,
  });
}

/** An address said in words: an article with its text's name (P6 of the polish review) and number; or a topic's
 *  place by its name, with a post's title. */
export type Label = { article: string; text: string; name?: { ar: string; fr: string | null } | null; number?: string;
                      place?: string; title?: string };

export type Labelled = Contribution & { path: string; label: Label; post_title?: string };

export function useQuestions(place: string) {
  return useInfiniteQuery({
    queryKey: ['discussion', 'questions', place],
    queryFn: ({ pageParam }) => api<{ questions: Labelled[]; next_page: number | null; places: string[] }>(
      `/discussion/questions/?place=${encodeURIComponent(place)}&page=${pageParam}`),
    initialPageParam: 1,
    getNextPageParam: (last) => last.next_page ?? undefined,
  });
}

/** Questions someone answered, the latest first, each with its answer (R12 of the for-everyone review). */
export function useAnswered() {
  return useInfiniteQuery({
    queryKey: ['discussion', 'answered'],
    queryFn: ({ pageParam }) => api<{ questions: (Labelled & { answer: Contribution | null })[]; next_page: number | null }>(
      `/discussion/answered/?page=${pageParam}`),
    initialPageParam: 1,
    getNextPageParam: (last) => last.next_page ?? undefined,
  });
}

/** The header's poll: what is new, what waits for a moderator, the reader's karma (30 Oct 2026). */
export type Unseen = { unseen: number; review: number; reviewer: boolean; karma: number };

export type PersonPlace = { path: string; slug: string; name: { ar: string; fr: string }; count: number };
export type Person = {
  person: { username: string; name: string; form: '' | 'm' | 'f'; joined: string; karma: number; contributions: number;
            posts: number; answers: number; last_at: string | null; places: PersonPlace[];
            accepted: number; moderates: { path: string; name: { ar: string; fr: string } }[] };
  contributions: Labelled[];
  total: number;
  next_page: number | null;
};
export type PersonKind = '' | 'posts' | 'answers';

/** A person's page, a page at a time: everything they wrote under their name, or their posts, or their answers. */
export function usePerson(username: string, kind: PersonKind = '', enabled = true) {
  return useInfiniteQuery({
    queryKey: ['discussion', 'person', username, kind],
    queryFn: ({ pageParam }) => api<Person>(
      `/discussion/people/${encodeURIComponent(username)}/?page=${pageParam}${kind ? `&kind=${kind}` : ''}`),
    initialPageParam: 1,
    getNextPageParam: (last) => last.next_page ?? undefined,
    retry: (n, e) => !(e instanceof ApiError) && n < 2,
    enabled: enabled && Boolean(username),
  });
}

export type Notice = { id: number; kind: string; path: string; contribution: number | null; detail: string;
                       created_at: string; seen: boolean; count: number; who: string | null };
export type Appeal = { created_at: string; decided: boolean; outcome: 'lifted' | 'kept' | null };
export type Mine = {
  standing: Writing & { karma: number; reviewer: boolean; staff: boolean };
  notices: Notice[];
  unseen: number;
  contributions: (Contribution & { path: string; label: Label; post_title?: string; removed: boolean;
                                   rule: Rule | null; appeal: Appeal | null })[];
  reports: { reason: Reason; status: 'open' | 'acted' | 'reviewed'; created_at: string; path: string }[];
  pause: { id: number; until: string | null; rule: Rule; appeal: Appeal | null } | null;
  following: { path: string; label: Label }[];
};

export const MINE_KEY = ['discussion', 'mine'] as const;

export function useMine(enabled = true) {
  const signedIn = useSession((s) => s.tokens !== null);
  return useQuery({ queryKey: MINE_KEY, queryFn: () => api<Mine>('/discussion/me/').then((d) => staffSeen(d.standing?.staff, d)),
                   enabled: signedIn && enabled });
}

export type NewContribution = {
  path?: string; kind?: Kind; title?: string; body: string; about?: string; quote?: string; parent?: number;
  anonymous?: boolean; voice?: string; pictures?: string[];
  /** The first post's agreement that a model reads it; `insist` sends a returned post to a moderator as it is. */
  consent?: boolean; insist?: boolean;
};

export const discussionApi = {
  contribute: (body: NewContribution) => api<Contribution>('/discussion/contributions/', { method: 'POST', json: body }),
  edit: (id: number, body: string, title?: string, insist?: boolean) =>
    api<Contribution>(`/discussion/contributions/${id}/`, { method: 'PATCH', json: { body, title, insist } }),
  remove: (id: number) => api<void>(`/discussion/contributions/${id}/`, { method: 'DELETE' }),
  useful: (id: number, on: boolean) =>
    api<{ useful: number; voted: boolean }>(`/discussion/contributions/${id}/useful/`, { method: on ? 'POST' : 'DELETE' }),
  accept: (id: number, on: boolean) =>
    api<{ accepted: boolean }>(`/discussion/contributions/${id}/accept/`, { method: on ? 'POST' : 'DELETE' }),
  report: (id: number, reason: Reason, details: string, moment_ms?: number) =>
    api<{ ok: true }>(`/discussion/contributions/${id}/report/`, { method: 'POST', json: { reason, details, moment_ms } }),
  follow: (path: string, on: boolean) =>
    api<{ following: boolean }>('/discussion/follow/', { method: on ? 'POST' : 'DELETE', json: { path } }),
  voiceLink: (id: string) => api<{ src: string; expires_at: string }>(`/discussion/voices/${id}/`),
  dropVoice: (id: string) => api<void>(`/discussion/voices/${id}/`, { method: 'DELETE' }),
  dropPicture: (id: string) => api<void>(`/discussion/pictures/${id}/`, { method: 'DELETE' }),
  seen: () => api<void>('/discussion/me/notices/seen/', { method: 'POST' }),
  appeal: (body: { contribution?: number; pause?: number; text: string }) =>
    api<{ ok: true }>('/discussion/appeals/', { method: 'POST', json: body }),
  check: (body: string) => api<{ reasons: string[]; spans: [number, number, string][] }>('/discussion/check/',
                                                                                         { method: 'POST', json: { body } }),
  /** The words being typed go in the body: the server's logs write addresses, never bodies (/privacy). */
  similar: (path: string, q: string) => api<{ questions: Similar[] }>('/discussion/similar/',
                                                                     { method: 'POST', json: { path, q } }),
  takedown: (id: number, details: string, contact: string) =>
    api<{ ok: true }>(`/discussion/contributions/${id}/takedown/`, { method: 'POST', json: { details, contact } }),
  unseen: () => api<Unseen>('/discussion/me/unseen/'),
  /** A reviewer's act on one contribution: approve, keep, remove, restore, pause, redact, send_back, check, trust,
   *  untrust, duplicate, reveal. */
  act: (id: number, body: Record<string, unknown>) =>
    api<Record<string, string>>(`/discussion/review/contributions/${id}/`, { method: 'POST', json: body }),
  lock: (path: string, locked: boolean) =>
    api<{ locked: boolean }>('/discussion/review/lock/', { method: 'POST', json: { path, locked } }),
};

export type Similar = { id: number; title: string; body: string; path: string; useful: number; answers: number;
                        accepted: boolean; share: number };

/** Multipart uploads go through fetch with the session's token (the JSON wrapper sends JSON only). */
export async function upload<T>(path: string, form: FormData): Promise<T> {
  const send = () => {
    const access = useSession.getState().tokens?.access;
    return fetch(`/api${path}`, { method: 'POST', body: form, headers: access ? { Authorization: `Bearer ${access}` } : {} });
  };
  let response = await send();
  if (response.status === 401) {
    // Let the JSON wrapper refresh the session once, then try again.
    await api('/auth/me/').catch(() => undefined);
    response = await send();
  }
  if (!response.ok) {
    let errors: { field: string; code: string }[] = [];
    try {
      errors = ((await response.json()) as { errors?: typeof errors }).errors ?? [];
    } catch {
      // No JSON body.
    }
    throw new ApiError(response.status, errors);
  }
  return (await response.json()) as T;
}
