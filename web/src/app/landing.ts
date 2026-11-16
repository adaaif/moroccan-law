import { homeCode } from '@/features/corpus/homeSections';

// The code of the pages a prerendered landing page can be, loaded apart: the routes (App.tsx) load them with these, and
// a landing page waits for its own before the app mounts over its words.
export const issuePage = () => import('@/features/corpus/IssuePage');
export const topicsPage = () => import('@/features/topics/TopicsPage');
export const topicPage = () => import('@/features/topics/hub');
// A topic's journeys, papers, pages, reform and tools (F16 of the family plan), and each topic's own code with them.
export const topicArea = () => import('@/topics/kit/TopicArea');
export const blogIndex = () => import('@/features/blog/BlogIndex');
export const blogPost = () => import('@/features/blog/BlogPost');

/** A prerendered landing page's code (HM2 of the hard-moment review), awaited before the app mounts over its
 *  words (main.tsx), as a law's answer is: the page goes from its words to the app with no skeleton between. */
export function landingCode(path: string): Promise<unknown> {
  const p = path.replace(/\/$/, '');
  return p === '/topics' ? topicsPage() : /^\/topics\/[^/]+$/.test(p) ? topicPage().then((m) => m.hubExtras()) : p.startsWith('/topics/') ? topicArea()
    : p === '/blog' ? blogIndex() : p.startsWith('/blog/') ? blogPost() : p === '' ? homeCode()
    // A Bulletin issue Django drew with its answer (IX8 of the search-engines review): only an issue's page carries one.
    : p.startsWith('/bo/') ? issuePage() : Promise.resolve();
}
