import { lazy, Suspense } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { Examples } from '@/features/search/Examples';
import { SearchBox } from '@/features/search/SearchBox';
import { useSituations } from './corpus.api';
import { usePageTitle } from '@/shared/services/title';
import { Page, SectionHeader } from '@/shared/components/ui';
import { homeCalendar, homeEnd, homeTalk, homeWeek, situationList, topicRow } from './homeSections';

const HomeCalendar = lazy(homeCalendar);
const HomeTalk = lazy(homeTalk);
const SituationList = lazy(() => situationList().then((m) => ({ default: m.SituationList })));
const HomeWeek = lazy(homeWeek);
const HomeEnd = lazy(homeEnd);
const TopicRow = lazy(() => topicRow().then((m) => ({ default: m.TopicRow })));

/** The home (R1 of the for-everyone review, 19 Oct 2026; its lower half drawn again on 30 Oct 2026): it asks what is
 *  happening to you, then offers the parts of life the law governs (a door marked when its law changed lately or changes
 *  soon), then the law's calendar around today, the conversation as it lives, the guides, the week's Bulletin, the newest
 *  posts of «قانون بالأرقام». The
 *  archive (the shelf, the issues, the finance law) is one tap away, in «المكتبة». */
export default function HomePage() {
  const { t } = useTranslation();
  usePageTitle([t('corpus.heroTitle')]);
  const situations = useSituations();
  // This week's Bulletin: in the flow on a phone, beside the question on a desk, where its first screen was the box,
  // the doors and white (UX16 of the phone-test review).
  const weekSection = <Suspense fallback={null}><HomeWeek /></Suspense>;

  return (
    <Page width="reading" className="gap-8 sm:gap-10"
          aside={<div className="hidden lg:block">{weekSection}</div>}>
      {/* The question and the twelve doors, on the paper and on the first screen of a phone (U1, U3 of
          the Moroccan-design review, 25 Oct 2026): no card around the box, as on Google's home. */}
      <section className="flex flex-col gap-4 pt-1 sm:gap-5 sm:pt-6">
        <h1 className="m-0 text-balance text-h2 font-bold leading-[1.25] sm:text-display">{t('corpus.heroTitle')}</h1>
        <p className="m-0 max-w-[52ch] text-body leading-relaxed text-ink-soft sm:text-lead">{t('corpus.heroLead')}</p>
        <SearchBox big />
        <div className="flex min-w-0 items-center gap-3">
          <span className="shrink-0 text-body text-ink-soft">{t('home.try')}</span>
          <Examples size="big" line />
        </div>
      </section>

      <section aria-labelledby="home-topics" className="-mt-2 flex flex-col gap-2 sm:mt-0">
        <h2 id="home-topics" className="sr-only">{t('home.topics')}</h2>
        <Suspense fallback={<div aria-hidden="true" className="h-[396px] sm:h-[262px]" />}><TopicRow /></Suspense>
        <Link to="/topics" className="inline-flex min-h-11 items-center self-end text-body font-medium no-underline">{t('home.allTopics')}</Link>
      </section>

      <Suspense fallback={null}><HomeCalendar /></Suspense>
      <Suspense fallback={null}><HomeTalk /></Suspense>

      {situations.data?.length ? (
        <section aria-labelledby="home-situations" className="flex flex-col gap-4">
          <SectionHeader id="home-situations" title={t('situations.home')} lead={t('situations.homeLead')} to="/situations" more={t('situations.all')} />
          <Suspense fallback={null}><SituationList limit={6} tiles /></Suspense>
        </section>
      ) : null}

      <div className="lg:hidden">{weekSection}</div>

      <Suspense fallback={null}><HomeEnd /></Suspense>
    </Page>
  );
}

