/** Where each of the old situations leads now (HM4 of the hard-moment review, 7 Nov 2026): the topic page that
 *  answers it, written and laid out since. The October drafts said the Labour Code and the Family Code were «not yet
 *  here», drew a crash in the papers topic's teal and never reached the journeys. /situations/<slug> leads here too. */
export const SITUATION_TO: Record<string, { topic: string; path: string }> = {
  'road-accident': { topic: 'road', path: '/topics/road/journeys/accident' },
  'driving-licence': { topic: 'road', path: '/topics/road/pages/licence' },
  renting: { topic: 'housing', path: '/topics/housing' },
  divorce: { topic: 'family', path: '/topics/family/pages/ways' },
  dismissal: { topic: 'work', path: '/topics/work/journeys/dismissed' },
  birth: { topic: 'family', path: '/topics/family/journeys/birth' },
  consumer: { topic: 'consumer', path: '/topics/consumer/journeys/defect' },
  'co-ownership': { topic: 'housing', path: '/topics/housing/journeys/syndic' },
  building: { topic: 'land', path: '/topics/land/tools/permit' },
  expropriation: { topic: 'land', path: '/topics/land/journeys/expropriation' },
  copyright: { topic: 'digital', path: '/topics/digital/tools/copyright' },
  property: { topic: 'land', path: '/topics/land/tools/before' },
};

export const situationPath = (slug: string) => SITUATION_TO[slug]?.path ?? `/situations/${slug}`;
export const situationTopic = (slug: string, topic?: string | null) => SITUATION_TO[slug]?.topic || topic || 'papers';
