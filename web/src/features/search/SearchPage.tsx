import { createContext, Fragment, lazy, Suspense, useContext, useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/shared/services/api';
import { todayIso } from '@/shared/services/today';
import { useTranslation } from 'react-i18next';
import { Link, Navigate, useNavigate, useSearchParams } from 'react-router-dom';
import { go } from '@/shared/services/motion';
import { Stamp } from '@/features/corpus/article/Stamp';
import { AR, articleName, longDate } from '@/features/corpus/format';
import { Examples } from './Examples';
import { SearchBox } from './SearchBox';
import { Running, Searching } from './Searching';
import { DoorAnswer, Margin, Nearest, People, Said, TopicCard } from './SearchParts';
import { Choices, FamousCard, Maybe } from './Famous';
import { TYPE_GROUPS, useSearchResults, type Changed, type FoundBy, type Resolved, type SearchResponse, type Segment, type TopicWord } from './search.api';
import { finishReading, noteFound, noteOpened } from './events';
import { textName } from '@/features/corpus/names';
import '@/shared/locales/pages';
import '@/shared/design/french.css';
import { usePageTitle } from '@/shared/services/title';
import { Card, Page } from '@/shared/components/ui';
import { LoadError } from '@/features/corpus/NotFound';
import { chipClass } from '@/shared/components/buttons';
import PlaceDoor from '@/features/places/PlaceDoor';

// The road's computed answer (X2 of the road tools review): its code comes only for a question about the road.
const RoadAnswer = lazy(() => import('@/topics/road/SearchAnswer'));
// The consumer's computed answer (S2 of the consumer plan): the same, for a question about buying.
const ConsumerAnswer = lazy(() => import('@/topics/consumer/SearchAnswer'));

// Every year the Bulletin holds, this one first (PX17 of the where-it-trips review: 2012 was the last, though the answers
// reach 1956, and 2027 would have been missing in January).
const YEARS = Array.from({ length: Number(todayIso().slice(0, 4)) - 1956 + 1 }, (_, i) => String(Number(todayIso().slice(0, 4)) - i));

const FIRST = 3;   // texts shown before the fold

/** The words a search searched (after the question's own words were set aside, Darija spelled as the law spells it),
 *  carried by every article it leads to as ?hl=, so the law lights them (H1 of the search's marks, 29 Oct 2026). */
const Searched = createContext('');
const withWords = (path: string, words: string) =>
  words ? `${path}${path.includes('?') ? '&' : '?'}hl=${encodeURIComponent(words)}` : path;

export default function SearchPage() {
  const { t, i18n } = useTranslation();
  const [params, setParams] = useSearchParams();
  const q = params.get('q') ?? '';
  usePageTitle([q ? `«${q}»` : null, t('pages:search.heading')]);
  const type = params.get('type') ?? '';
  const year = params.get('year') ?? '';
  const repealed = params.get('repealed') === '1';
  const page = Number(params.get('page')) || 1;
  const search = useSearchResults({ q, type, year, repealed, page, lang: i18n.language === 'fr' ? 'fr' : 'ar' });
  // The questions people asked already, asked beside the answer, never before it (PX10): up to a second of a search went
  // on them. The first page of a question only.
  const asked = useQuery({ queryKey: ['searchPeople', q], enabled: Boolean(q.trim()) && page === 1, staleTime: 300_000,
    queryFn: () => api<{ topic: string | null; people: NonNullable<SearchResponse['people']> }>(`/search/people/?q=${encodeURIComponent(q)}`) });

  const set = (changes: Record<string, string>) => {
    const next = new URLSearchParams(params);
    for (const [k, v] of Object.entries(changes)) {
      if (v) next.set(k, v);
      else next.delete(k);
    }
    if (!('page' in changes)) next.delete('page');
    setParams(next);
  };
  const d = search.data;
  // A new question: the answers kept on the page are another question's, so they give way to the wait (Searching).
  // A filter or a page changes the same question's answers: they stay, dimmed, under the running bar.
  const asking = search.isFetching && (!d || d.query.trim() !== q.trim());
  // A search about violence leaves no trace on the device (F14 of the family plan): out of «بحثت مؤخرا عن».
  useEffect(() => {
    if (!d?.private) return;
    try {
      const kept = JSON.parse(localStorage.getItem('law.searches') ?? '[]') as string[];
      localStorage.setItem('law.searches', JSON.stringify(kept.filter((x) => x.trim() !== d.query.trim())));
    } catch { /* nothing kept */ }
  }, [d?.private, d?.query]);
  // Back at the answers: how long the one opened stayed open is said now (B3 of the search plan).
  useEffect(() => { finishReading(); }, []);
  const [filtersOpen, setFiltersOpen] = useState(false);
  // Shown for this question only: a new question starts folded again.
  const [partialFor, setPartialFor] = useState('');
  const showPartial = partialFor === q;
  // Not one word of the question in any text, and no topic or door understood it (UX8 of the phone-test review:
  // «زززززز» listed 133 texts found by meaning, a named official's delegation first): said so, the nearest by meaning
  // a tap away.
  const [meaningFor, setMeaningFor] = useState('');
  const active = Number(!!type) + Number(!!year) + Number(repealed);
  // A filter that leaves the words in no text (PX4): said of the filters, which stay to be undone; it said the words
  // were nowhere on the site and hid every filter («المناجم», a dahir of 2025: 445 texts hold the word).
  const filteredOut = Boolean(d && active && !d.jump && (!d.results.length || d.understood_as === 'meaning'));
  const unmatched = Boolean(d && d.understood_as === 'meaning' && !d.doors?.length && !d.topics?.length && !d.place && !d.jump
    && !d.answer && meaningFor !== q && !active);
  // After the first page's best texts the rest fold into one line (N11 of the read-and-trusted review: an eviction's
  // answer ran to 83 texts on a page 6,852 px long, the hospitals' rules second).
  const [unfoldedFor, setUnfoldedFor] = useState('');
  const folded = Boolean(d && d.page === 1 && unfoldedFor !== q && d.texts > FIRST && d.results.length > FIRST);
  // Filters only when there is something to filter, or a filter is on (P7 of the polish review): a filter beside
  // «nothing found» offered nothing; a filter that emptied the page stays, to be undone.
  // Only some words found, and a topic or the nearest moments above are the better answer: texts wait behind a tap.
  const nearer = Boolean(d?.topics?.length || d?.nearest?.length);
  // Only some of its words anywhere, or a word «repaired» into another, and nothing understood it: no door, no topic,
  // no place, no citation (RD11 of the readers review: «طقس الرباط غدا» listed 447 texts, «كيفاش نطيب الطاجين»
  // was read «نايب الطاجين» and listed 19). Said plainly; the texts wait behind the same tap.
  const outside = Boolean(d && (d.partial || d.understood_as === 'spelling') && !nearer && !d.doors?.length && !d.place && !d.jump
    && !d.answer && !d.famous?.length && !showPartial && !active);
  const hidden = Boolean((d?.partial && nearer && !showPartial) || unmatched || outside);
  const filterable = Boolean(q && d && !asking && !hidden && (d.results.length > 0 || active > 0));

  // The filters, under the box on a phone (behind their button), in the side column on a desk (U18).
  const filters = (id: string, side = false) => (
    <div id={id} className={side ? 'flex flex-col items-start gap-2' : `${filtersOpen ? 'flex' : 'hidden'} flex-wrap items-center gap-2 sm:flex`} role="group" aria-label={t('pages:search.filters')}>
      <Chip on={!type} onClick={() => set({ type: '' })}>{t('pages:search.allTypes')}</Chip>
      {TYPE_GROUPS.map((g) => {
        // How many texts of the kind were found, as Légifrance counts them (B15); a filter on counts itself only.
        // Counted in what the words found; when they filled every entry a search reads, a filter finds more, so no number
        // (PX17: «الكراء» said 52 orders, a tap gave 385).
        const n = !type && !d?.capped ? g.types.split(',').reduce((sum, k) => sum + (d?.kinds?.[k] ?? 0), 0) : 0;
        return (
          <Chip key={g.key} on={type === g.types} onClick={() => set({ type: type === g.types ? '' : g.types })}>
            {t(`pages:search.types.${g.key}`)}{n ? <span className="ms-1.5 text-meta opacity-75">{n}</span> : null}
          </Chip>
        );
      })}
      <label className="ms-auto flex items-center gap-2 text-meta text-ink-soft">
        {t('pages:search.year')}
        <select value={year} onChange={(e) => set({ year: e.target.value })}
                className="h-11 rounded-control border border-field bg-sheet px-2 text-ink">
          <option value="">{t('pages:search.allYears')}</option>
          {YEARS.map((y) => <option key={y} value={y}>{y}</option>)}
        </select>
      </label>
      <label className="flex items-center gap-2 text-meta text-ink-soft">
        <input type="checkbox" checked={repealed} onChange={(e) => set({ repealed: e.target.checked ? '1' : '' })}
               className="size-4 accent-[var(--color-stamp)]" />
        {t('pages:search.withRepealed')}
      </label>
    </div>
  );

  // The words the answers' links carry, so the law lights them (H1 of the search's marks).
  const words = !d || d.jump ? '' : (d.asked ?? d.repaired ?? d.query ?? q);
  // An answer stands above the texts: they come under their own heading.
  const answered = Boolean(d && !d.jump && (d.said?.length || d.doors?.length || d.place || d.answer || d.people?.length || d.famous?.length));

  // Asking starts on the home's box (since 25 Oct 2026); this page is where its answers are.
  if (!q.trim()) return <Navigate to="/" replace />;

  return (
    <Page width="reading" className="gap-6" aside={d && q && !asking && !d.jump && (d.topics?.length || filterable) ? (
      // A desk's other half (U18 of the Moroccan-design review): the topic the question names, its guides and its words
      // of the law, and the filters.
      <div className="hidden lg:flex lg:flex-col lg:gap-5">
        {d.topics?.length ? <TopicCard topic={d.topics[0]} words={d.words} /> : null}
        {filterable ? filters('search-filters-side', true) : null}
      </div>
    ) : undefined}>
      <h1 id="search-top" tabIndex={-1} className="sr-only">{t('pages:search.heading')}</h1>
      {/* The box stays the same box from one question to the next (PX25): rebuilt, it dropped the focus. */}
      <SearchBox initial={q} />
      {/* Said once the answers are in, for a screen reader (PX25): the wait's own words go when they come. */}
      <p className="sr-only" aria-live="polite">{d && !asking ? t('search.texts', { count: d.texts }) : ''}</p>


      {asking ? <Searching key={`wait:${q}`} q={q} /> : null}
      {!asking && !d && search.isError ? <LoadError error={search.error} retry={() => void search.refetch()} /> : null}
      {d && q && !asking ? (
        <Searched.Provider value={words}>
        <div className={`flex flex-col gap-6 ${search.isPlaceholderData ? 'opacity-60' : ''}`}>
          {search.isFetching ? <Running /> : null}
          {/* An article people know by its number or a name, first (C2 of the famous-articles review); then, for a number, the
              other codes that have one; for a word the law uses otherwise, «did you mean». */}
          {d.famous?.map((c) => <FamousCard key={c.path} c={c} onOpen={() => noteOpened(d.log, 0, c.path)} />)}
          {d.choices ? <Choices ch={d.choices} alone={!d.famous?.length} /> : null}
          {d.maybe?.map((m) => <Maybe key={m.path} m={m} />)}
          {/* The person first (30 Oct 2026): their question with the law's words under it, the topic's answer and the
              articles it rests on, the questions people asked already; then the texts the words found. */}
          {d.foreign ? <p className="m-0 rounded-control bg-wash px-4 py-3 text-body">{t('pages:search.foreign')}</p> : null}
          {d.said?.length && !d.jump ? <Said key={q} said={d.said} /> : null}
          {d.topics?.some((x) => x.slug === 'road') && !d.jump ? <Suspense fallback={null}><RoadAnswer q={q} /></Suspense> : null}
          {d.topics?.some((x) => x.slug === 'consumer') && !d.jump ? <Suspense fallback={null}><ConsumerAnswer q={q} /></Suspense> : null}
          {d.place && !d.jump ? <PlaceDoor p={d.place} /> : null}
          {d.doors?.length && !d.jump ? <DoorAnswer doors={d.doors} articles={d.door_articles ?? []} words={(path) => withWords(path, words)} /> : null}
          {!d.doors?.length && d.nearest?.length && !d.jump ? <Nearest doors={d.nearest} /> : null}
          {d.jump && d.repaired && d.understood_as === 'citation'
            // A law's number typed the wrong way round is said, not silently swapped (HM44 of the hard-moment review).
            ? <p className="m-0 text-meta text-ink-soft">{t('pages:search.flipped', { to: d.repaired, from: d.query })}</p> : null}
          {d.jump ? <Jump r={d.jump} onOpen={() => noteOpened(d.log, 0, d.jump?.article?.path ?? d.jump?.text?.path)} /> : null}
          {d.answer && !d.jump ? <Answer a={d.answer} onOpen={() => noteOpened(d.log, 1, d.answer?.path)} /> : null}
          {asked.data?.people.length && d.topics?.length && !d.jump && asked.data.topic === d.topics[0].slug
            ? <People people={asked.data.people} topic={d.topics[0]} /> : null}
          {d.topics?.length && !d.jump ? <div className="lg:hidden"><TopicCard topic={d.topics[0]} words={d.words} /></div> : null}
          {d.words?.length && (!d.results.length || d.partial) ? <LawWords words={d.words} /> : null}
          {d.jump?.state === 'not_in_corpus' && d.results.length
            ? <h2 className="m-0 text-body font-semibold">{t('pages:search.otherTexts')}</h2> : null}
          {(d.partial && nearer && !showPartial) || unmatched || outside || (!d.results.length && !active) ? null : <Summary d={d} answered={answered} filter={filterable ? (
            // On the count's line (UX9 of the phone-test review): alone on its own it took a row of the phone's
            // first screen and left a band of nothing under it.
            <button type="button" onClick={() => setFiltersOpen((o) => !o)} aria-expanded={filtersOpen} aria-controls="search-filters"
                    className="flex h-11 shrink-0 items-center gap-2 rounded-full border border-rule bg-sheet px-4 text-body text-ink sm:hidden">
              <FilterIcon />
              {t('pages:search.filterButton')}
              {active ? <span className="rounded-full bg-stamp px-2 text-meta text-on-stamp">{active}</span> : null}
            </button>
          ) : null} />}
          {/* Under the count's line, where its button is (UX9). */}
          {filterable ? <div className="lg:hidden">{filters('search-filters')}</div> : null}
          {filteredOut ? (
            <section className="flex flex-col items-start gap-2 rounded-control bg-wash px-5 py-4">
              <p className="m-0 font-medium">{t('pages:search.filteredOut')}</p>
              <button type="button" onClick={() => set({ type: '', year: '', repealed: '' })}
                      className="min-h-11 rounded-control px-1 text-body font-medium text-stamp">{t('pages:search.clearFilters')}</button>
            </section>
          ) : null}
          {/* Nothing found by the words, the nearest texts by meaning (PX11): said above them, not only per article. */}
          {d.understood_as === 'meaning' && d.results.length && !unmatched && !active
            ? <p className="m-0 text-meta text-ink-soft">{t('pages:search.byMeaningOnly')}</p> : null}
          {unmatched ? (
            <section className="flex flex-col items-start gap-3 rounded-control bg-wash px-5 py-4">
              <p className="m-0 font-medium">{t('pages:search.noWord')} <bdi dir="auto">«{q}»</bdi></p>
              <Tips />
              <Link to="/topics" className="inline-flex min-h-11 items-center text-body font-medium">{t('pages:search.byTopic')}</Link>
              <button type="button" onClick={() => setMeaningFor(q)} className="min-h-11 rounded-control px-1 text-body font-medium text-stamp">
                {t('pages:search.meaningShow', { count: d.texts })}
              </button>
            </section>
          ) : outside ? (
            <section className="flex flex-col items-start gap-3 rounded-control bg-wash px-5 py-4">
              <p className="m-0 font-medium">{t('pages:search.outside')}</p>
              <Link to="/topics" className="inline-flex min-h-11 items-center text-body font-medium">{t('pages:search.byTopic')}</Link>
              <button type="button" onClick={() => setPartialFor(q)} className="min-h-11 rounded-control px-1 text-body font-medium text-stamp">
                {t('pages:search.partialShow')}
              </button>
            </section>
          ) : d.partial && nearer && !showPartial ? (
            // Only some of the question's words were found, and the question names a part of life: its page above is
            // the better answer; texts holding some of the words wait behind a tap.
            <div className="flex flex-col items-start gap-2 rounded-card bg-sheet px-5 py-4">
              <p className="m-0 text-body text-ink-soft">{t(d.topics?.length ? 'pages:search.partialHidden' : 'pages:search.partialNearest')}</p>
              <button type="button" onClick={() => setPartialFor(q)} className="min-h-11 rounded-control px-1 text-body font-medium text-stamp">
                {t('pages:search.partialShow')}
              </button>
            </div>
          ) : d.results.length ? (
            <>
              <ol className="m-0 list-none rounded-card bg-sheet p-0 px-5 sm:px-8">
                {(folded ? d.results.slice(0, FIRST) : d.results).map((r, i) => (
                  <Result key={r.text.path} r={r} q={d.asked ?? q} onOpen={(path) => noteOpened(d.log, (d.page - 1) * 10 + i + 1, path)} />
                ))}
              </ol>
              {folded ? (
                <button type="button" onClick={() => setUnfoldedFor(q)} aria-expanded={false}
                        className="flex min-h-12 items-center justify-between gap-3 rounded-card bg-sheet px-5 text-start text-body font-medium text-stamp hover:text-stamp-deep sm:px-8">
                  {t('pages:search.otherFolded', { count: d.texts - FIRST })}
                  <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="m6 9 6 6 6-6" /></svg>
                </button>
              ) : null}
            </>
          ) : !d.jump && !filteredOut && !d.famous?.length && !d.choices?.texts.length ? <Empty q={q} exact={d.exact ?? []} /> : null}
          {d.page === 1 && (d.results.length || d.jump) && !unmatched ? <FoundIt key={d.log ?? q} log={d.log} /> : null}
          {d.pages > 1 && !folded && !unmatched && !outside && !(d.partial && nearer && !showPartial) ? <Pager page={d.page} pages={d.pages} go={(p) => {
            // The next page starts at its top, its heading in focus (PX16: it opened at the bottom, its first answer off screen).
            set({ page: String(p) });
            window.scrollTo({ top: 0 });
            document.getElementById('search-top')?.focus({ preventScroll: true });
          }} /> : null}
        </div>
        </Searched.Provider>
      ) : null}
    </Page>
  );
}

function FilterIcon() {
  return (
    <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
      <path d="M4 6h16M7 12h10M10 18h4" />
    </svg>
  );
}

function Chip({ on, onClick, children }: { on: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button type="button" aria-pressed={on} onClick={onClick} className={chipClass(on)}>
      {children}
    </button>
  );
}

/** What a citation in the query points at: opened in one tap, or named when the corpus does not hold it. */
/** «لقيت الجواب؟» under the first page of answers (B3 of the search plan): yes or no, kept on the search's anonymous row,
 *  read with what was opened to see where the search fails. */
function FoundIt({ log }: { log: number | null }) {
  const { t } = useTranslation();
  const [said, setSaid] = useState(false);
  if (log === null) return null;
  if (said) return <p className="m-0 text-meta text-ink-soft">{t('pages:search.foundThanks')}</p>;
  const say = (found: boolean) => { noteFound(log, found); setSaid(true); };
  return (
    <div className="flex flex-wrap items-center gap-2 text-body">
      <span>{t('pages:search.foundIt')}</span>
      <button type="button" onClick={() => say(true)} className="min-h-11 rounded-full border border-rule bg-sheet px-4 text-body">{t('pages:search.foundYes')}</button>
      <button type="button" onClick={() => say(false)} className="min-h-11 rounded-full border border-rule bg-sheet px-4 text-body">{t('pages:search.foundNo')}</button>
    </div>
  );
}

function Jump({ r, onOpen }: { r: Resolved; onOpen: () => void }) {
  const { t, i18n } = useTranslation();
  let title: React.ReactNode = r.name?.[i18n.language === 'fr' ? 'fr' : 'ar'] ?? r.citation.raw;
  let line = t('pages:search.notInCorpusLong');
  let path: string | null = null;
  let action = '';
  if (r.state === 'issue' && r.issue) {
    title = t('search.issue', { key: r.issue.key });
    line = longDate(r.issue.date, i18n.language);
    path = r.issue.path;
    action = t('search.openIssue');
  } else if (r.text) {
    // A code by its name («مدونة السير على الطرق»), its law's number under it.
    const named = r.name && !r.article ? r.name[i18n.language === 'fr' ? 'fr' : 'ar'] : null;
    title = r.article ? `${articleName(r.article.label, t)} — ${textName(r.text, i18n.language, 140)}` : named ?? textName(r.text, i18n.language, 160);
    path = r.article?.path ?? r.text.path;
    action = r.article ? t('search.openArticle') : t('search.openText');
    line = r.state === 'repealed' ? t('pages:search.repealed')
      : r.state === 'text_only' ? t('search.articleMissing', { article: r.citation.article })
      : r.text.in_corpus ? t('pages:search.citationFound') : t('pages:search.notLoadedLong');
    if (named) line = `${t(`corpus.types.${r.text.type}`)} ${r.text.number_as_printed}${t('corpus.listSep')}${line}`;
  }
  // A code named as such («مدونة الأسرة») needs no «إحالة «مدونة الأسرة»» over its own name.
  const said = (!!r.citation.code && !r.citation.article)
    || (typeof title === 'string' && title.replace(/\s+/g, ' ') === r.citation.raw.replace(/\s+/g, ' '));
  return (
    <section aria-label={t('pages:search.citation')}
             className="flex flex-col gap-4 rounded-control border-2 border-stamp bg-wash px-5 py-4 sm:flex-row sm:flex-wrap sm:items-center">
      <div className="flex min-w-0 flex-1 flex-col gap-1">
        {said ? null : <span className="text-meta text-stamp">{t('pages:search.citation')} <bdi {...AR}>«{r.citation.raw}»</bdi></span>}
        <span {...AR} className="font-law text-h2 font-semibold leading-snug text-ink">{title}</span>
        <span className="text-meta text-ink-soft">{line}</span>
      </div>
      {path ? <Link to={path} onClick={onOpen} className="rounded-control bg-stamp px-5 py-2.5 text-center font-medium text-on-stamp no-underline hover:bg-stamp-deep hover:text-on-stamp">{action}</Link> : null}
      {r.state === 'not_in_corpus' && r.official ? (
        <a href={r.official} target="_blank" rel="noreferrer"
           className="flex flex-col rounded-control border border-stamp bg-sheet px-5 py-2 text-center font-medium no-underline hover:bg-paper">
          {t('search.readOnAdala')}
          <span className="text-meta font-normal text-ink-soft">{t('search.adalaWho')}</span>
        </a>
      ) : null}
    </section>
  );
}

function Summary({ d, filter, answered }: { d: SearchResponse; filter?: React.ReactNode; answered: boolean }) {
  const { t } = useTranslation();
  return (
    <div className="flex flex-col gap-1.5">
      {answered && d.results.length ? <div className="sa-texts"><h2>{t('pages:search2.texts')}</h2></div> : null}
      {d.asked && !answered ? (
        <p className="m-0 text-meta text-ink-soft">
          {t('pages:search.asked')} <bdi dir="auto" className="font-medium text-ink">«{d.asked}»</bdi>
        </p>
      ) : null}
      {d.exact?.length ? <p className="m-0 text-meta text-ink-soft">{t('pages:search.exact')} <Quoted words={d.exact} /></p> : null}
      <div className="flex items-center justify-between gap-3">
        <p className="m-0 text-body">
          <strong className="font-semibold">{t('search.texts', { count: d.texts })}</strong>
          {d.articles ? <span className="text-ink-soft">{t('corpus.listSep')}{t('corpus.results', { count: d.articles })}</span> : null}
        </p>
        {filter}
      </div>
      {/* A door or a topic understood the question as typed (U17): a spelling note would only tell a Darija writer
          they wrote it wrong. */}
      {(d.understood_as === 'repaired' || d.understood_as === 'everyday' || d.understood_as === 'arabizi' || d.understood_as === 'spelling') && d.repaired
        && !(d.understood_as === 'spelling' && (d.doors?.length || d.topics?.length)) ? (
        <p className="m-0 text-meta text-ink-soft">
          {d.understood_as === 'arabizi' ? t('pages:search.arabiziLong')
            : d.understood_as === 'spelling' ? t('pages:search.spellingLong')
              : t(d.understood_as === 'everyday' ? 'pages:search.everydayLong' : 'pages:search.repairedLong')}{' '}
          <bdi {...AR} className="font-medium text-ink">«{d.repaired}»</bdi>
        </p>
      ) : null}
      {d.partial ? <p className="m-0 text-meta text-amended">{t('pages:search.someWords')}</p> : null}
      {d.understood_as === 'meaning' ? <p className="m-0 text-meta text-stamp">{t('pages:search.meaningLong')}</p> : null}
    </div>
  );
}

/** The box that answers first (B15 of the search plan): the law's own sentence from the first article, the question's
 *  words marked and, for «شحال» or «combien», the number in bold; where it is, and a way to the whole article. Shown only
 *  when the question's words and its meaning found the same article, never above a topic's own answer. */
function Answer({ a, onOpen }: { a: NonNullable<SearchResponse['answer']>; onOpen: () => void }) {
  const words = useContext(Searched);
  const { t, i18n } = useTranslation();
  const translated = a.text.consolidation === 'translation';
  const consolidated = !translated && !!a.text.consolidation && a.text.consolidation !== 'as_published';
  return (
    <section aria-labelledby="search-answer" className="flex flex-col gap-3 rounded-card border-s-4 border-stamp bg-sheet px-5 py-4 sm:px-6">
      <h2 id="search-answer" className="m-0 text-meta font-semibold text-stamp">{t('pages:search.answerHead')}</h2>
      <blockquote {...AR} className="m-0 max-w-[66ch] font-law text-law leading-[1.8] text-ink">
        {a.sentence.map((seg, i) => seg.num
          ? <strong key={i} className="font-bold text-ink">{seg.t}</strong>
          : seg.hit
            ? <mark key={i} className="rounded-sm bg-wash px-0.5 text-ink shadow-[inset_0_-2px_0_var(--color-stamp-line)]">{seg.t}</mark>
            : <span key={i}>{seg.t}</span>)}
      </blockquote>
      <p className="m-0 flex flex-wrap items-center gap-x-3 gap-y-1.5 text-meta text-ink-soft">
        <span><bdi {...AR} className="font-medium text-ink">{articleName(a.label, t)}</bdi>{t('corpus.listSep')}{textName(a.text, i18n.language, 90)}</span>
        {translated ? <Stamp line translated />
          : consolidated ? <Stamp line consolidated /> : a.page ? <Stamp line page={a.page} /> : a.text.issue ? <Stamp line issue={a.text.issue} /> : null}
      </p>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <Link to={withWords(a.path, words)} onClick={onOpen} className="inline-flex min-h-11 items-center rounded-control bg-stamp px-5 font-medium text-on-stamp no-underline hover:bg-stamp-deep hover:text-on-stamp">
          {t('pages:search.answerRead')}
        </Link>
        <span className="text-meta text-ink-soft">{t('pages:search.answerWhy')}</span>
      </div>
    </section>
  );
}

/** A text found (P9 of the polish review): under its everyday name, what it is and where it was printed, then its two
 *  articles that hold the words best, two lines each, and «و 32 مادة أخرى فيه», found inside the text. A formal title
 *  of four lines and five-line snippets used to make «الطلاق» a long scroll. */
function Result({ r, q, onOpen }: { r: SearchResponse['results'][number]; q: string; onOpen: (path: string) => void }) {
  const { t, i18n } = useTranslation();
  // Its best article, the others it found a tap away in place (UX9: «كراء» showed one law on a phone's first screen).
  const [all, setAll] = useState(false);
  const shown = all ? r.articles : r.articles.slice(0, 1);
  const others = r.articles.length - shown.length;
  const translated = r.text.consolidation === 'translation';
  const consolidated = !translated && !!r.text.consolidation && r.text.consolidation !== 'as_published';
  const name = textName(r.text, i18n.language, 90);
  return (
    <li className="border-t border-rule py-5 first:border-t-0">
      <Link to={r.text.path} onClick={() => onOpen(r.text.path)} title={r.text.title} lang={i18n.language === 'fr' && !r.text.name?.fr ? 'ar' : undefined}
            className="text-h3 font-bold leading-snug text-ink no-underline hover:text-stamp">
        {name}
      </Link>
      <p className="m-0 mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1.5 text-meta text-ink-soft">
        <span>
          {t(`corpus.types.${r.text.type}`)}{r.text.number_as_printed ? ` ${r.text.number_as_printed}` : ''}
          {r.text.year ? `${t('corpus.listSep')}${r.text.year}` : ''}
          {r.text.status === 'repealed' ? <span className="text-repealed">{t('corpus.listSep')}{t('search.repealedShort')}</span>
            // A text in part repealed, or whose standing the site has not established, says so (HM8 of the hard-moment review).
            : r.text.status === 'partly_repealed' || r.text.status === 'unknown'
              ? <span className="text-ink-soft">{t('corpus.listSep')}{t(r.text.status === 'unknown' ? 'pages:search.statusUnknown' : 'pages:search.partlyRepealed')}</span> : null}
        </span>
        {translated ? <Stamp line translated />
          : consolidated ? <Stamp line consolidated /> : r.text.issue ? <Stamp line issue={r.text.issue} /> : null}
      </p>
      {r.articles.length ? (
        <ul className="m-0 mt-2 list-none p-0">
          {shown.map((a) => <Found key={a.eid} a={a} onOpen={onOpen} />)}
        </ul>
      ) : r.title_match ? <p className="m-0 mt-3 border-t border-rule-soft pt-3 text-meta text-ink-soft">{t('pages:search.titleMatch')}</p> : null}
      {others > 0 ? (
        <button type="button" onClick={() => setAll(true)} aria-expanded={false}
                className="mt-1 inline-flex min-h-11 items-center text-body font-medium text-stamp">
          {t('pages:search.more', { count: others + (r.more ?? 0) })}
        </button>
      ) : r.more ? (
        <Link to={withWords(`${r.text.path}?find=${encodeURIComponent(q)}`, q)} onClick={() => onOpen(r.text.path)}
              className="mt-1 inline-flex min-h-11 items-center text-body font-medium no-underline">
          {t('pages:search.more', { count: r.more })}
        </Link>
      ) : null}
    </li>
  );
}

/** An article that holds the words: its number in the stamp's ink, where it sits, two lines of it; an amending
 *  article says which article it changes and leads there (B16 of the search plan). */
function Found({ a, onOpen, text }: {
  a: { label: string; path: string; heading_path?: string[]; page?: number | null; snippet: Segment[]; changes?: Changed[]; found_by?: FoundBy;
       french?: { label: string; snippet: Segment[] } };
  onOpen?: (path: string) => void;
  text?: string;
}) {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const to = withWords(a.path, useContext(Searched));
  const changed = a.changes?.[0];
  // A French reader reads the article's official French first, the Arabic (which alone is the law) a tap away (N16).
  const french = i18n.language === 'fr' ? a.french : undefined;
  return (
    <li className="border-t border-rule-soft py-3 first:border-t-0">
      <Link to={to} className="sa-found group"
            onClick={(e) => {
              onOpen?.(a.path);
              if (e.metaKey || e.ctrlKey || e.shiftKey) return;
              e.preventDefault();
              // The result's label becomes the article's number (U7 of the Moroccan-design review).
              go(navigate, to, e.currentTarget.querySelector<HTMLElement>('[data-label]'), 'article-label');
            }}>
        <Margin label={a.label} />
        <span className="body">
          {text || a.heading_path?.length || a.page || a.found_by === 'meaning' ? (
            <span className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
              {text ? <span className="text-meta text-ink-soft">{text}</span> : null}
              {a.heading_path?.length ? <span {...AR} className="text-meta text-ink-soft">{a.heading_path.at(-1)}</span> : null}
              {a.page ? <Stamp line page={a.page} /> : null}
              {a.found_by === 'meaning' ? <span className="text-meta text-stamp">{t('pages:search.byMeaning')}</span> : null}
            </span>
          ) : null}
          {french ? (
            <span lang="fr" dir="ltr" className="line-clamp-3 max-w-[66ch] text-start font-law-fr text-lead leading-[1.6]">
              <b className="font-semibold">{french.label}</b> <Snippet s={french.snippet} />
            </span>
          ) : <span {...AR} className="line-clamp-2 max-w-[66ch] font-law text-law leading-[1.7]"><Snippet s={a.snippet} /></span>}
        </span>
      </Link>
      {french ? (
        <details className="sa-under mt-1 text-meta">
          <summary className="inline-flex min-h-11 cursor-pointer items-center font-medium text-stamp">{t('pages:search.arabicText')}</summary>
          <span {...AR} className="line-clamp-3 block max-w-[66ch] font-law text-law leading-[1.7]"><Snippet s={a.snippet} /></span>
        </details>
      ) : null}
      {changed ? (
        <p className="sa-under m-0 mt-1 text-meta text-ink-soft">
          <Link to={changed.path} onClick={() => onOpen?.(changed.path)} className="inline-flex min-h-11 items-center font-medium">
            {t(changed.verb === 'added' ? 'pages:search.adds' : 'pages:search.changes', {
              article: frArticle(articleName(changed.label, t), i18n.language), text: textName({ title: '', name: changed.name }, i18n.language, 90) })}
          </Link>
          {a.changes!.length > 1 ? <> {t('pages:search.changesMore', { count: a.changes!.length - 1 })}</> : null}
        </p>
      ) : null}
    </li>
  );
}

/** When the question's own words found nothing whole, the article of the topic's texts that holds each of its words of
 *  the law best (P9 of the polish review); the words themselves are chips on the topic's card. Found by searching the
 *  word, never guessed: «مول الدار بغا يخرجني» reaches article 46 of the rent law, on the eviction notice. */
function LawWords({ words }: { words: TopicWord[] }) {
  const { t, i18n } = useTranslation();
  const lang = i18n.language === 'fr' ? 'fr' : 'ar';
  const found = words.filter((w) => w.article);
  if (!found.length) return null;
  return (
    <Card className="flex flex-col gap-1 py-3 sm:py-4">
      <h2 className="m-0 pt-1 text-meta font-semibold text-ink-soft">{t('pages:search2.wordsArticles')}</h2>
      <ul className="m-0 list-none p-0">
        {found.map((w) => w.article && (
          <Found key={w.slug} a={w.article} text={`${w.term[lang]} · ${textName(w.article.text, i18n.language, 40)}`} />
        ))}
      </ul>
    </Card>
  );
}

function Snippet({ s }: { s: Segment[] }) {
  return (
    <>
      {s.map((seg, i) => seg.hit
        ? <mark key={i} className="rounded-sm bg-wash px-0.5 text-ink shadow-[inset_0_-2px_0_var(--color-stamp-line)]">{seg.t}</mark>
        : <span key={i}>{seg.t}</span>)}
    </>
  );
}

/** The words typed between quotes, as typed, each in guillemets. */
function Quoted({ words }: { words: string[] }) {
  const { t } = useTranslation();
  return <>{words.map((w, i) => <Fragment key={w}>{i ? t('corpus.listSep') : null}<bdi dir="auto" className="font-medium text-ink">«{w}»</bdi></Fragment>)}</>;
}

function Empty({ q, exact }: { q: string; exact: string[] }) {
  const { t } = useTranslation();
  // Quoted words found nowhere as typed: the same words, unquoted, a tap away.
  const loose = q.replace(/["“”„«»]/g, ' ').replace(/\s+/g, ' ').trim();
  return (
    <section className="flex flex-col items-start gap-3 rounded-control bg-wash px-5 py-4">
      {exact.length ? (
        <>
          <p className="m-0 font-medium">{t('pages:search.exactNone')} <Quoted words={exact} /></p>
          {loose ? <Link to={`/search?q=${encodeURIComponent(loose)}`} className="inline-flex min-h-11 items-center text-body font-medium">{t('pages:search.exactLoose')}</Link> : null}
        </>
      ) : (
        <>
          <p className="m-0 font-medium">{t('pages:search.nothingFor')} <bdi dir="auto">«{q}»</bdi></p>
          <Tips />
        </>
      )}
    </section>
  );
}

/** How to ask: the forms the box understands, with examples a reader can tap, and words between quotes. */
function Tips() {
  const { t } = useTranslation();
  const example = t('pages:search.exactExample');
  return (
    <div className="flex flex-col gap-2 text-meta text-ink-soft">
      <p className="m-0">{t('pages:search.tips')}</p>
      <Examples />
      <p className="m-0">
        {t('pages:search.exactTip')}{' '}
        <Link to={`/search?q=${encodeURIComponent(example)}`} dir="auto" className="font-medium">{example}</Link>
      </p>
    </div>
  );
}

function Pager({ page, pages, go }: { page: number; pages: number; go: (p: number) => void }) {
  const { t } = useTranslation();
  return (
    <nav aria-label={t('pages:search.pages')} className="flex items-center justify-center gap-3 text-meta">
      <button type="button" disabled={page <= 1} onClick={() => go(page - 1)}
              className="min-h-11 rounded-control border border-rule bg-sheet px-4 disabled:opacity-40">{t('corpus.previous')}</button>
      <span className="text-ink-soft">{t('pages:search.pageOf', { page, pages })}</span>
      <button type="button" disabled={page >= pages} onClick={() => go(page + 1)}
              className="min-h-11 rounded-control border border-rule bg-sheet px-4 disabled:opacity-40">{t('corpus.next')}</button>
    </nav>
  );
}

/** A numbered article said in a French line as French says it (PX29 of the where-it-trips review: «Modifie المادة 6 de Code
 *  général des impôts»); any other label stays as the law writes it. */
function frArticle(label: string, lang: string): string {
  const m = lang === 'fr' ? label.match(/^(?:المادة|الفصل)\s+(\d[\d-]*)$/) : null;
  return m ? `l’article ${m[1]}` : label;
}
