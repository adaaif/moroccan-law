import { useTranslation } from 'react-i18next';
import { Link, useParams } from 'react-router-dom';
import { longDate } from '@/features/corpus/format';
import FollowButton from '@/features/follows/FollowButton';
import { topicColour } from './colour';
import { ArchWindow } from './Arch';
import { SituationArt } from '@/features/situations/SituationArt';
import { situationPath } from '@/features/situations/to';
import { chipClass } from '@/shared/components/buttons';
import { useTopic, type TopicTalk } from './topics.api';
import '@/shared/locales/pages';
import { usePageTitle } from '@/shared/services/title';
import { Page, PageSkeleton } from '@/shared/components/ui';
import { textName } from '@/features/corpus/names';
import { LoadError } from '@/features/corpus/NotFound';
import { lazy, Suspense, useState } from 'react';

// A topic's folder adds its doors, tools and reform line (F3, F16 of the family plan); its code loads only then, and it
// starts with the page's own (hub.ts).
const HubExtras = lazy(() => import('@/topics/kit/HubExtras'));
// A desk holds the topic's instruments in its side column, above «القانون كامل» (A12 of the road-signposted review).
const HubInstruments = lazy(() => import('@/topics/kit/HubExtras').then((m) => ({ default: m.HubInstruments })));

/** /topics/:slug (R2): one part of life — its situations first, then its laws by their everyday names, then what
 *  changed in the last half year. Every line ends at the law itself. */
export default function TopicPage() {
  const { slug = '' } = useParams();
  const { t, i18n } = useTranslation();
  const topic = useTopic(slug);
  const lang = i18n.language === 'fr' ? 'fr' : 'ar';
  usePageTitle([topic.data?.name[lang], t('pages:topics.title')]);
  if (topic.isLoading) return <Main><PageSkeleton /></Main>;
  const d = topic.data;
  if (!d) return <Main><LoadError error={topic.error} retry={() => void topic.refetch()} /></Main>;
  const pickName = (n: { ar: string; fr: string }) => (lang === 'fr' && n.fr) || n.ar;
  // The folder's pages that sit among the topic's texts (A9 of the road-signposted review).
  const placed = (d.module?.tools ?? []).filter((x) => x.place === 'whole');
  // A topic with a folder: «القانون كامل» under the doors on a phone, beside them on a desk (U18 of
  // the Moroccan-design review: the desk's other half was empty paper).
  const whole = d.module ? (
    <Whole tabs={{
            laws: (
              d.codes.length ? (
            <Section title={t('pages:topics.laws')}>
              <ul className="m-0 flex list-none flex-col p-0">
                {d.codes.map((c) => {
                  const inner = (
                    <>
                      <span className="flex min-w-0 flex-1 flex-col">
                        <span lang={lang} className="text-lead font-medium leading-snug">{c.name[lang]}</span>
                        <span className="text-meta text-ink-soft">
                          {c.number_as_printed ? `${t(`corpus.types.${c.type ?? 'law'}`)} ${c.number_as_printed}` : null}
                          {c.articles ? `${c.number_as_printed ? t('corpus.listSep') : ''}${t('corpus.articlesCount', { count: c.articles })}` : null}
                        </span>
                      </span>
                      {c.state === 'in_corpus'
                        ? c.status === 'in_force' ? <span className="flex items-center gap-1.5 text-meta text-in-force"><span aria-hidden="true" className="size-2 rounded-full bg-in-force" />{t('corpus.standing.in_force')}</span> : null
                        : <span className="text-meta text-ink-soft">{t('pages:topics.onAdala')}</span>}
                    </>
                  );
                  const cls = 'flex min-h-14 items-center gap-3 py-3 text-ink no-underline hover:text-stamp';
                  return (
                    <li key={c.key} className="border-t border-rule first:border-t-0">
                      {c.state === 'in_corpus' && c.path ? <Link to={c.path} className={cls}>{inner}</Link>
                        : c.official ? <a href={c.official} target="_blank" rel="noreferrer" className={cls}>{inner}</a> : <span className={cls}>{inner}</span>}
                    </li>
                  );
                })}
              </ul>
              {placed.length ? (
                <ul className="m-0 flex list-none flex-col border-t border-rule p-0 pt-1">
                  {placed.map((x) => (
                    <li key={x.key}>
                      <Link to={x.to?.includes('/') ? `/topics/${d.slug}/${x.to}` : `/topics/${d.slug}/tools/${x.key}`}
                            className="flex min-h-12 items-center gap-2 py-2 text-body text-ink no-underline hover:text-stamp">
                        <span lang={lang} className="flex-1">{pickName(x.title)}</span>
                        <span aria-hidden="true" className="text-ink-soft">›</span>
                      </Link>
                    </li>
                  ))}
                </ul>
              ) : null}
            </Section>
          ) : null
            ),
            guides: (
              d.situations.length ? (
            <Section title={t('pages:topics.guides')}>
              <ul className="m-0 grid list-none gap-3 p-0 sm:grid-cols-2">
                {d.situations.map((s) => (
                  <li key={s.slug}>
                    <Link to={situationPath(s.slug)} lang={lang}
                          className="flex h-full min-h-20 items-center gap-4 rounded-card bg-paper p-3 text-ink no-underline hover:text-stamp">
                      <SituationArt slug={s.slug} topic={d.slug} size={56} />
                      <span className="flex min-w-0 flex-1 flex-col gap-1">
                        <span className="text-lead font-semibold leading-snug">{s.title[lang]}</span>
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            </Section>
          ) : null
            ),
            words: (
              d.words.length ? (
            <Section title={t('pages:topics.words')}>
              <ul className="m-0 flex list-none flex-wrap gap-2 p-0">
                {d.words.map((w) => (
                  <li key={w.slug}>
                    <Link to={`/words/${w.slug}`} lang={lang} className={chipClass(false, 'h-11 text-body')}>{w.term[lang]}</Link>
                  </li>
                ))}
              </ul>
            </Section>
          ) : null
            ),
            questions: (
              d.talk && (d.talk.posts.length || d.talk.questions.length) ? <TalkBlock talk={d.talk} slug={d.slug} /> : null
            ),
            recent: (
              <Section title={t('pages:topics.recent')} lead={t('pages:topics.recentLead')}>
            {d.recent.length ? (
              <ul className="m-0 flex list-none flex-col p-0">
                {d.recent.map((r) => (
                  <li key={r.path} className="border-t border-rule first:border-t-0">
                    <Link to={r.path} className="flex min-h-12 items-baseline gap-3 py-2.5 text-ink no-underline hover:text-stamp">
                      <span dir="auto" className="min-w-0 flex-1 text-body leading-snug">{textName(r, i18n.language, 70)}</span>
                      <span className="shrink-0 text-meta text-ink-soft">{longDate(r.date, i18n.language)}</span>
                    </Link>
                  </li>
                ))}
              </ul>
            ) : <p className="m-0 text-body text-ink-soft">{t('pages:topics.recentNone')}</p>}
          </Section>
            ),
          }} />
  ) : null;
  return (
    <Main aside={whole ? (
      <div style={topicColour(d.slug)} className="hidden lg:flex lg:flex-col lg:gap-6">
        {d.module ? <Suspense fallback={null}><HubInstruments slug={d.slug} module={d.module} side /></Suspense> : null}
        {whole}
      </div>
    ) : undefined}>
      <div style={topicColour(d.slug)} className="flex flex-col gap-5">
        {/* On a phone a topic with a folder leaves the way back to the bar's «المواضيع», lit on this page (A6). */}
        <Link to="/topics" className={`min-h-11 items-center self-start text-body text-ink-soft no-underline hover:text-stamp ${d.module ? 'hidden sm:inline-flex' : 'inline-flex'}`}>
          {t('pages:topics.all')}
        </Link>
        {/* The topic's face: its scene seen through its door (U1 of the Moroccan-design review), its name, «متابعة».
            A topic with a folder says it on one line, on the paper (A6 of the road-signposted review: 230 px became 64), so
            its first screen holds the moment the reader came with; its line waits for a desk. */}
        {d.module ? (
          <header className="flex flex-wrap items-center gap-3 sm:gap-5">
            <ArchWindow slug={d.slug} className="w-[52px] sm:w-[72px]" />
            <div className="flex min-w-[120px] flex-1 flex-col">
              <h1 lang={lang} className="m-0 text-h2 font-bold leading-tight sm:text-h1">{d.name[lang]}</h1>
              <p lang={lang} className="m-0 hidden text-body text-ink-soft sm:block">{d.lead[lang]}</p>
            </div>
            <FollowButton path={`/topics/${d.slug}`} compact />
          </header>
        ) : (
          <header className="flex items-center gap-4 rounded-card bg-sheet px-4 py-4 sm:gap-6 sm:px-7 sm:py-6">
            <ArchWindow slug={d.slug} className="w-[84px] sm:w-[120px]" />
            <div className="flex min-w-0 flex-1 flex-col items-start gap-2">
              <h1 lang={lang} className="m-0 text-h1 font-bold leading-tight">{d.name[lang]}</h1>
              <p lang={lang} className="m-0 text-body text-ink-soft">{d.lead[lang]}</p>
              <FollowButton path={`/topics/${d.slug}`} />
            </div>
          </header>
        )}

        {/* Its place held while it comes: «القانون كامل» under it is never pushed off the screen. */}
        {d.module ? <Suspense fallback={<div aria-hidden="true" className="min-h-svh" />}><HubExtras slug={d.slug} module={d.module} /></Suspense> : null}

        {d.module ? <div className="lg:hidden">{whole}</div> : (
          <>
        {d.situations.length ? (
          <Section title={t('pages:topics.guides')}>
            <ul className="m-0 grid list-none gap-3 p-0 sm:grid-cols-2">
              {d.situations.map((s) => (
                <li key={s.slug}>
                  <Link to={situationPath(s.slug)} lang={lang}
                        className="flex h-full min-h-20 items-center gap-4 rounded-card bg-paper p-3 text-ink no-underline hover:text-stamp">
                    <SituationArt slug={s.slug} topic={d.slug} size={56} />
                    <span className="flex min-w-0 flex-1 flex-col gap-1">
                      <span className="text-lead font-semibold leading-snug">{s.title[lang]}</span>
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          </Section>
        ) : null}

        {d.words.length ? (
          <Section title={t('pages:topics.words')}>
            <ul className="m-0 flex list-none flex-wrap gap-2 p-0">
              {d.words.map((w) => (
                <li key={w.slug}>
                  <Link to={`/words/${w.slug}`} lang={lang} className={chipClass(false, 'h-11 text-body')}>{w.term[lang]}</Link>
                </li>
              ))}
            </ul>
          </Section>
        ) : null}

        {d.codes.length ? (
          <Section title={t('pages:topics.laws')}>
            <ul className="m-0 flex list-none flex-col p-0">
              {d.codes.map((c) => {
                const inner = (
                  <>
                    <span className="flex min-w-0 flex-1 flex-col">
                      <span lang={lang} className="text-lead font-medium leading-snug">{c.name[lang]}</span>
                      <span className="text-meta text-ink-soft">
                        {c.number_as_printed ? `${t(`corpus.types.${c.type ?? 'law'}`)} ${c.number_as_printed}` : null}
                        {c.articles ? `${c.number_as_printed ? t('corpus.listSep') : ''}${t('corpus.articlesCount', { count: c.articles })}` : null}
                      </span>
                    </span>
                    {c.state === 'in_corpus'
                      ? c.status === 'in_force' ? <span className="flex items-center gap-1.5 text-meta text-in-force"><span aria-hidden="true" className="size-2 rounded-full bg-in-force" />{t('corpus.standing.in_force')}</span> : null
                      : <span className="text-meta text-ink-soft">{t('pages:topics.onAdala')}</span>}
                  </>
                );
                const cls = 'flex min-h-14 items-center gap-3 py-3 text-ink no-underline hover:text-stamp';
                return (
                  <li key={c.key} className="border-t border-rule first:border-t-0">
                    {c.state === 'in_corpus' && c.path ? <Link to={c.path} className={cls}>{inner}</Link>
                      : c.official ? <a href={c.official} target="_blank" rel="noreferrer" className={cls}>{inner}</a> : <span className={cls}>{inner}</span>}
                  </li>
                );
              })}
            </ul>
          </Section>
        ) : null}

        {d.talk && (d.talk.posts.length || d.talk.questions.length) ? <TalkBlock talk={d.talk} slug={d.slug} /> : null}

        <Section title={t('pages:topics.recent')} lead={t('pages:topics.recentLead')}>
          {d.recent.length ? (
            <ul className="m-0 flex list-none flex-col p-0">
              {d.recent.map((r) => (
                <li key={r.path} className="border-t border-rule first:border-t-0">
                  <Link to={r.path} className="flex min-h-12 items-baseline gap-3 py-2.5 text-ink no-underline hover:text-stamp">
                    <span dir="auto" className="min-w-0 flex-1 text-body leading-snug">{textName(r, i18n.language, 70)}</span>
                    <span className="shrink-0 text-meta text-ink-soft">{longDate(r.date, i18n.language)}</span>
                  </Link>
                </li>
              ))}
            </ul>
          ) : <p className="m-0 text-body text-ink-soft">{t('pages:topics.recentNone')}</p>}
        </Section>
          </>
        )}
      </div>
    </Main>
  );
}

/** A topic with a folder of its own keeps its first screens for the moment the reader came with (T5 of the road tools
 *  review): its guides, words, laws, questions and recent texts wait at the end, as the tabs of «القانون كامل». */
function Whole({ tabs }: { tabs: Record<'laws' | 'guides' | 'words' | 'questions' | 'recent', React.ReactNode> }) {
  const { t } = useTranslation();
  const present = (Object.keys(tabs) as (keyof typeof tabs)[]).filter((k) => tabs[k]);
  const [tab, setTab] = useState(present[0]);
  if (!present.length) return null;
  return (
    <section className="flex flex-col gap-3" aria-labelledby="whole">
      <h2 id="whole" className="m-0 text-h3 font-bold">{t('pages:topics.whole')}</h2>
      {/* The tabs scroll on a phone and wrap in the desk's column (A2 of the road-signposted review: no scrollbar, none cut). */}
      <div role="tablist" aria-labelledby="whole" className="-mx-1 flex gap-2 overflow-x-auto px-1 pb-1 lg:flex-wrap lg:overflow-visible">
        {present.map((k) => (
          <button key={k} type="button" role="tab" aria-selected={k === tab} onClick={() => setTab(k)}
                  className={`min-h-11 shrink-0 rounded-full border px-4 text-body ${k === tab ? 'border-ink bg-ink text-sheet' : 'border-rule bg-sheet'}`}>
            {t(`pages:topics.tabs.${k}`)}
          </button>
        ))}
      </div>
      <div role="tabpanel">{tabs[tab]}</div>
    </section>
  );
}

function Section({ title, lead, children }: { title: string; lead?: string; children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-2 rounded-card bg-sheet px-5 py-5 sm:px-7">
      <h2 className="m-0 text-lead font-semibold">{title}</h2>
      {lead ? <p className="m-0 text-meta text-ink-soft">{lead}</p> : null}
      {children}
    </section>
  );
}

function Main({ children, aside }: { children: React.ReactNode; aside?: React.ReactNode }) {
  return <Page width="reading" aside={aside} className="gap-6">{children}</Page>;
}


/** The topic's conversation (29 Oct 2026): its place's liveliest posts and the questions waiting longest, each a way
 *  into its post, the way into the topic's discussion, and who moderates it. */
function TalkBlock({ talk, slug }: { talk: TopicTalk; slug: string }) {
  const { t } = useTranslation();
  return (
    <Section title={t('pages:topics.questions')}>
      <ul className="m-0 flex list-none flex-col gap-2 p-0">
        {[...talk.questions, ...talk.posts.filter((p) => !talk.questions.some((q) => q.id === p.id))].map((q) => (
          <li key={q.id}>
            <Link to={q.path} className="flex flex-col gap-1 rounded-card bg-talk-wash px-4 py-3 text-ink no-underline hover:text-talk">
              <span dir="auto" className="line-clamp-2 text-body font-semibold">{q.title || q.body}</span>
              <span className="text-meta text-ink-soft">
                {q.kind === 'question' && !q.reply_count ? t('pages:topics.talkWaiting') : t('pages:topics.talkComments', { count: q.reply_count })}
              </span>
            </Link>
          </li>
        ))}
      </ul>
      <p className="m-0 mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-meta">
        <Link to={`/talk/${slug}`} className="inline-flex min-h-11 items-center font-medium no-underline">{t('pages:topics.talkOpen')}</Link>
        {talk.moderators.length ? (
          <span className="text-ink-soft">{t('pages:topics.talkModerators', { names: talk.moderators.map((m) => m.name).join('، ') })}</span>
        ) : null}
      </p>
    </Section>
  );
}
