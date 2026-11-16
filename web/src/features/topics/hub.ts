// A topic's page, as the app loads it. A topic's doors are the page's first screen, so their code starts with the page's
// own (HM11 of the hard-moment review: they came a moment after it and pushed the page down a whole screen, CLS
// 0.95), and a drawn topic waits for it before the app mounts over its words (landingCode in app/landing.ts).
export { default } from './TopicPage';

export const hubExtras = () => import('@/topics/kit/HubExtras');
void hubExtras();
