import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useParams } from 'react-router-dom';
import { documentFileUrl, useIssue, type IssueDetail, type IssueText } from './corpus.api';
import { useArchive } from './library/library.api';
import { AR, issueDate, issueNo } from './format';
import { PageStrip } from './PageStrip';
import '@/shared/locales/pages';
import { usePageTitle } from '@/shared/services/title';
import { Page, PageSkeleton } from '@/shared/components/ui';
import { buttonClass } from '@/shared/components/buttons';
import { LoadError } from '@/features/corpus/NotFound';

const SECTIONS = ['general', 'special', 'other'] as const;
/** Before 1956 the Bulletin printed two parts, the official and the non-official (the Bulletin-from-No.-1 review). */
const OLD_SECTIONS = [['official', ['general', 'special']], ['unofficial', ['other']]] as const;
/** A long section shows its first texts and folds the rest (the special section runs to dozens of appointments and
 *  expropriations: a phone scrolled 12,000 px). */
const SHOWN = 6;

/** A cover that bears several numbers is named as it prints them, «610 — 637» (FX3 of the mended-Bulletin review); kept
 *  here, off the first load. */
function coverNo(d: IssueDetail, t: (key: string) => string): string {
  return d.last_number && d.last_number > d.number && !d.suffix ? `${d.number} — ${d.last_number}` : issueNo(d, t);
}

/** /bo/:edition/:number: one issue of the Bulletin, its pages as a strip, its texts by section and rubric. */
export default function IssuePage() {
  const { edition = '', number = '' } = useParams();
  const { t, i18n } = useTranslation();
  const issue = useIssue(edition, number);
  // The tab's name is a search result's too: «الجريدة الرسمية عدد 7465», as people search it and the server's head says
  // it (IX8 of the search-engines review).
  usePageTitle([issue.data ? t('corpus.issueTitle', { number: issueNo(issue.data, t) }) : null]);

  if (issue.isLoading) return <Shell><PageSkeleton /></Shell>;
  if (!issue.data) return <Shell><LoadError error={issue.error} retry={() => void issue.refetch()} /></Shell>;
  const d = issue.data;
  const starts = new Set(d.texts.map((x) => x.page).filter((p): p is number => p !== null));
  return (
    <Shell>
      {/* The issue headed as the Bulletin heads its own (the review of 18 Oct 2026; 26 Oct 2026): a double rule, its
          name, its number large, its date; the way back to its year and to the issues on either side. */}
      <nav aria-label={t('issues.title')} className="flex flex-wrap items-center justify-between gap-x-6 gap-y-1">
        <Link to={`/bo?year=${d.date.slice(0, 4)}`} className="inline-flex min-h-11 items-center text-body text-ink-soft no-underline hover:text-stamp">
          <span aria-hidden="true" className="me-2">‹</span>{t('pages:library.allIssues', { year: d.date.slice(0, 4) })}
        </Link>
        <Neighbours edition={d.edition} issueKey={d.key} />
      </nav>
      <header className="flex flex-wrap items-end justify-between gap-6 border-t-[3px] border-double border-ink pt-5">
        <div className="flex flex-col gap-2">
          {/* The masthead in the reader's language (PX29): «الجريدة الرسمية، Édition générale» on a French page. */}
          {d.edition === 'translation_fr' ? <span className="text-body text-ink-soft">{t('pages:issue.french')}</span>
            : i18n.language === 'fr' ? <span className="text-body text-ink-soft">Bulletin officiel, {t('corpus.editionGeneral').toLowerCase()}</span>
            : <span {...AR} className="text-body text-ink-soft">الجريدة الرسمية، {t('corpus.editionGeneral')}</span>}
          <h1 className="m-0 font-law text-display font-bold leading-none">{t('corpus.issueTitleShort', { number: coverNo(d, t) })}</h1>
          <p className="m-0 text-lead">{issueDate(d.date, d.hijri_date, i18n.language)}</p>
          {d.asked_for ? (
            <p className="m-0 max-w-[60ch] text-body text-ink-soft">
              {t('pages:issue.printedWithin', { asked: d.asked_for, cover: coverNo(d, t) })}
            </p>
          ) : null}
        </div>
        <div className="flex flex-wrap gap-2">
          <a href={documentFileUrl(d.document_id)} target="_blank" rel="noreferrer" className={buttonClass('primary')}>
            {t('corpus.openPdf')}
          </a>
          <Link to={`/bo/${d.edition}/${d.key}/quality`} className={buttonClass('secondary')}>
            {t('pages:quality.title')}
          </Link>
        </div>
      </header>

      {/* An issue kept by its pages alone (a report, a table of sworn experts) says what it holds in its own words: its
          contents table as printed, each entry opening its page (W9 of the library-search review). It opened on a grid of
          grey cells and nothing else. */}
      {!d.texts.length && d.edition !== 'translation_fr' ? (
        <section className="flex flex-col gap-2" aria-labelledby="bare">
          <p className="m-0 max-w-[64ch] text-body text-ink-soft">{t('pages:lib4.bare.said')}</p>
          {d.contents?.length ? (
            <>
              <h2 id="bare" className="m-0 mt-2 text-h3 font-semibold">{t('pages:lib4.bare.title')}</h2>
              <ol {...AR} className="m-0 list-none overflow-hidden rounded-card bg-sheet p-0">
                {d.contents.map((c, i) => {
                  const at = c.page ? d.pages.find((x) => x.printed_number === c.page) : undefined;
                  const cls = 'flex items-baseline justify-between gap-4 border-b border-rule-soft px-5 py-3 last:border-b-0';
                  if (c.kind === 'rubric') return <li key={i} className="px-5 pt-4 text-meta font-medium text-stamp">{c.text}</li>;
                  const words = <span className="min-w-0 font-law text-[1.1875rem] leading-snug">{c.text}</span>;
                  return (
                    <li key={i}>
                      {at ? <Link to={`/pages/${d.document_id}/${at.index}`} className={`${cls} text-ink no-underline hover:text-stamp`}>{words}
                        <span className="flex-none text-meta text-stamp" lang={i18n.language} dir={i18n.dir()}>{t('pages:lib4.bare.page', { page: c.page })}</span></Link>
                        : <span className={cls}>{words}</span>}
                    </li>
                  );
                })}
              </ol>
            </>
          ) : null}
        </section>
      ) : null}

      <section className="flex flex-col gap-3 rounded-control border border-rule bg-sheet p-5">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h2 className="m-0 text-body font-semibold">{t('corpus.pageStrip')}</h2>
          <span className="text-meta text-ink-soft">
            {t('corpus.pages', { count: d.page_count ?? 0 })}{t('corpus.listSep')}<bdi>{d.pages[0]?.printed_number}–{d.pages.at(-1)?.printed_number}</bdi>.{' '}
            {t('corpus.pageStripHint')}
          </span>
        </div>
        <PageStrip documentId={d.document_id} pages={d.pages} starts={starts} />
      </section>

      {/* A French issue of 1912–1925 lists the texts the Arabic edition never printed, translated (A of
          the Bulletin-from-No.-1 review); its other texts are in the Arabic issues of the same weeks. */}
      {d.edition === 'translation_fr' ? (
        <>
          <p className="m-0 max-w-[64ch] text-body text-ink-soft">{t('pages:issue.frenchNote')}</p>
          {d.texts.length ? <Section section="" title={t('pages:issue.frenchTexts')} texts={d.texts} /> : null}
        </>
      ) : (d.date < '1956' ? OLD_SECTIONS : SECTIONS.map((s) => [s, [s]] as const)).map(([section, kinds]) => {
        const texts = d.texts.filter((x) => (kinds as readonly string[]).includes(x.section || 'other'));
        return texts.length ? <Section key={section} section={section} texts={texts} /> : null;
      })}
    </Shell>
  );
}

/** A section's texts by rubric; past six, the rest behind one button that says how many. */
function Section({ section, title, texts }: { section: string; title?: string; texts: IssueText[] }) {
  const { t } = useTranslation();
  const [all, setAll] = useState(false);
  const shown = all ? texts : texts.slice(0, SHOWN);
  return (
    <section className="flex flex-col gap-3">
      <h2 className="m-0 text-h3 font-semibold">
        {title ?? t(`corpus.${section}`)} <span className="text-body font-normal text-ink-soft">({texts.length})</span>
      </h2>
      <ol className="m-0 list-none overflow-hidden rounded-card bg-sheet p-0">
        {byRubric(shown).map(([rubric, group], i) => (
          <li key={`${rubric}-${i}`} className="border-b border-rule-soft last:border-b-0">
            {rubric ? <p {...AR} className="m-0 px-5 pt-4 text-meta font-medium text-stamp sm:px-6">{rubric}</p> : null}
            <ul className="m-0 list-none p-0">
              {group.map((x) => <Entry key={x.id} text={x} />)}
            </ul>
          </li>
        ))}
      </ol>
      {texts.length > SHOWN ? (
        <button type="button" aria-expanded={all} onClick={() => setAll(!all)} className={buttonClass('secondary', 'self-start')}>
          {all ? t('pages:issue.fewer') : t('pages:issue.more', { count: texts.length - SHOWN })}
        </button>
      ) : null}
    </section>
  );
}

/** The issues just before and after this one among those the site read (the list is already kept by the library). */
function Neighbours({ edition, issueKey }: { edition: string; issueKey: string }) {
  const { t } = useTranslation();
  // The issues held, oldest first, from the compact map (LB13 of the every-code review): an issue held without texts
  // is a neighbour too (LB10).
  const archive = useArchive().data;
  const list = archive ? (edition === 'translation_fr' ? archive.fr : archive.ar) : [];
  const i = list.findIndex((x) => x.key === issueKey);
  if (i < 0) return null;
  const older = list[i - 1];
  const newer = list[i + 1];
  const link = (x: (typeof list)[number] | undefined, label: string, side: 'older' | 'newer') => (x ? (
    <Link to={`/bo/${x.edition}/${x.key}`} rel={side === 'older' ? 'prev' : 'next'}
          className="inline-flex min-h-11 items-center gap-1.5 rounded-full border border-rule bg-sheet px-4 text-body text-ink no-underline hover:border-stamp hover:text-stamp">
      {side === 'older' ? <span aria-hidden="true">‹</span> : null}
      <span>{label} {issueNo(x, t)}</span>
      {side === 'newer' ? <span aria-hidden="true">›</span> : null}
    </Link>
  ) : null);
  return (
    <span className="flex gap-2">
      {link(older, t('pages:issue.older'), 'older')}
      {link(newer, t('pages:issue.newer'), 'newer')}
    </span>
  );
}

function Entry({ text: x }: { text: IssueText }) {
  const { t } = useTranslation();
  return (
    <li className="flex gap-4 px-5 py-3.5 sm:gap-6 sm:px-6">
      <div className="flex min-w-0 flex-1 flex-col gap-1">
        <Link {...AR} to={x.path} className="font-law text-law leading-snug text-ink no-underline hover:text-stamp">
          {x.title}
        </Link>
        <span className="flex flex-wrap gap-x-4 gap-y-1 text-meta text-ink-soft">
          <span>{t(`corpus.types.${x.type}`)}{x.number_as_printed ? ` ${x.number_as_printed}` : ''}</span>
          {x.articles ? <span>{t('corpus.articlesCount', { count: x.articles })}</span> : null}
          {x.amends ? <span className="text-amended">{t('corpus.amendsCount', { count: x.amends })}</span> : null}
          {x.page ? <span className="sm:hidden">{t('corpus.page', { page: x.page })}</span> : null}
        </span>
      </div>
      {x.page ? <span className="hidden flex-none pt-1 text-meta text-ink-soft sm:block">{t('corpus.page', { page: x.page })}</span> : null}
    </li>
  );
}

function byRubric(texts: IssueText[]): [string, IssueText[]][] {
  const groups: [string, IssueText[]][] = [];
  for (const x of texts) {
    const last = groups.at(-1);
    if (last && last[0] === x.rubric) last[1].push(x);
    else groups.push([x.rubric, [x]]);
  }
  return groups;
}

function Shell({ children }: { children: React.ReactNode }) {
  return <Page width="wide" className="gap-8">{children}</Page>;
}
