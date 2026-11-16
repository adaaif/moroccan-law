import { api } from '@/shared/services/api';
import { keptKey } from '../kit/api';

/** What the family keeps on the phone once its page has been opened (G14 of the family-papers review): the
 *  protection page, its numbers and their sources, and the code that draws it (the service worker keeps every built
 *  file it fetched), so it opens without a network. Never a shortcut on the home screen: that would not be discreet. */
export async function keep(): Promise<void> {
  await Promise.all([import('../kit/TopicArea'), import('../kit/InfoPage')]);
  const page = await api<unknown>('/topics/family/pages/protection/').catch(() => null);
  if (page) try { localStorage.setItem(keptKey('family', 'pages', 'protection'), JSON.stringify(page)); } catch { /* private window */ }
}
