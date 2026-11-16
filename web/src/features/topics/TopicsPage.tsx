import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate } from 'react-router-dom';
import { longDate } from '@/features/corpus/format';
import { api } from '@/shared/services/api';
import { go } from '@/shared/services/motion';
import { ArchDoor, ArchWindow } from './Arch';
import { topicColour } from './colour';
import { useOpenTopic } from './open';
import { useTopics, type Named, type TopicSummary } from './topics.api';
import '@/shared/locales/pages';
import { usePageTitle } from '@/shared/services/title';
import { Page, PageSkeleton } from '@/shared/components/ui';
import './topics.css';

type Moment = { key: string; title: Named; lead: Named | null; path: string };
type Moments = { slug: string; doors: Moment[]; count: number; next: { date: string; title: Named | null; path: string } | null }[];

/** How many moments a bay shows; a phone shows three of them (topics.css). */
const SHOWN = 4;

/**
 * /topics (R2 of the for-everyone review; drawn again on 30 Oct 2026): the twelve parts of life as
 * an arcade, each topic a bay whose arch stands on its threshold with its name beside it like a door's plaque, and under
 * it what happens to people there, in their words («طردوني», «زاد عليا فالكرا»), each with the line of the law that
 * answers it, its figures in bold; how many more, and the day its law changes next. Each moment opens its answer.
 */
export default function TopicsPage() {
  const { t, i18n } = useTranslation();
  usePageTitle([t('pages:topics.title')]);
  const topics = useTopics();
  const moments = useQuery({ queryKey: ['topics', 'moments'], queryFn: () => api<Moments>('/topics/moments/'), staleTime: 600_000 });
  const lang = i18n.language === 'fr' ? 'fr' : 'ar';
  const bySlug = new Map((moments.data ?? []).map((m) => [m.slug, m]));
  const total = (moments.data ?? []).reduce((n, m) => n + m.count, 0);
  return (
    <Page width="wide" className="tp">
      <header className="tp-head">
        <h1>{t('pages:topics.title')}</h1>
        <p>
          {total && topics.data
            ? t('pages:topics2.lead', { moments: t('pages:topics2.moments', { count: total }), topics: topics.data.length })
            : t('pages:topics.lead')}
        </p>
      </header>
      {topics.data ? (
        // On a phone and a tablet the bays run long: the twelve arches first, each a way to its bay on the page.
        <nav className="tp-jump" aria-label={t('pages:topics2.jump')}>
          <ul>
            {topics.data.map((x) => (
              <li key={x.slug}>
                <a href={`#${x.slug}`} onClick={(e) => {
                  e.preventDefault();
                  document.getElementById(x.slug)?.scrollIntoView({ behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' });
                  history.replaceState(null, '', `#${x.slug}`);
                }}>
                  <ArchDoor slug={x.slug} className="w-12" />
                  <span>{(x.short ?? x.name)[lang]}</span>
                </a>
              </li>
            ))}
          </ul>
        </nav>
      ) : null}
      {topics.data ? (
        <div className="tp-arcade">
          {topics.data.map((x) => <Bay key={x.slug} topic={x} moments={bySlug.get(x.slug)} lang={lang} />)}
        </div>
      ) : <PageSkeleton />}
    </Page>
  );
}

/** One topic: its door (the arch on its threshold, its name and how many moments), its first moments with their
 *  answers, how many more, its next change. */
function Bay({ topic, moments, lang }: { topic: TopicSummary; moments?: Moments[number]; lang: 'ar' | 'fr' }) {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const { pending, warm, open } = useOpenTopic();
  const path = `/topics/${topic.slug}`;
  const shown = moments?.doors.slice(0, SHOWN) ?? [];
  const more = (moments?.count ?? 0) - shown.length;
  const pick = (x: Named | null | undefined) => (x ? (lang === 'fr' && x.fr) || x.ar : '');
  return (
    <section id={topic.slug} className="tp-bay" style={topicColour(topic.slug)} aria-labelledby={`tp-${topic.slug}`}>
      <Link to={path} lang={lang} className="tp-door" aria-busy={pending === topic.slug || undefined}
            onPointerEnter={() => warm(topic.slug)} onPointerDown={() => warm(topic.slug)} onFocus={() => warm(topic.slug)}
            onClick={(e) => {
              if (e.metaKey || e.ctrlKey || e.shiftKey) return;
              e.preventDefault();
              // The arch grows into the topic's window (U7 of the Moroccan-design review).
              const arch = e.currentTarget.querySelector<HTMLElement>('[data-vt]');
              open(topic.slug, () => go(navigate, path, arch, 'topic-arch'));
            }}>
        <ArchWindow slug={topic.slug} className="arch" />
        <span className="nm">
          <h2 id={`tp-${topic.slug}`}>{topic.name[lang]}</h2>
          <span className="n">{moments?.count ? t('pages:topics2.moments', { count: moments.count }) : pick(topic.lead)}</span>
        </span>
      </Link>
      {shown.length ? (
        <ul className="tp-moments">
          {shown.map((m) => (
            <li key={m.key}>
              <Link to={m.path} lang={lang}>
                <b dir="auto">{pick(m.title)}</b>
                {m.lead ? <span dir="auto">{figures(pick(m.lead))}</span> : null}
              </Link>
            </li>
          ))}
        </ul>
      ) : null}
      {moments?.next ? (
        <Link to={moments.next.path} className="tp-next" lang={lang}>
          <span className="dot" aria-hidden="true" />
          <span><b>{t('pages:topics2.changes', { date: longDate(moments.next.date, i18n.language) })}</b> {pick(moments.next.title)}</span>
        </Link>
      ) : null}
      {shown.length ? (
        <Link to={path} className="tp-more">{more > 0 ? t('pages:topics2.more', { count: more }) : t('pages:topics.open')}</Link>
      ) : null}
    </section>
  );
}

/** An answer's line with the law's figures in bold: «90 يوم», «8%», «150 حتى 700 درهم». */
function figures(line: string): React.ReactNode[] {
  return line.split(/(\d[\d.,\u00a0\u202f]*\d%?|\d%?)/).map((part, i) => (i % 2 ? <b key={i}>{part}</b> : part));
}
