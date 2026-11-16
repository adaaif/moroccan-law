import { api } from '@/shared/services/api';
import { keptKey } from '../kit/api';

/** What health keeps on the phone once its page has been opened (the health review, S10): the emergency journey
 *  (the band's acts, the SAMU's number and its page) and the code that draws it, so it opens without a network at a
 *  hospital's door. */
export async function keep(): Promise<void> {
  await Promise.all([import('../kit/TopicArea'), import('../kit/JourneyPage')]);
  const page = await api<unknown>('/topics/health/journeys/emergency/').catch(() => null);
  if (page) try { localStorage.setItem(keptKey('health', 'journeys', 'emergency'), JSON.stringify(page)); } catch { /* private window */ }
}
