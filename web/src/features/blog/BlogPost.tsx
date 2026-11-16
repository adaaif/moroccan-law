import { lazy, Suspense, type ComponentType } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Navigate, useParams } from 'react-router-dom';
import NotFound from '@/features/corpus/NotFound';
import { Page, PageSkeleton } from '@/shared/components/ui';
import { usePageTitle } from '@/shared/services/title';
import { fetchPost, type PostSummary } from './blog.api';
import { BlogLinks } from './BlogLinks';
import './i18n';

/** Each post is drawn by its own code: its pictures are its own. */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const POSTS: Record<string, ComponentType<{ post: any }>> = {
  'from-no-1': lazy(() => import('./seventy/Seventy')),
  'six-constitutions': lazy(() => import('./six/Six')),
  'words-in-the-law': lazy(() => import('./words/Words')),
  'who-writes': lazy(() => import('./who/Who')),
  'december': lazy(() => import('./months/Months')),
  'minimum-wage': lazy(() => import('./wage/Wage')),
  'holidays': lazy(() => import('./holidays/Holidays')),
  'signed-to-published': lazy(() => import('./waits/Waits')),
  'errata': lazy(() => import('./errata/Errata')),
  'agreements': lazy(() => import('./agreements/Agreements')),
  'countries': lazy(() => import('./countries/Countries')),
  'cities': lazy(() => import('./cities/Cities')),
  'clock': lazy(() => import('./clock/Clock')),
  'marquise': lazy(() => import('./marquise/Marquise')),
  'bread-gasoil': lazy(() => import('./staples/Staples')),
  ages: lazy(() => import('./ages/Ages')),
  'article-28': lazy(() => import('./drinks/Drinks')),
  strike: lazy(() => import('./strike/Strike')),
  whatsapp: lazy(() => import('./absent/Absent')),
  'death-penalty': lazy(() => import('./death/Death')),
  parliament: lazy(() => import('./parliament/Parliament')),
  speed: lazy(() => import('./speed/Speed')),
  deadlines: lazy(() => import('./deadlines/Deadlines')),
  expropriation: lazy(() => import('./expropriation/Expropriation')),
  mokri: lazy(() => import('./mokri/Mokri')),
  ministry: lazy(() => import('./ministry/Ministry')),
  emergency: lazy(() => import('./emergency/Emergency')),
};

/** A post that took another's place: its old address leads to it («سبعون سنة» became the Bulletin from No. 1; the places'
 *  two short posts were folded into the long ones, 6 Nov 2026). */
const MOVED: Record<string, string> = { 'seventy-years': 'from-no-1', 'countries-in-brief': 'countries', 'cities-in-brief': 'cities' };

/** /blog/<slug>: a post of «قانون بالأرقام», its meta and figures from /api/blog/<slug>/. */
export default function BlogPost() {
  const { slug = '' } = useParams();
  if (MOVED[slug]) return <Navigate to={`/blog/${MOVED[slug]}`} replace />;
  return <Shown slug={slug} />;
}

function Shown({ slug }: { slug: string }) {
  const { i18n } = useTranslation('blog');
  const Post = POSTS[slug];
  const post = useQuery({ queryKey: ['blog', slug], queryFn: () => fetchPost<PostSummary>(slug), enabled: Boolean(Post), staleTime: 3600_000 });
  usePageTitle([post.data?.title[i18n.language === 'fr' ? 'fr' : 'ar']]);
  if (!Post || post.isError) return <NotFound />;
  return (
    <Page width="wide">
      {post.data ? (
        <>
          <Suspense fallback={<PageSkeleton kind="text" />}><Post post={post.data} /></Suspense>
          <BlogLinks around={slug} />
        </>
      ) : <PageSkeleton kind="text" />}
    </Page>
  );
}
