import { useInfiniteQuery, useQuery } from '@tanstack/react-query';
import { api } from '@/shared/services/api';

/** A place as a list shows it (apps/places): a state, a gone state, or a Moroccan region, province, city or commune. */
export type PlaceCard = {
  slug: string;
  kind: 'country' | 'gone' | 'region' | 'province' | 'city' | 'commune';
  ar: string;
  fr: string;
  texts: number;
  path: string;
  lat?: number;
  lon?: number;
  population?: number;
  parent?: string;
  successor?: string;
  town?: string;
};

export type YearTotal = { year: number; texts: number; foreign: number };

export type PlaceListing = {
  countries: PlaceCard[];
  regions: PlaceCard[];
  provinces: PlaceCard[];
  cities: PlaceCard[];
  communes: number;
  years: YearTotal[];
};

export type Stamp = { issue: string; edition: string; page: number | null; to: string | null };

export type PlaceProfile = {
  place: PlaceCard & {
    en: string;
    code: string;
    foreigners: number | null;
    old: string[];
    spellings: { form: string; n: number; from: number; to: number }[];
    first: { date: string; path: string; form: string; title: string; stamp: Stamp } | null;
  };
  /** Texts as printed that name it, and all the texts as printed, each year since 1913. */
  years: { year: number; texts: number; total: number }[];
  kinds: Record<string, number>;
  types: Record<string, number>;
  near: PlaceCard[];
};

export type MentionRow = {
  path: string;
  text: string;
  label: string;
  title: string;
  name: { ar: string; fr: string | null };
  date: string;
  kind: string;
  type: string;
  in_title: boolean;
  stamp: Stamp;
  snippet: { before: string; hit: string; after: string } | null;
};

export type MentionPage = { place: { slug: string; ar: string; fr: string }; rows: MentionRow[]; next: string | null };

export type Filters = { from?: number; to?: number; kind?: string; type?: string; title?: boolean; with?: string };

export const usePlaces = () => useQuery({ queryKey: ['places'], queryFn: () => api<PlaceListing>('/places/'), staleTime: 3_600_000 });

export const useTyped = (q: string) => useQuery({
  queryKey: ['places', 'typed', q],
  queryFn: () => api<{ query: string; places: PlaceCard[] }>(`/places/?q=${encodeURIComponent(q)}`),
  enabled: q.trim().length >= 2,
  staleTime: 600_000,
});

export const usePlace = (slug: string) => useQuery({
  queryKey: ['places', slug],
  queryFn: () => api<PlaceProfile>(`/places/${slug}/`),
  staleTime: 3_600_000,
});

export function filterQuery(f: Filters): string {
  const p = new URLSearchParams();
  if (f.from) p.set('from', String(f.from));
  if (f.to) p.set('to', String(f.to));
  if (f.kind) p.set('kind', f.kind);
  if (f.type) p.set('type', f.type);
  if (f.title) p.set('title', '1');
  if (f.with) p.set('with', f.with);
  return p.toString();
}

export function useMentions(slug: string, f: Filters) {
  const q = filterQuery(f);
  return useInfiniteQuery({
    queryKey: ['places', slug, 'mentions', q],
    queryFn: ({ pageParam }) => api<MentionPage>(`/places/${slug}/mentions/?${q}${pageParam ? `${q ? '&' : ''}after=${encodeURIComponent(pageParam)}` : ''}`),
    initialPageParam: '',
    getNextPageParam: (last) => last.next ?? undefined,
    staleTime: 600_000,
  });
}
