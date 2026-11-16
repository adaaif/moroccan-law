import { useAccess } from './access.api';

/** The requests waiting for a superuser's answer, from GET /api/access/'s `desk` (null for everyone else): the
 *  header's menu and «أنا» read it from the answer the data's pages already share, with no second request. 0 when none
 *  waits or the account may not open the desk. */
export function useDeskWaiting(desk: boolean | undefined): number {
  const body = useAccess().data as { desk?: { waiting: number } | null } | undefined;
  return desk ? (body?.desk?.waiting ?? 0) : 0;
}
