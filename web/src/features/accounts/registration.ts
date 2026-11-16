import { useQuery } from '@tanstack/react-query';
import { api } from '@/shared/services/api';
import { useSession } from '@/shared/stores/session';

/** Whether sign-up is open (closed on 27 Oct 2026: REGISTRATION_OPEN), and writing in the discussion
 *  (DISCUSSION_OPEN): the shell asks once a visit, so it offers no door that leads to a refusal (N17 of
 *  the read-and-trusted review). */
export function useRegistration() {
  return useQuery({ queryKey: ['registration'], queryFn: () => api<{ open: boolean; discussion: boolean; talk_alive?: boolean; mcp_open?: boolean; google?: string }>('/auth/register/'),
                    staleTime: 30 * 60_000 });
}

/** True once the server says sign-up is open; false while it is closed or not known yet, so no way in is offered. */
export function useRegistrationOpen(): boolean {
  return useRegistration().data?.open === true;
}

/** True once the server says people can write in the discussion; false while it is closed or not known yet. */
export function useDiscussionOpen(): boolean {
  return useRegistration().data?.discussion === true;
}

/** True when assistants read the site without an account (MCP_AUTH 'open', since 3 Nov 2026). */
export function useMcpOpen(): boolean {
  return useRegistration().data?.mcp_open === true;
}

/** Whether this reader can write in the discussion: it is open and they have an account or can make one (HM44 of
 *  the hard-moment review: with sign-up closed the bar's «النقاش» led every visitor to an empty /talk they could
 *  not write in). The shell's last place is the conversation then, else what the reader kept. */
export function useCanTalk(): boolean {
  const signedIn = useSession((s) => s.tokens !== null);
  const r = useRegistration().data;
  return r?.discussion === true && (r.open || signedIn);
}

/** Whether a phone's bar gives the conversation its fifth place: this reader can write in it and it holds its first
 *  hundred posts (C2 of the readers review, 10 Nov 2026: «النقاش» held a place and no post in any topic, while
 *  «محفوظاتي», which works with no connection, had left the bar). Until then the conversation is reached from the home,
 *  a law, an article and the footer, and a desk's header keeps it. */
export function useTalkInBar(): boolean {
  const alive = useRegistration().data?.talk_alive === true;
  return useCanTalk() && alive;
}
