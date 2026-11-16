import { lazy, Suspense } from 'react';
import { Route, Routes, useLocation, useParams } from 'react-router-dom';
import NotFound from '@/features/corpus/NotFound';
import { Note, Page, PageSkeleton } from '@/shared/components/ui';
import { useTopic } from '@/features/topics/topics.api';
import { OFFLINE, TOOLS, UNDER, underTool } from '../registry';
import { useKitT } from './api';
import ChecklistPage from './ChecklistPage';
import InfoPage from './InfoPage';
import JourneyPage from './JourneyPage';
import ChangesPage from './ChangesPage';
import ReformPage from './ReformPage';

// The reviewer's desk (R1 of the road tools review): staff only, loaded only on its page.
const ReviewDesk = lazy(() => import('./ReviewDesk'));

/** Everything under /topics/<slug>/: the kit's journeys, papers, pages and reform, and the topic's own tools. */
export default function TopicArea() {
  const { slug = '' } = useParams();
  return (
    <Routes>
      <Route path="journeys/:key" element={<JourneyPage slug={slug} />} />
      <Route path="checklists/:key" element={<ChecklistPage slug={slug} />} />
      <Route path="pages/:key" element={<InfoPage slug={slug} />} />
      <Route path="reform" element={<ReformPage slug={slug} />} />
      <Route path="reform/:key" element={<ReformPage slug={slug} />} />
      <Route path="changes" element={<ChangesPage slug={slug} />} />
      <Route path="tools/:key" element={<Tool slug={slug} />} />
      {/* A tool with addresses of its own under its page (the inheritance calculator's families and readings). */}
      <Route path="tools/:key/*" element={<Tool slug={slug} />} />
      <Route path="review" element={<Suspense fallback={<Page width="reading"><PageSkeleton /></Page>}><ReviewDesk slug={slug} /></Suspense>} />
      <Route path="*" element={<NotFound />} />
    </Routes>
  );
}

/** A tool shows once a person checked it (F17): the hub lists it then. An `open` one shows before; any other only while
 *  developing. Neither says so on its page any more (15 Nov 2026): every tool ends on «كيفاش حسبنا؟» (KitPage), the way
 *  to «عن «قانون»», which says once that no specialist has reviewed the tools yet. */
function Tool({ slug }: { slug: string }) {
  const { key = '' } = useParams();
  const under = underTool(useLocation().pathname, key);
  const { t } = useKitT();
  const topic = useTopic(slug);
  const Component = TOOLS[slug]?.[key];
  if (!Component || (under && !UNDER[slug]?.includes(key))) return <NotFound />;
  if (topic.isLoading) return <Page width="reading"><PageSkeleton /></Page>;
  const door = topic.data?.module?.tools.find((d) => d.key === key);
  // Without a network, a tool that works offline opens from what the phone kept (A17).
  if (!door && topic.isError && OFFLINE[slug]?.includes(key)) {
    return <Suspense fallback={<Page width="reading"><PageSkeleton /></Page>}><Component slug={slug} /></Suspense>;
  }
  // Without a network the topic cannot say whether the tool is shown: that is said, never «waiting for a check» (HM15 of
  // the hard-moment review: offline, the open fine tool claimed it waited for a person's review).
  if (!door) return <Page width="reading"><Note tone="warn"><p className="m-0 text-body">{t(topic.isError ? 'offlineTool' : 'notYet')}</p></Note></Page>;
  return (
    <Suspense fallback={<Page width="reading"><PageSkeleton /></Page>}>
      <Component slug={slug} />
    </Suspense>
  );
}
