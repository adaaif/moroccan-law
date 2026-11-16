import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '@/shared/services/api';
import { useSession } from '@/shared/stores/session';
import type { AccessBody, Keys, Manifest, NewKey } from './access';

/** An account's request and access (/api/access/), a request to change it, and its keys (/api/access/keys/), the
 *  edition's manifest and a ticket to one of its files (/api/open/). Every answer of /api/access/ is the body GET gives,
 *  after its act. */
export const accessApi = {
  get: () => api<AccessBody>('/access/'),
  send: (json: object) => api<AccessBody>('/access/request/', { method: 'POST', json }),
  answer: (answer: string) => api<AccessBody>('/access/request/answer/', { method: 'POST', json: { answer } }),
  /** A holder's request to change the access it holds: it waits for the staff like any request. */
  change: (json: object) => api<AccessBody>('/access/change/', { method: 'POST', json }),
  end: () => api<AccessBody>('/access/end/', { method: 'POST' }),
  keys: () => api<Keys>('/access/keys/'),
  makeKey: (name: string) => api<NewKey>('/access/keys/', { method: 'POST', json: { name } }),
  dropKey: (id: number) => api<void>(`/access/keys/${id}/`, { method: 'DELETE' }),
  manifest: () => api<Manifest>('/open/'),
  /** A link to one file of the newest edition, good for ten minutes, for the browser to follow. */
  ticket: (file: string) => api<{ url: string }>('/open/ticket/', { method: 'POST', json: { file, edition: 'latest' } }),
};

/** The account's request and access, or a visitor's position: one query whichever part asks. */
export function useAccess() {
  const signedIn = useSession((s) => s.tokens !== null);
  return useQuery({ queryKey: ['access', signedIn], queryFn: accessApi.get, staleTime: 60_000 });
}

/** Put the body an act answered where the parts read it. */
export function useKeepAccess() {
  const client = useQueryClient();
  return (body: AccessBody) => client.setQueryData(['access', true], body);
}

/** The newest edition's manifest; 404 until the first edition is written, 403 while the data is closed. */
export const useManifest = (enabled = true) =>
  useQuery({ queryKey: ['openManifest'], queryFn: accessApi.manifest, staleTime: 3_600_000, retry: false, enabled });
