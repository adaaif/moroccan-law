import { useQueryClient, type QueryClient } from '@tanstack/react-query';
import { useCallback, useRef, useState } from 'react';
import { topicQuery } from './topics.api';

/** How long a tapped door waits for its page before opening anyway, on a skeleton. */
const WAIT_MS = 1500;

/** What a topic's page needs to be drawn whole: its code, its answer and, with a folder, the folder's code. A tap opened
 *  the router's transition while these came one after the other, and the reader saw nothing happen, then the page all
 *  at once; asked for as the finger lands (or the pointer rests), they come together. Asking twice costs nothing: the
 *  modules and the answer are kept. */
export function readyTopic(client: QueryClient, slug: string): Promise<unknown> {
  return Promise.all([
    import('./hub'),
    client.fetchQuery(topicQuery(slug)).then((d) => (d.module ? import('@/topics/kit/HubExtras') : null)),
  ]).catch(() => null); // the page says what went wrong
}

/** A topic's door or card as a way in: `warm` on the first sign of intent, `open` on the tap, which marks the door
 *  `pending` at once (the reader sees their tap taken) and opens the page when it is ready, or after WAIT_MS. */
export function useOpenTopic() {
  const client = useQueryClient();
  const [pending, setPending] = useState<string | null>(null);
  const opening = useRef<string | null>(null);
  const warm = useCallback((slug: string) => { void readyTopic(client, slug); }, [client]);
  const open = useCallback((slug: string, then: () => void) => {
    if (opening.current) return;
    opening.current = slug;
    setPending(slug);
    const wait = new Promise((r) => window.setTimeout(r, WAIT_MS));
    void Promise.race([readyTopic(client, slug), wait]).then(() => {
      // The door stays pending: the page it opens takes its place.
      opening.current = null;
      then();
    });
  }, [client]);
  return { pending, warm, open };
}
