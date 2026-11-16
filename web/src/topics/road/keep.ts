import { api } from '@/shared/services/api';
import type { Journey, Module } from '../kit/api';

/** What the accident page needs without a network, kept on the phone once the road's page has been opened (A17 of
 *  the road-signposted review): the journey's steps, the numbers with their sources, and the code of the pages that draw
 *  them (the service worker keeps every built file it fetched). */
export const KEPT = 'law.road.accident';
export const KEPT_NUMBERS = 'law.road.numbers';

export async function keep(module: Module): Promise<void> {
  try { localStorage.setItem(KEPT_NUMBERS, JSON.stringify(module.urgent?.numbers ?? [])); } catch { /* private window */ }
  await Promise.all([import('./NowPage'), import('../kit/TopicArea')]);
  const journey = await api<Journey>('/topics/road/journeys/accident/').catch(() => null);
  if (journey) try { localStorage.setItem(KEPT, JSON.stringify(journey)); } catch { /* private window */ }
}

export function keptNumbers(): NonNullable<Module['urgent']>['numbers'] {
  try { return JSON.parse(localStorage.getItem(KEPT_NUMBERS) ?? '[]'); } catch { return []; }
}
