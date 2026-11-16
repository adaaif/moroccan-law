// The home's sections whose code loads apart from the page's (HomePage.tsx).
// The law's calendar (what changed, what comes) and the conversation's liveliest posts come after the page (30 Oct 2026).
export const homeCalendar = () => import('./HomeCalendar');
export const homeTalk = () => import('@/features/discussion/HomeTalk');
// Below the hero, the guides' list and the week's issue come a moment later too.
export const situationList = () => import('@/features/situations/SituationList');
// The week's Bulletin, drawn as its front page (30 Oct 2026), with its own code and words.
export const homeWeek = () => import('./HomeWeek');
// «قانون بالأرقام», the library and who makes the site, at the end.
export const homeEnd = () => import('./HomeEnd');
// The topics' doors come a moment after the hero (their drawings and their list), the space they take kept meanwhile.
export const topicRow = () => import('@/features/topics/TopicRow');

/** The home's sections that load apart, awaited before the app mounts over the prerendered home (HM2 of
 *  the hard-moment review): the doors, the week and the rest stay on screen instead of blinking out while their code comes. */
export const homeCode = () => Promise.all([topicRow(), homeWeek(), situationList(), homeCalendar(), homeTalk(), homeEnd()]);
