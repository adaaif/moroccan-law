import { useInfiniteQuery, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '@/shared/services/api';
import type {
  AccessFilter, AccessRow, AccessSheet, DeskEvent, Editions, Letter, ListPage, Overview, RequestFilter, RequestRow,
  RequestSheet, Use,
} from './desk';

/** /api/access/desk/: the desk's reads and acts. Every act answers the sheet it acted on. */
const BASE = '/access/desk/';
const query = (o: Record<string, string>) => {
  const q = new URLSearchParams(Object.entries(o).filter(([, v]) => v)).toString();
  return q ? `?${q}` : '';
};
const post = <T>(path: string, json: object) => api<T>(`${BASE}${path}`, { method: 'POST', json });

export const deskApi = {
  home: () => api<Overview>(BASE),
  requests: (state: RequestFilter, q: string, cursor: string) =>
    api<ListPage<RequestRow, Exclude<RequestFilter, 'all'>>>(`${BASE}requests/${query({ state, q, cursor })}`),
  request: (id: number) => api<RequestSheet>(`${BASE}requests/${id}/`),
  preview: (id: number, json: object) => post<Letter>(`requests/${id}/preview/`, json),
  accept: (id: number, json: object) => post<RequestSheet>(`requests/${id}/accept/`, { ...json, confirm: true }),
  ask: (id: number, line: string) => post<RequestSheet>(`requests/${id}/ask/`, { line }),
  decline: (id: number, reason: string) => post<RequestSheet>(`requests/${id}/decline/`, { reason }),
  accesses: (state: AccessFilter, q: string, cursor: string) =>
    api<ListPage<AccessRow, Exclude<AccessFilter, 'all'>>>(`${BASE}accesses/${query({ state, q, cursor })}`),
  access: (id: number) => api<AccessSheet>(`${BASE}accesses/${id}/`),
  change: (id: number, json: object) => post<AccessSheet>(`accesses/${id}/change/`, { ...json, confirm: true }),
  renew: (id: number, ends_on: string) => post<AccessSheet>(`accesses/${id}/renew/`, { ends_on }),
  end: (id: number, reason: string) => post<AccessSheet>(`accesses/${id}/end/`, { reason, confirm: true }),
  endKey: (id: number) => post<AccessSheet>(`keys/${id}/end/`, {}),
  use: () => api<Use>(`${BASE}use/?days=30`),
  editions: () => api<Editions>(`${BASE}editions/`),
  log: (cursor: string) => api<{ results: DeskEvent[]; next: string | null }>(`${BASE}log/${query({ cursor })}`),
};

/** The desk's answers are never kept by the server; here they stay fresh for half a minute, and a failure is said, not
 *  asked again behind the reader's back. */
const fresh = { staleTime: 30_000, retry: false } as const;

export const useOverview = () => useQuery({ queryKey: ['desk', 'home'], queryFn: deskApi.home, ...fresh });
export const useUse = () => useQuery({ queryKey: ['desk', 'use'], queryFn: deskApi.use, ...fresh });
export const useEditions = () => useQuery({ queryKey: ['desk', 'editions'], queryFn: deskApi.editions, ...fresh });
export const useRequestSheet = (id: number) =>
  useQuery({ queryKey: ['desk', 'request', id], queryFn: () => deskApi.request(id), ...fresh });
export const useAccessSheet = (id: number) =>
  useQuery({ queryKey: ['desk', 'access', id], queryFn: () => deskApi.access(id), ...fresh });

export const useRequests = (state: RequestFilter, q: string, enabled = true) => useInfiniteQuery({
  queryKey: ['desk', 'requests', state, q], enabled, ...fresh,
  queryFn: ({ pageParam }) => deskApi.requests(state, q, pageParam),
  initialPageParam: '', getNextPageParam: (last) => last.next ?? undefined,
});

export const useAccesses = (state: AccessFilter, q: string) => useInfiniteQuery({
  queryKey: ['desk', 'accesses', state, q], ...fresh,
  queryFn: ({ pageParam }) => deskApi.accesses(state, q, pageParam),
  initialPageParam: '', getNextPageParam: (last) => last.next ?? undefined,
});

export const useLog = () => useInfiniteQuery({
  queryKey: ['desk', 'log'], ...fresh,
  queryFn: ({ pageParam }) => deskApi.log(pageParam),
  initialPageParam: '', getNextPageParam: (last) => last.next ?? undefined,
});

/** After an act: its sheet as the server answered it, and every list asked again (the header's count too). */
export function useActed() {
  const client = useQueryClient();
  return (key: ['desk', 'request' | 'access', number], sheet: RequestSheet | AccessSheet) => {
    client.setQueryData(key, sheet);
    void client.invalidateQueries({ queryKey: ['desk'], predicate: (q) => q.queryKey[1] !== key[1] || q.queryKey[2] !== key[2] });
    void client.invalidateQueries({ queryKey: ['access'] });
  };
}
