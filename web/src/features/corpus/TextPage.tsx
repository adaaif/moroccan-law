import { lazy, Suspense, useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, Navigate, useLocation, useNavigate, useNavigationType, useParams } from 'react-router-dom';
import { FRENCH_SIZES, LAW_SIZES, useReading, type TextSize } from '@/shared/stores/reading';
import { SHOWN_STATES, useText, useTextAt, type ArticleItem, type OutlineEntry, type TextDetail } from './corpus.api';
import { useArticleWindow } from './useArticleWindow';
import { AR, DIVISION, articleName, longDate, paragraphs, issueNo, splitAddress, splitLabel } from './format';
import { LawBody } from './LawBody';
import { Explain } from './article/Explain';
import type { Word } from './article/words';
import { Stamp } from './article/Stamp';
import { shortName } from './article/message';
import { STANDING_TONE, articleStanding, textStanding } from './article/status';
import { ReadingBar } from './reading/ReadingTools';
import { useMedia } from './reading/navigation';
import { keptBack } from './reading/back';
import { ConsolidatedNote, ConsolidationSlip } from './history/Versions';
import { SourceSlip } from './SourceSlip';
import { textName } from './names';
import { ReadTo } from './Currency';
import { usePageTitle } from '@/shared/services/title';
import { useDiscussionOpen } from '@/features/accounts/registration';
import { PageSkeleton } from '@/shared/components/ui';

// An article's tools come out only when asked for: their code (sending, saving, embedding, reporting) loads then,
// and a phone's sheet with it.
// A text that cannot load: the not-found page, or the connection lost and a way to try again (P17).
const LoadError = lazy(() => import('./NotFound').then((m) => ({ default: m.LoadError })));
// Said only of an archive text (UX3): with the page's second wave.
const ReadFromScans = lazy(() => import('./ReadFromScans'));
const ArticleRow = lazy(() => import('./article/ArticleActions').then((m) => ({ default: m.ArticleRow })));
const ToolSheet = lazy(() => import('./article/ToolSheet').then((m) => ({ default: m.ToolSheet })));
// The text's link lists and an article's «applied by / cited by» come a moment after its words (the first-load budget).
const TextLinks = lazy(() => import('./history/Lazy').then((m) => ({ default: m.TextLinks })));
const Proposed = lazy(() => import('./history/Proposed'));
// An article's extras, one line of words under it (N7 of the read-and-trusted review), a moment after the law's words.
const Extras = lazy(() => import('./article/Extras'));
const BillStamp = lazy(() => import('./history/Proposed').then((m) => ({ default: m.BillStamp })));
const StandingLine = lazy(() => import('./history/Lazy').then((m) => ({ default: m.StandingLine })));
const Coverage = lazy(() => import('./history/Lazy').then((m) => ({ default: m.Coverage })));
const OnBefore = lazy(() => import('./history/Lazy').then((m) => ({ default: m.OnBefore })));
// The reading place kept and offered, and the line above an article opened by its address (N6, N9 of
// the read-and-trusted review): a moment after the law's words (the first-load budget).
const GoOn = lazy(() => import('./reading/Place').then((m) => ({ default: m.GoOn })));
const KeepPlace = lazy(() => import('./reading/Place').then((m) => ({ default: m.KeepPlace })));
const Landing = lazy(() => import('./reading/Place').then((m) => ({ default: m.Landing })));
// A bill's memorandum and its filing, with their words, only on a bill's page (a margin under the first-load budget).
const Memorandum = lazy(() => import('./history/Memorandum').then((m) => ({ default: m.Memorandum })));
const Bill = lazy(() => import('./history/Memorandum').then((m) => ({ default: m.Bill })));
// An address's article this text does not hold (PX20), and a window that could not load (PX23): said, with a way on.
const Missing = lazy(() => import('./reading/Place').then((m) => ({ default: m.Missing })));
const Failed = lazy(() => import('./reading/Place').then((m) => ({ default: m.Failed })));
// «حول هذا النص» is closed at first: its ruler and its ribbon come when it opens.
const Versions = lazy(() => import('./history/Ruler'));
const VersionRibbon = lazy(() => import('./VersionRibbon').then((m) => ({ default: m.VersionRibbon })));
// The people's words beside the law (R8 of the for-everyone review): a text's «باختصار» and each article's.
const FollowButton = lazy(() => import('@/features/follows/FollowButton'));
const ExplainText = lazy(() => import('@/features/explain/ExplainSlot').then((m) => ({ default: m.ExplainText })));
const ExplainArticle = lazy(() => import('@/features/explain/ExplainSlot').then((m) => ({ default: m.ExplainArticle })));
// An article's discussion count comes after the text, with the discussion's own code.
const TextTalk = lazy(() => import('@/features/discussion/TextTalk'));
// Choosing articles to export, and its bar, come when asked for.
const ExportBar = lazy(() => import('./reading/ExportBar').then((m) => ({ default: m.ExportBar })));
// A desk's side column (P11 of the polish review) comes after the law: a phone never loads it.
const SideColumn = lazy(() => import('./reading/SideColumn').then((m) => ({ default: m.SideColumn })));
// A constitution's own opening, preamble and map of titles (the constitution review, 25 Oct 2026), only on its pages.
const Opening = lazy(() => import('./constitution/ConstitutionHead').then((m) => ({ default: m.Opening })));
const ConstitutionBody = lazy(() => import('./constitution/ConstitutionHead').then((m) => ({ default: m.Body })));
const Lineage = lazy(() => import('./constitution/Lineage').then((m) => ({ default: m.Lineage })));

/** /texts/:id, the address before texts had stable ones: sent on to the text's address. */
export function TextRedirect() {
  const { id = '' } = useParams();
  const location = useLocation();
  const text = useText(id);
  if (text.data) return <Navigate replace to={`${text.data.path}${location.hash ? `/${location.hash.slice(1)}` : ''}`} />;
  return <Shell>{text.isError ? <Suspense fallback={null}><LoadError error={text.error} retry={() => void text.refetch()} /></Suspense> : <PageSkeleton kind="text" />}</Shell>;
}

/** A text, one sheet of paper (the review of 18 Oct 2026): its title and where it was printed, then its articles,
 *  each numbered in the margin with its stamp, the parts printed once where they begin, the tools on request. */
export default function TextPage() {
  const { t, i18n } = useTranslation();
  const location = useLocation();
  const { textPath, focus } = splitAddress(location.pathname);
  // The law on a date (row 8): ?on=2024-01-01 asks for the version in force that day.
  const on = new URLSearchParams(location.search).get('on') ?? '';
  const text = useTextAt(textPath, focus, on);
  usePageTitle([text.data && focus ? text.data.articles.find((a) => a.eid === focus)?.label : null,
                text.data ? (i18n.language !== 'fr' && text.data.title_name) || textName(text.data, i18n.language) : null]);
  const size = useReading((s) => s.size);
  // A tablet or wider opens an article's tools in place, a phone as a sheet from the bottom; a desk has the side column.
  const wide = useMedia('(min-width: 40rem)');
  const desk = useMedia('(min-width: 64rem)');
  const [selecting, setSelecting] = useState(false);
  // An article's address opens on the article (HM13 of the hard-moment review): the text's head is one line, its
  // facts one tap away.
  const [headOpen, setHeadOpen] = useState(false);
  // «الأكثر نقاشا» only once people can write: until then its code and words stay unloaded (N14).
  const talking = useDiscussionOpen();
  // The article in focus carries the row of actions (N7 of the read-and-trusted review, C2): the one the address
  // names (a link, a search result, the outline), or the last one tapped.
  const [active, setActive] = useState(focus);
  useEffect(() => { if (focus) setActive(focus); }, [focus]);
  const [chosen, setChosen] = useState<Set<string>>(new Set());
  const win = useArticleWindow(text.data, textPath, on);
  const { reach } = win;
  const shown = useRef('');
  const navigate = useNavigate();
  // Back to a law left mid-way (PX1): KeepPlace puts the reader's place back; until then neither the address's article
  // nor the loader at the end moves the page. Asked at each history entry (RD21 of the readers review): an article the
  // law names opens on this same page, and back from it landed where that article had left the screen.
  const how = useNavigationType();
  const [entry, setEntry] = useState('');
  const [returning, setReturning] = useState(false);
  if (entry !== location.key) {
    setEntry(location.key);
    setReturning(how === 'POP' && keptBack(location.key)?.path === location.pathname);
  }

  // An address it had before (/ma/loi/2022/66-19), a twin merged into it or its dahir: the API answered with the
  // text at its own address, which the bar now shows (row L1 of the links review).
  useEffect(() => {
    if (text.data && text.data.path !== textPath)
      navigate(`${text.data.path}${focus ? `/${focus}` : ''}${location.search}${location.hash}`, { replace: true });
  }, [text.data, textPath, focus, location.search, location.hash, navigate]);

  // Opened on an article (or sent to one by the outline): there once, loaded around it first if it is not on the page.
  useEffect(() => {
    if (!text.data || !focus || shown.current === focus || returning) return;
    const el = document.getElementById(focus);
    if (el) {
      shown.current = focus;
      el.scrollIntoView({ block: 'start' });
    } else void reach(focus);
  }, [text.data, focus, win.articles, reach, returning]);
  // An address without an article starts at the first one (PX2), whatever window the text was read in before.
  const { start } = win;
  useEffect(() => { if (text.data && !focus && !returning) start(); }, [text.data, focus]); // eslint-disable-line react-hooks/exhaustive-deps

  if (text.isLoading) return <Shell><PageSkeleton kind="text" /></Shell>;
  if (!text.data) return <Shell><Suspense fallback={null}><LoadError error={text.error} retry={() => void text.refetch()} /></Suspense></Shell>;
  const d = text.data;
  const toggle = (eid: string) =>
    setChosen((prev) => {
      const next = new Set(prev);
      if (next.has(eid)) next.delete(eid);
      else next.add(eid);
      return next;
    });
  const pad = 'px-5 sm:px-10';

  // A desk reads with the side column (P11 of the polish review): the outline, the search in the text and the jump
  // stay beside the law; a phone has them in the reading bar.
  const side = desk && Boolean(d.version) && d.total_articles > 1;
  const choosing = (on: boolean) => { setSelecting(on); if (!on) setChosen(new Set()); };

  return (
    <Shell>
      <div className={side ? 'grid grid-cols-[minmax(0,1fr)_340px] items-start gap-8' : ''}>
      <div className="-mx-4 min-w-0 bg-sheet sm:mx-0 sm:rounded-card">
        {focus && !headOpen && !d.constitution ? (
          <CompactHead d={d} label={win.outline.find((o) => o.eid === focus)?.label ?? win.articles.find((a) => a.eid === focus)?.label}
                       pad={pad} onOpen={() => setHeadOpen(true)} />
        ) : (
        <header className={`flex flex-col gap-3 border-b border-rule-soft pb-5 pt-5 sm:gap-4 sm:pb-6 sm:pt-9 ${pad}`}>
          {d.issue ? (
            <nav aria-label={t('corpus.whereFrom')} className="flex flex-wrap items-center gap-2 text-meta text-ink-soft">
              <Link to={`/bo/${d.issue.edition}/${d.issue.key}`} className="text-ink-soft no-underline hover:text-stamp">
                {t('corpus.issueTitle', { number: issueNo(d.issue, t) })}
              </Link>
              {d.rubric ? (
                <>
                  <Chevron />
                  <span {...AR}>{d.rubric}</span>
                </>
              ) : null}
            </nav>
          ) : null}
          {d.constitution ? <Suspense fallback={<TextTitle d={d} />}><Opening d={d} /></Suspense> : <TextTitle d={d} />}
          {/* A law's page starts with the law (U4 of the Moroccan-design review): under the title, one line of facts,
              the source chip and what is wrong for the reader, the parts, the most discussed articles in one row; who
              compiled the text and what changed it last are in «حول هذا النص», as on a desk. */}
          <Badges d={d} follow={!side} />
          <ConsolidatedNote d={d} compact />
          {d.version?.read_from_scans ? <Suspense fallback={null}><ReadFromScans d={d} /></Suspense> : null}
          {!focus && d.version && d.total_articles > 1 ? <Suspense fallback={null}><GoOn d={d} first={win.articles[0]?.eid ?? ''} /></Suspense> : null}
          <Suspense fallback={null}><StandingLine d={d} only="warnings" /></Suspense>
          {/* The law's first words higher on a phone (HM13): the parts are in the reading bar's «الفهرس»; what the site
              read and «ما معنى هذا؟» in «حول هذا النص». A text without the bar keeps its parts here. */}
          {d.constitution ? <Suspense fallback={null}><ConstitutionBody d={d} outline={win.outline} articles={win.articles} /></Suspense>
            : side || d.total_articles > 1 ? null : <Parts d={d} outline={win.outline} />}
          {side || !talking ? null : <Suspense fallback={null}><TextTalk textPath={d.path} outline={win.outline} /></Suspense>}
          <About d={d} />
        </header>
        )}

        {!d.version ? <div className={`py-6 ${pad}`}><NotInCorpus d={d} /></div> : (
          <>
            {on && !focus && d.version.valid_from && on < d.version.valid_from
              ? <div className={`pt-4 ${pad}`}><Suspense fallback={null}><OnBefore d={d} on={on} /></Suspense></div> : null}
            {d.total_articles > 1 && !side ? (
              <ReadingBar name={textName(d, i18n.language)} index={win.outline} loaded={win.articles} textPath={d.path}
                          selecting={selecting} onSelecting={choosing} />
            ) : null}
            <div className={`flex flex-wrap items-start gap-x-12 gap-y-8 pb-10 pt-2 ${pad}`}>
              <div className="flex min-w-0 flex-[999_1_560px] flex-col">
                {d.explanations.some((e) => e.kind === 'memorandum') ? <Suspense fallback={null}><Memorandum d={d} /></Suspense> : null}
                {d.version.preamble ? <Preamble text={d.version.preamble} /> : null}
                <section aria-label={t('corpus.articles')} aria-busy={win.busy}>
                  {win.from > 0 ? (
                    <button type="button" onClick={win.earlier} disabled={win.busy}
                            className={focus ? 'mt-2 inline-flex min-h-11 items-center text-meta font-medium text-stamp'
                              : 'mt-4 w-full rounded-control border border-rule-soft px-5 py-3 text-start font-medium text-stamp hover:bg-paper'}>
                      {t('reading.earlier', { count: win.from })}
                    </button>
                  ) : null}
                  {focus && win.known && !win.outline.some((o) => o.eid === focus) && !win.articles.some((a) => a.eid === focus)
                    ? <Suspense fallback={null}><Missing eid={focus} /></Suspense> : null}
                  {win.articles.map((a, i) => (
                    <Article key={a.id} a={a} d={d} size={size} wide={wide} focused={a.eid === focus}
                             active={a.eid === active} onActive={setActive}
                             changedFrom={changedFrom(win.articles[i - 1]?.heading_path, a.heading_path)}
                             selecting={selecting} chosen={chosen.has(a.eid)} onChoose={() => toggle(a.eid)} />
                  ))}
                  {win.failed ? <Suspense fallback={null}><Failed retry={win.failed} /></Suspense>
                    : win.to < win.total ? (
                    <Further onSeen={returning ? noop : win.more} busy={win.busy} left={win.total - win.to} path={d.path} />
                  ) : null}
                  {d.version.closing ? (
                    <p {...AR} className="m-0 mt-4 whitespace-pre-line border-t border-rule-soft pt-5 font-law text-law leading-relaxed text-ink-soft">
                      {d.version.closing}
                    </p>
                  ) : null}
                </section>
              </div>
              <aside className={`flex min-w-[240px] flex-[1_1_260px] flex-col gap-7 pt-6 ${side ? 'border-t border-rule-soft' : ''}`} data-noprint>
                {d.version.source ? (
                  <section className="flex flex-col gap-3">
                    <h2 className="m-0 text-body font-semibold">{t('corpus.source')}</h2>
                    <ConsolidationSlip d={d} />
                  </section>
                ) : d.issue ? (
                  <section className="flex flex-col gap-3">
                    <h2 className="m-0 text-body font-semibold">{t('corpus.source')}</h2>
                    <SourceSlip issueNumber={issueNo(d.issue, t)} date={d.issue.date} page={d.page}
                                documentId={d.issue.document_id} pageIndex={d.page_index} />
                  </section>
                ) : null}
                {d.bill ? <Suspense fallback={null}><Bill d={d} /></Suspense> : null}
                <Suspense fallback={null}><TextLinks d={d} /></Suspense>
              </aside>
            </div>
            {/* The reading place, and a search's words lit in the law when a search led here (?hl=). */}
            <Suspense fallback={null}><KeepPlace path={d.path} articles={win.articles} returning={returning} known={win.known} reach={reach}
                                                   onBack={() => { shown.current = focus; setReturning(false); }} /></Suspense>
            {selecting ? (
              <Suspense fallback={null}>
                <ExportBar paths={win.articles.filter((a) => chosen.has(a.eid)).map((a) => a.path)}
                           onClear={() => { setSelecting(false); setChosen(new Set()); }} />
              </Suspense>
            ) : null}
          </>
        )}
      </div>
      {side ? (
        <Suspense fallback={<div className="sticky top-4 h-[calc(100vh-2rem)] rounded-card bg-sheet" />}>
          <SideColumn d={d} index={win.outline} loaded={win.articles} selecting={selecting} onSelecting={choosing} />
        </Suspense>
      ) : null}
      </div>
      <p className="m-0 text-meta text-ink-soft">{d.french ? (d.issue?.edition === 'translation_fr' ? '' : t('french.available')) : t('corpus.frenchMissing')} {t('corpus.disclaimer')}</p>
    </Shell>
  );
}

/** Where an article's parts stop being the ones before it: its divisions are printed from there (once, as the
 *  code prints them); -1 when they are the same. */
function changedFrom(before: string[] | undefined, path: string[]): number {
  if (!path.length) return -1;
  if (!before) return 0;
  const i = path.findIndex((h, k) => before[k] !== h);
  return i === -1 ? (before.length > path.length ? path.length - 1 : -1) : i;
}

/** A text's title, set in the law's face. A BO title can run on for a paragraph: three lines, the rest on request.
 *  `small`: the formal title under the everyday name. */
function Title({ text, lang, small = false }: { text: string; lang: 'ar' | 'fr'; small?: boolean }) {
  const { t } = useTranslation();
  const [whole, setWhole] = useState(false);
  const long = text.length > (small ? 120 : 170);
  const attrs = lang === 'ar' ? AR : { lang: 'fr', dir: 'ltr' as const };
  const Tag = small ? 'p' : 'h1';
  return (
    <div className="flex flex-col items-start gap-1.5">
      <Tag {...attrs} className={`m-0 max-w-[48ch] text-start ${lang === 'fr' ? 'font-law-fr' : 'font-law'} ${small ? 'text-law leading-snug text-ink-soft' : 'text-h2 font-semibold leading-[1.3] sm:text-h1'} ${long && !whole ? (small ? 'line-clamp-2' : 'line-clamp-3') : ''}`}>
        {text}
      </Tag>
      {long ? (
        <button type="button" onClick={() => setWhole((w) => !w)} aria-expanded={whole} className="min-h-11 text-meta font-medium text-stamp hover:text-stamp-deep" data-noprint>
          {whole ? t('corpus.titleShort') : t('corpus.titleWhole')}
        </button>
      ) : null}
    </div>
  );
}

/** The name people know the text by, first (R4 of the for-everyone review): «قانون الكراء» large, the law's own title
 *  under it. A text with no everyday name keeps its printed title. A French reader gets the official translation's. */
function TextTitle({ d }: { d: TextDetail }) {
  const { i18n } = useTranslation();
  const lang = i18n.language === 'fr' ? 'fr' : 'ar';
  const name = d.everyday_name?.[lang];
  if (lang === 'fr' && d.french?.title) {
    return (
      <div className="flex flex-col gap-2">
        {name ? <h1 lang="fr" className="m-0 text-h1 font-bold leading-tight">{name}</h1> : null}
        {name ? <Title text={shortName(d.french.title, 220)} lang="fr" small /> : <Title text={shortName(d.french.title, 220)} lang="fr" />}
        <p {...AR} className="m-0 max-w-[60ch] font-law text-law leading-snug text-ink-soft">{d.title}</p>
      </div>
    );
  }
  if (!name) return <Title text={d.title} lang="ar" />;
  return (
    <div className="flex flex-col gap-2">
      <h1 lang={lang} className="m-0 text-h1 font-bold leading-tight">{name}</h1>
      <Title text={d.title} lang="ar" small />
    </div>
  );
}

/** A code's parts as doors (R4): each top division's name, in plain words, opening its first article. */
function Parts({ d, outline }: { d: TextDetail; outline: OutlineEntry[] }) {
  const { t } = useTranslation();
  const parts: { full: string; name: string; eid: string }[] = [];
  for (const o of outline) {
    const top = o.heading_path.find((h) => DIVISION.test(h.trim()));
    if (top && !parts.some((x) => x.full === top)) {
      const colon = top.search(/[:：]/);
      parts.push({ full: top, name: (colon > 0 && colon < 40 ? top.slice(colon + 1) : top).replace(/[.،]$/, '').trim(), eid: o.eid });
    }
  }
  if (parts.length < 2) return null;
  return (
    <nav aria-label={t('corpus.parts')} className="flex flex-col gap-2" data-noprint>
      <h2 className="m-0 text-body font-semibold text-ink-soft">{t('corpus.parts')}</h2>
      {/* One line that scrolls sideways on a phone (P12 of the polish review): the outline holds them all a tap away. */}
      <ul className="m-0 -mx-5 flex list-none gap-2 overflow-x-auto px-5 pb-1 [scrollbar-width:none] sm:mx-0 sm:flex-wrap sm:overflow-visible sm:px-0">
        {parts.slice(0, 16).map((x) => (
          <li key={x.eid}>
            <Link {...AR} to={`${d.path}/${x.eid}`} title={x.full}
                  className="inline-flex min-h-11 items-center whitespace-nowrap rounded-card bg-paper px-3.5 py-1.5 text-body leading-snug text-ink no-underline hover:bg-wash hover:text-stamp sm:whitespace-normal">
              {x.name}
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}

const noop = () => {};

/** The end of the loaded articles: more are asked for as it nears the screen; a link for a page without scripts, a
 *  finger's 44 px tall by its own padding (RD21: it was 20), which moves nothing in the line. */
function Further({ onSeen, busy, left, path }: { onSeen: () => void; busy: boolean; left: number; path: string }) {
  const { t } = useTranslation();
  const ref = useRef<HTMLParagraphElement>(null);
  // On scroll rather than an IntersectionObserver: a fling or a jump to the end of the page (the sources come under
  // the articles on a phone) passes the end of the articles without crossing it.
  useEffect(() => {
    let frame = 0;
    const check = () => {
      frame = 0;
      const el = ref.current;
      if (el && el.getBoundingClientRect().top < window.innerHeight + 1200) onSeen();
    };
    const soon = () => { if (!frame) frame = requestAnimationFrame(check); };
    check();
    window.addEventListener('scroll', soon, { passive: true });
    window.addEventListener('resize', soon);
    return () => {
      window.removeEventListener('scroll', soon);
      window.removeEventListener('resize', soon);
      if (frame) cancelAnimationFrame(frame);
    };
  }, [onSeen]);
  return (
    <p ref={ref} className="m-0 border-t border-rule-soft py-5 text-ink-soft">
      {busy ? t('corpus.loading') : <Link to={path} onClick={(e) => { e.preventDefault(); onSeen(); }} className="py-3 font-medium">
        {t('reading.more', { count: left })}
      </Link>}
    </p>
  );
}

const KIND_WORD: Record<string, Word> = {
  law: 'law', organic_law: 'organic_law', dahir: 'dahir', decree_law: 'decree_law', decree: 'decree', order: 'order',
  decision: 'decision', circular: 'circular', convention: 'convention', constitution: 'constitution',
};

/** What the text is, where it stands, which version this is and where it was printed, each word explained a tap
 *  away (rows 11, 12). */
function Badges({ d, follow }: { d: TextDetail; follow: boolean }) {
  const { t } = useTranslation();
  const standing = textStanding(d);
  const kind = KIND_WORD[d.type];
  const label = <>{t(`corpus.types.${d.type}`)}{d.number_as_printed ? ` ${d.number_as_printed}` : ''}</>;
  const version = d.version?.consolidation === 'as_published' ? 'as_published' : 'consolidated';
  return (
    <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-body">
      {d.issue && version === 'as_published' ? <Stamp line issue={issueNo(d.issue, t)} /> : null}
      {kind ? <Explain word={kind} className="text-ink">{label}</Explain> : <span>{label}</span>}
      {standing ? (
        <Explain word={standing === 'partly_repealed' ? 'repealed' : standing}
                 className={`inline-flex items-center gap-2 font-medium ${STANDING_TONE[standing].text}`}>
          <span aria-hidden="true" className={`size-2 rounded-full ${STANDING_TONE[standing].dot}`} />
          {t(`corpus.standing.${standing}`)}
          {standing === 'amended' ? <span className="font-normal text-ink-soft">({d.standing.changes})</span> : null}
        </Explain>
      ) : null}
      {d.version && version === 'as_published' ? (
        <Explain word={version} className={`font-medium ${version === 'as_published' ? 'text-ink-soft' : 'text-amended'}`}>
          {d.version.consolidation === 'as_published' ? t('corpus.asPublished') : t(`history.kinds.${d.version.consolidation}`)}
        </Explain>
      ) : null}
      {/* A text the site has not loaded has no articles to count: «لا مادة» read as an error (P7). */}
      {d.version ? <span className="text-ink-soft">{t('corpus.results', { count: d.total_articles })}</span> : null}
      {follow ? <span className="ms-auto"><Suspense fallback={null}><FollowButton path={d.path} /></Suspense></span> : null}
    </div>
  );
}

/** An article's address, on top (HM13 of the hard-moment review): «مدونة الأسرة · المادة 49» with the
 *  source chip that says a consolidation is unofficial, and the text's whole head one tap away. A shared link to art. 49
 *  put the code's title, facts, parts and links first, the article under the fold. */
function CompactHead({ d, label, pad, onOpen }: { d: TextDetail; label?: string; pad: string; onOpen: () => void }) {
  const { t, i18n } = useTranslation();
  // The article's own standing is said on it (Place.tsx's line): the text's here read «عُدّل بعد صدوره» over «نافذة».
  return (
    <header className={`flex flex-col gap-2 border-b border-rule-soft pb-3 pt-4 sm:pt-6 ${pad}`}>
      <div className="flex items-start justify-between gap-3">
        <p className="m-0 min-w-0 text-body leading-snug">
          <Link to={d.path} className="font-semibold text-ink no-underline hover:text-stamp">{textName(d, i18n.language)}</Link>
          {label ? <span className="text-ink-soft"> · {label}</span> : null}
        </p>
        <button type="button" onClick={onOpen} aria-expanded={false}
                className="inline-flex min-h-11 shrink-0 items-center gap-1 text-meta font-medium text-stamp" data-noprint>
          {t('corpus.about')}<span aria-hidden="true">⌄</span>
        </button>
      </div>
      <ConsolidatedNote d={d} compact />
    </header>
  );
}

/** Where the text was printed and who made it: in «حول هذا النص» with its versions and what the site has read (R4). */
function About({ d }: { d: TextDetail }) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const versions = d.versions.length > 1 || (d.version && d.version.consolidation !== 'as_published');
  return (
    <section className="rounded-card bg-paper">
      <button type="button" onClick={() => setOpen((o) => !o)} aria-expanded={open} aria-controls="text-about"
              className="flex min-h-12 w-full items-center justify-between gap-3 px-4 text-start text-body font-semibold" data-noprint>
        {t('corpus.about')}
        <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
             strokeLinecap="round" className={`shrink-0 text-stamp transition-transform motion-reduce:transition-none ${open ? 'rotate-180' : ''}`}>
          <path d="m6 9 6 6 6-6" />
        </svg>
      </button>
      <div id="text-about" className={`${open ? 'flex' : 'hidden'} flex-col gap-5 px-4 pb-5 print:flex`}>
        <ReadTo d={d} />
        {open ? <Suspense fallback={null}><ExplainText path={d.path} /></Suspense> : null}
        <ConsolidatedNote d={d} />
        {open ? <Suspense fallback={null}><StandingLine d={d} only="last" /></Suspense> : null}
        <Facts d={d} />
        {!open ? null : versions ? <Suspense fallback={null}><Versions d={d} /></Suspense> : d.version && d.issue ? (
          <Suspense fallback={null}>
          <VersionRibbon
            start={d.version.valid_from}
            startLabel={t('corpus.issueTitle', { number: issueNo(d.issue, t) })}
            changes={d.amended_by.filter((a) => SHOWN_STATES.includes(a.state) && (a.effective_on ?? a.published_on)).map((a) => ({
              date: (a.effective_on ?? a.published_on)!,
              label: `${t(`corpus.types.${a.by.type}`)} ${a.by.number}`,
            }))}
          />
          </Suspense>
        ) : null}
        {open ? <Suspense fallback={null}><Coverage d={d} /></Suspense> : null}
      </div>
    </section>
  );
}

function Facts({ d }: { d: TextDetail }) {
  const { t, i18n } = useTranslation();
  const rows: [string, React.ReactNode][] = [];
  if (d.promulgating_dahir) rows.push([t('corpus.promulgatedByLabel'), t('corpus.dahirNumber', { number: d.promulgating_dahir })]);
  if (d.signed_on || d.signed_on_hijri)
    rows.push([t('corpus.signedOn'), <>
      {longDate(d.signed_on, i18n.language)}
      {d.signed_on && d.signed_on_hijri ? t('corpus.listSep') : null}
      {d.signed_on_hijri ? <bdi {...AR}>{d.signed_on_hijri}</bdi> : null}
    </>]);
  if (d.issue && d.page)
    rows.push([t('corpus.publishedIn'), d.page_index !== null ? (
      <Link to={`/pages/${d.issue.document_id}/${d.page_index}`} className="no-underline">
        {t('corpus.issueTitle', { number: issueNo(d.issue, t) })}{t('corpus.listSep')}{t('corpus.pageLong', { page: d.page })}
      </Link>
    ) : t('corpus.issueTitle', { number: issueNo(d.issue, t) })]);
  if (d.french?.consolidated_to)
    // Adala's French labour code (T1 of the work plan): a consolidation at its date, not the BO's translation.
    rows.push([t('french.labelConsolidated'), d.french.document_id ? (
      <Link to={`/pages/${d.french.document_id}/0`} className="no-underline">
        <bdi lang="fr" dir="ltr">{t('french.consolidated', { date: longDate(d.french.consolidated_to, 'fr') })}</bdi>
      </Link>
    ) : <bdi lang="fr" dir="ltr">{t('french.consolidated', { date: longDate(d.french.consolidated_to, 'fr') })}</bdi>]);
  else if (d.french)
    rows.push([t('french.label'), (
      <Link to={`/bo/translation_fr/${d.french.issue_number}${d.french.issue_suffix ? `-${d.french.issue_suffix}` : ''}`} className="no-underline">
        <bdi lang="fr" dir="ltr">{t('french.issue', { number: d.french.issue_number, date: longDate(d.french.issue_date, 'fr') })}</bdi>
      </Link>
    )]);
  // A law's authority is Parliament; its dahir (above) says who promulgated it and who countersigned.
  if (d.authority && !['law', 'organic_law'].includes(d.type)) rows.push([t('corpus.authority'), d.authority]);
  if (!rows.length) return null;
  return (
    <dl className="m-0 grid max-w-3xl gap-x-8 gap-y-2 text-body sm:grid-cols-[auto_1fr]">
      {rows.map(([k, v]) => (
        <div key={k} className="contents">
          <dt className="text-ink-soft">{k}</dt>
          <dd className="m-0">{v}</dd>
        </div>
      ))}
    </dl>
  );
}

function Preamble({ text }: { text: string }) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const lines = paragraphs(text);
  return (
    <section className="mt-6 border-y border-rule-soft py-4">
      <button type="button" onClick={() => setOpen((o) => !o)} aria-expanded={open}
              className="flex w-full items-center justify-between gap-4 text-start text-body font-semibold">
        <span>{t('corpus.preamble')} <span className="font-normal text-ink-soft">({lines.length})</span></span>
        <span className="text-meta font-normal text-stamp">{open ? t('corpus.hidePreamble') : t('corpus.showPreamble')}</span>
      </button>
      {open ? (
        <ul {...AR} className="m-0 mt-4 flex list-none flex-col gap-2 p-0 font-law text-law leading-relaxed">
          {lines.map((l, i) => <li key={i}>{l}</li>)}
        </ul>
      ) : null}
    </section>
  );
}

/** The parts above an article where they begin: the outer ones in a line, the nearest set between rules. */
function Division({ path, from }: { path: string[]; from: number }) {
  const outer = path.slice(from, -1);
  return (
    <div {...AR} className="flex flex-col items-center gap-1.5 pb-2 pt-10 text-center">
      {outer.length ? <p className="m-0 text-meta text-ink-soft">{outer.join('، ')}</p> : null}
      <div className="flex w-full items-center gap-4">
        <span aria-hidden="true" className="h-px flex-1 bg-rule" />
        <h2 className="m-0 max-w-[36ch] font-law text-h2 font-semibold leading-snug">{path.at(-1)}</h2>
        <span aria-hidden="true" className="h-px flex-1 bg-rule" />
      </div>
    </div>
  );
}

function Article({ a, d, size, wide, changedFrom, selecting, chosen, onChoose, focused = false, active, onActive }: {
  a: ArticleItem;
  /** In focus: its row of actions stands under it (N7). */
  active: boolean;
  onActive: (eid: string) => void;
  /** The article the address names: a search result's label lands on its number (U7). */
  focused?: boolean;
  d: TextDetail;
  size: TextSize;
  wide: boolean;
  /** Where its parts begin to differ from the article before; -1 when they do not. */
  changedFrom: number;
  selecting: boolean;
  chosen: boolean;
  onChoose: () => void;
}) {
  const { t, i18n } = useTranslation();
  // «⋯»: the article's other tools, opened by its button or its number (P13 of the polish review: no second row of
  // tools out by itself on a desk any more).
  const [more, setMore] = useState(false);
  const opener = useRef<HTMLButtonElement>(null);
  // A French reader gets the official translation first, the Arabic (which alone is the law) under it (row 15).
  const frenchFirst = i18n.language === 'fr' && Boolean(a.french);
  useEffect(() => { if (frenchFirst) void import('@/shared/design/french.css'); }, [frenchFirst]);
  const label = articleName(frenchFirst ? a.french!.label : a.label, t);
  const [word, number] = splitLabel(label);
  const Heading = a.heading_path.length ? 'h3' : 'h2';
  const standing = articleStanding(a, d);
  const documentId = a.document_id ?? d.issue?.document_id ?? null;
  const consolidated = d.version?.consolidation !== 'as_published';
  const bill = d.version?.consolidation === 'bill';
  // The page opens lit on this article (U14 of the Moroccan-design review).
  const page = a.page && documentId !== null && a.page_index !== null ? `/pages/${documentId}/${a.page_index}?a=${encodeURIComponent(a.label)}` : null;
  // The phone's tool sheet still names where the words come from, with the page.
  const stamp = bill ? <Suspense fallback={null}><BillStamp page={a.page} to={page} /></Suspense>
    : <Stamp issue={d.issue ? issueNo(d.issue, t) : null} page={a.page} consolidated={consolidated} translated={d.version?.consolidation === 'translation'} issued={d.version?.as_issued} to={page} />;
  const tools = t('article.tools', { label: articleName(a.label, t) });
  const close = () => { setMore(false); opener.current?.focus(); };
  return (
    <>
      {changedFrom >= 0 ? <Division path={a.heading_path} from={changedFrom} /> : null}
      {/* An article as a post (R5 of the for-everyone review): its number and, across from it, the page it was printed on;
          the law's words under a violet rule, the loudest thing here (P5 of the polish review); its row of actions right
          under them (P13); then what it means in plain words, when someone explained it. */}
      {/* A tap on its words (not a link, not a selection) brings the row of actions under it. */}
      <article id={a.eid} data-selected={selecting ? String(chosen) : undefined}
               onClick={active ? undefined : (e) => {
                 if (!(e.target as HTMLElement).closest('a, button, input, label') && !window.getSelection()?.toString()) onActive(a.eid);
               }}
               className={`-mx-3 scroll-mt-28 rounded-card px-3 py-5 [content-visibility:auto] [contain-intrinsic-size:auto_360px] target:bg-target-wash sm:py-6 ${chosen ? 'bg-target-wash' : ''}`}>
        {focused ? <Suspense fallback={<div className="h-14" />}><Landing a={a} d={d} /></Suspense> : null}
        <div className="mb-3 flex flex-wrap items-center gap-2">
          {selecting ? (
            <input type="checkbox" checked={chosen} onChange={onChoose} aria-label={t('reading.selectArticle', { label: articleName(a.label, t) })}
                   className="size-5 shrink-0 accent-[var(--color-stamp)]" data-noprint />
          ) : null}
          <Heading {...(frenchFirst ? { lang: 'fr', dir: 'ltr' as const } : AR)} className="m-0 leading-none">
            {/* The number opens the article's tools: a phone's way to them, a desk's too. */}
            <button ref={opener} type="button" onClick={() => { onActive(a.eid); setMore(!more); }} aria-expanded={more}
                    aria-haspopup={wide ? undefined : 'dialog'} title={tools} data-stamp data-pill
                    {...(focused ? { 'data-vt': 'article-label', style: { viewTransitionName: 'article-label' } } : {})}
                    className="inline-flex min-h-11 items-center gap-1.5 rounded-full bg-paper px-4 py-1.5 text-start text-ink hover:bg-wash hover:text-stamp">
              {word ? <span className="text-body font-medium">{word}</span> : null}
              <span className="whitespace-nowrap text-lead font-bold leading-none">{number}</span>
            </button>
          </Heading>
          {/* «In force» and «no repeal found» are the text's, said once in its header. */}
          {standing && standing !== 'in_force' && standing !== 'none_found' ? (
            <span className={`inline-flex items-center gap-1.5 text-meta ${STANDING_TONE[standing].text}`}>
              <span aria-hidden="true" className={`size-2 rounded-full ${STANDING_TONE[standing].dot}`} />
              {t(`article.standing.${standing}`)}
            </span>
          ) : null}
          {page ? <PageMark to={page} page={a.page} consolidated={consolidated && !bill} /> : <span className="ms-auto" />}
          <button type="button" onClick={() => { onActive(a.eid); setMore(!more); }} aria-expanded={more}
                  aria-label={t('article.tools', { label: articleName(a.label, t) })} title={t('article.more')}
                  aria-haspopup={wide ? undefined : 'dialog'}
                  className="grid size-11 shrink-0 place-items-center rounded-control text-ink-soft hover:bg-paper hover:text-stamp" data-noprint>
            <MoreIcon />
          </button>
        </div>
        <div className="min-w-0 border-s-[3px] border-stamp-line ps-4 sm:ps-5">
          {frenchFirst ? (
            <>
              {a.french!.older ? <p lang="fr" className="m-0 mb-3 text-meta font-medium text-amended">{t('french.older')}</p> : null}
              <LawBody text={a.french!.body} lang="fr" className={`max-w-[64ch] text-start font-law-fr ${FRENCH_SIZES[size]}`} />
              <p lang="fr" className="m-0 mt-3 text-meta text-ink-soft">{d.french?.consolidated_to
                ? t('french.consolidated', { date: longDate(d.french.consolidated_to, 'fr') }) : t('french.note')}</p>
              <h4 className="m-0 mt-6 text-meta font-semibold text-ink-soft">{t('article.arabicText')}</h4>
              <p {...AR} className="m-0 mt-1 font-law text-law font-semibold">{articleName(a.label, t)}</p>
              <LawBody text={a.body} marks={a.marks} definitions={d.definitions} textPath={d.path}
                       className={`mt-2 max-w-[64ch] font-law ${LAW_SIZES[size]}`} />
            </>
          ) : (
            <LawBody text={a.body} marks={a.marks} definitions={d.definitions} textPath={d.path}
                     className={`max-w-[64ch] font-law ${LAW_SIZES[size]}`} />
          )}
          <p {...AR} className="m-0 mt-3 hidden text-meta print:block">{a.citation}</p>
        </div>
        {a.proposed ? <Suspense fallback={null}><Proposed a={a} /></Suspense> : null}
        <div className="min-w-0">
          {(!frenchFirst && a.french) || a.diff || a.changes.length || a.applied_by?.length || a.cited_by?.length || a.known_as ? (
            <Suspense fallback={<div className="mt-1 h-11" />}><Extras a={a} d={d} frenchFirst={frenchFirst} /></Suspense>
          ) : null}
          {d.constitution && a.eid ? <Suspense fallback={null}><Lineage path={a.path} /></Suspense> : null}
          {active ? (
            <div className="mt-2">
              <Suspense fallback={<RowSpace path={a.path} />}>
                <ArticleRow a={a} d={d} frenchFirst={frenchFirst} wide={wide} more={more} />
              </Suspense>
            </div>
          ) : null}
          <Suspense fallback={null}><ExplainArticle textPath={d.path} eid={a.eid} path={a.path} /></Suspense>
        </div>
      </article>
      {!wide && more ? <Suspense fallback={null}><ToolSheet a={a} d={d} frenchFirst={frenchFirst} stamp={stamp} label={tools} onClose={close} /></Suspense> : null}
    </>
  );
}

/** Where the article was printed, at the end of its row (P7 of the polish review): a page and «الصفحة 14», never the
 *  abbreviation «ص.»; amber for a text assembled from its amendments. The whole sentence is its name for the ear. */
function PageMark({ to, page, consolidated }: { to: string; page: number | null; consolidated: boolean }) {
  const { t } = useTranslation();
  const said = consolidated ? t('article.pageConsolidated', { page }) : t('article.pageOfficial', { page });
  return (
    <Link to={to} title={said} aria-label={said}
          className={`ms-auto inline-flex h-11 items-center gap-1.5 px-2 text-meta no-underline hover:text-stamp ${consolidated ? 'text-amended' : 'text-ink-soft'}`}>
      <PageIcon />{consolidated ? t('article.pageShort', { page }) : t('corpus.pageAsPrinted', { page })}
    </Link>
  );
}

/** The row's place while its code arrives: its height, and the way to the discussion (the count comes with it). */
function RowSpace({ path }: { path: string }) {
  const { t } = useTranslation();
  return (
    <div className="flex h-11 items-center" data-noprint>
      <Link to={`/discussion${path}`} className="inline-flex h-11 items-center gap-2 rounded-control px-3 text-body text-ink no-underline hover:bg-paper hover:text-talk">
        <TalkIcon />{t('article.ask')}
      </Link>
    </div>
  );
}

const ICON = { width: 19, height: 19, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 1.8,
               strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const, 'aria-hidden': true };
const MoreIcon = () => <svg {...ICON}><circle cx="5" cy="12" r="1.3" /><circle cx="12" cy="12" r="1.3" /><circle cx="19" cy="12" r="1.3" /></svg>;
const PageIcon = () => <svg {...ICON} width={16} height={16}><path d="M6 3h9l4 4v14H6z" /><path d="M15 3v4h4M9 12h6M9 16h6" /></svg>;
const TalkIcon = () => <svg {...ICON}><path d="M4 5h16v11H9l-5 4z" /></svg>;


function NotInCorpus({ d }: { d: TextDetail }) {
  const { t } = useTranslation();
  return (
    <div className="flex flex-col gap-5">
      <div className="flex max-w-[60ch] flex-col items-start gap-3 rounded-control bg-wash px-5 py-4">
        <p className="m-0 text-body">{t('corpus.notInCorpus')}</p>
        {d.official ? (
          <a href={encodeURI(d.official)} target="_blank" rel="noreferrer"
             className="inline-flex min-h-11 flex-col justify-center rounded-control bg-stamp px-5 py-2 font-semibold text-on-stamp no-underline hover:bg-stamp-deep hover:text-on-stamp">
            {t('search.readOnAdala')}
            <span className="text-meta font-normal opacity-90">{t('search.adalaWho')}</span>
          </a>
        ) : null}
      </div>
      <aside className="flex max-w-xl flex-col gap-5"><Suspense fallback={null}><TextLinks d={d} /></Suspense></aside>
    </div>
  );
}

function Chevron() {
  return (
    <svg aria-hidden="true" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
         strokeLinecap="round" className="rtl:rotate-0 ltr:rotate-180"><path d="M15 6l-6 6 6 6" /></svg>
  );
}

function Shell({ children }: { children: React.ReactNode }) {
  return <main className="mx-auto flex w-full max-w-6xl flex-col gap-5 px-4 pb-10 pt-0 sm:px-6 sm:pt-8">{children}</main>;
}
