import { longDate } from '@/features/corpus/format';
import { standing, type Standing } from '@/features/opendata/access';
import { useAccess } from '@/features/opendata/access.api';
import { dayIn } from '@/shared/services/today';
import { useT } from '../strings';

/** Where the account's request for the data stands, in one line: «وصولي» in the header's menu and on «أنا» (/account),
 *  both leading to /data/access. Null for an account that never asked. Asked of GET /api/access/, the query the data's
 *  pages share. */
export function useAccessLine(): { standing: Standing; line: string } | null {
  const { t, i18n } = useT();
  const body = useAccess().data;
  const s = body ? standing(body) : 'none';
  if (!body || s === 'none') return null;
  const { request: r, access: a } = body;
  const on = s === 'waiting' ? r?.created_at : s === 'declined' ? r?.ask_again_on : s === 'live' ? a?.ends_on : null;
  const date = on ? longDate(on.length > 10 ? dayIn(new Date(on)) : on, i18n.language) : '';
  return { standing: s, line: t(`me2.accessStates.${s}`, { date }) };
}
