import type { TFunction } from 'i18next';
import { useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useSearchParams } from 'react-router-dom';
import { BlogLinks } from '@/features/blog/BlogLinks';
import { todayIso } from '@/shared/services/today';
import { reducedMotion } from '@/shared/services/motion';
import { LinesSkeleton, Page } from '@/shared/components/ui';
import { usePageTitle } from '@/shared/services/title';
import '@/shared/locales/pages';
import { longDate } from './format';
import { Find } from './library/Find';
import { span, useArchive, useNum } from './library/library.api';
import type { Held, Year } from './library/map';
import { Strata, YearMonths } from './library/Strata';
import { YearTexts } from './library/YearTexts';
import { LoadError } from './NotFound';
import './library.css';

/** /bo: every issue held since No. 1 (row 18; drawn again on 30 Oct 2026, and on 9 Nov 2026 for
 *  the every-code review). The box at the top reads any number, page, reference or day (LB2). The strata are the years' picker, the
 *  whole Bulletin on one screen (LB8). The year chosen opens on its months: calendars on a desk, Monday first, each issue
 *  stamped on its day; on a phone a row of issues a month (LB9). An issue held without a text cut from it is drawn too,
 *  «صفحاته فقط» (LB10). Read from the compact map of the issues (LB13). */
export default function IssuesPage() {
  const { t, i18n } = useTranslation();
  usePageTitle([t('issues.title')]);
  const num = useNum();
  const archive = useArchive();
  const [params] = useSearchParams();
  const a = archive.data;
  const list = a ? [...a.years.keys()].sort((x, y) => x - y) : [];
  const asked = Number(params.get('year'));
  const year = a ? (a.years.has(asked) ? asked : list[list.length - 1]) : undefined;
  const Y = year !== undefined ? a?.years.get(year) : undefined;
  const texts = params.get('view') === 'texts';
  const at = year !== undefined ? list.indexOf(year) : -1;
  const older = at > 0 ? list[at - 1] : undefined;
  const newer = at >= 0 && at < list.length - 1 ? list[at + 1] : undefined;
  // A year chosen (the strata, ‹ ›, the library) brings its months into view; the page as first opened stays at its top.
  const head = useRef<HTMLHeadingElement>(null);
  const first = useRef(true);
  useEffect(() => {
    if (!Y) return;
    if (first.current && !params.get('year')) { first.current = false; return; }
    first.current = false;
    head.current?.scrollIntoView({ behavior: reducedMotion() ? 'auto' : 'smooth', block: 'start' });
  }, [Y, params]);
  const total = a ? a.ar.length + a.fr.length : 0;
  return (
    <Page width="wide" className="lb">
      <header className="lb-head side">
        <div>
          <h1>{t('issues.title')}</h1>
          <p className="lead">{a ? t('pages:lib3.bo.lead', { count: total, n: num(total), from: a.fr[0]?.y ?? a.ar[0].y, to: list[list.length - 1] })
            : t('pages:issues.leadPlain')}</p>
        </div>
        <Find id="bo-find" examples={false} />
      </header>

      {archive.isLoading ? <LinesSkeleton lines={6} /> : archive.isError ? <LoadError error={archive.error} retry={() => void archive.refetch()} /> : null}
      {a ? <Strata archive={a} current={year} /> : null}

      {Y ? (
        <section aria-labelledby="year" className="lb-yearsec">
          <div className="lb-yearhead">
            <h2 id="year" ref={head} tabIndex={-1}>{Y.year}</h2>
            <p>{yearLine(Y, t, num)}</p>
            <nav aria-label={t('pages:issues.years')}>
              {/* The older year behind «‹», the newer ahead of «›» («‹ ›» turn by themselves; PX34). */}
              {older ? <Link to={`/bo?year=${older}${texts ? '&view=texts' : ''}`} className="lb-step">‹ {older}</Link> : null}
              {newer ? <Link to={`/bo?year=${newer}${texts ? '&view=texts' : ''}`} className="lb-step">{newer} ›</Link> : null}
            </nav>
          </div>
          {/* A year holds its laws and dahirs, not only its issues (W8 of the library-search review): two views of one year,
              each with its own address (?view=texts), so the box and a shared link open the one meant. */}
          <div className="lb-tabs" role="tablist" aria-label={String(Y.year)}>
            <Link role="tab" aria-selected={!texts} to={`/bo?year=${Y.year}`} replace>{t('pages:lib4.bo.tabIssues')}</Link>
            <Link role="tab" aria-selected={texts} to={`/bo?year=${Y.year}&view=texts`} replace>{t('pages:lib4.bo.tabTexts')}</Link>
          </div>
          {texts ? <YearTexts year={Y.year} /> : (
            <>
              <div className="lb-months">
                {months(Y).map(([month, items]) => <Month key={month} month={month} items={items} lang={i18n.language} />)}
              </div>
              <YearMonths year={Y} />
              <p className="lb-note">{t('pages:bo2.note')}{Y.fr.length ? ` ${t('pages:bo2.noteFrench')}` : ''}{Y.pagesOnly ? ` ${t('pages:lib3.bo.notePages')}` : ''}</p>
            </>
          )}
        </section>
      ) : null}
      {/* What the blog counted of the Bulletin itself: after the issues, never before them (its list often answers
          first, and the strip stood at the top until the strata threw it down: layout shift 0.42). */}
      {a ? <BlogLinks slugs={['from-no-1', 'december', 'signed-to-published', 'who-writes']} most={4} /> : null}
    </Page>
  );
}

function yearLine(Y: Year, t: TFunction, num: (n: number) => string): string {
  const held = Y.ar.filter((x) => !x.pagesOnly);
  const parts: string[] = [];
  if (Y.ar.length) parts.push(t('pages:issues.yearLine', { count: Y.ar.length, texts: t('pages:lib2.textsN', { count: Y.texts, n: num(Y.texts) }) }));
  if (Y.ar.length) parts.push(span(Y.min, Y.max));
  if (Y.pagesOnly) parts.push(t('pages:lib3.bo.pagesOnlyN', { count: Y.pagesOnly, n: num(Y.pagesOnly) }));
  if (Y.fr.length) parts.push(t('pages:lib3.strata.frenchN', { count: Y.fr.length, n: num(Y.fr.length) }));
  return held.length || Y.fr.length ? parts.join(t('corpus.listSep')) : '';
}

/** A year's issues by month, newest month first, both editions. */
function months(Y: Year): [string, Held[]][] {
  const by = new Map<string, Held[]>();
  for (const x of [...Y.ar, ...Y.fr].sort((p, q) => q.date.localeCompare(p.date))) {
    const m = x.date.slice(0, 7);
    by.set(m, [...(by.get(m) ?? []), x]);
  }
  return [...by];
}

/** A month as a calendar, Monday first: an issue on its day, its number under the day; two on one day (a «مكرر») both. */
function Month({ month, items, lang }: { month: string; items: Held[]; lang: string }) {
  const { t } = useTranslation();
  const locale = lang === 'fr' ? 'fr-MA' : 'ar-MA';
  const [y, m] = month.split('-').map(Number);
  const first = Date.UTC(y, m - 1, 1);
  const days = new Date(Date.UTC(y, m, 0)).getUTCDate();
  const lead = (new Date(first).getUTCDay() + 6) % 7;
  const byDay = new Map<number, Held[]>();
  for (const x of items) byDay.set(x.d, [...(byDay.get(x.d) ?? []), x].sort((p, q) => p.suffix.localeCompare(q.suffix)));
  const weekday = new Intl.DateTimeFormat(locale, { weekday: 'narrow', timeZone: 'UTC' });
  const today = todayIso();
  const name = new Intl.DateTimeFormat(locale, { month: 'long', timeZone: 'UTC' }).format(new Date(first));
  const iso = (d: number) => `${month}-${String(d).padStart(2, '0')}`;
  const said = (x: Held) => t('pages:bo2.cell', { date: longDate(x.date, lang), issue: x.number + (x.suffix ? ` ${t(`corpus.suffix.${x.suffix}`)}` : ''),
                                                  texts: x.pagesOnly ? t('pages:lib3.issue.pagesOnlyShort') : t('corpus.textsCount', { count: x.texts }) });
  const cls = (x: Held) => `${x.edition === 'translation_fr' ? ' fr' : ''}${x.pagesOnly ? ' z' : ''}`;
  return (
    <section className="lb-month" aria-labelledby={`m-${month}`}>
      <h3 id={`m-${month}`}>{name}<span>{t('pages:issues.issuesCount', { count: items.length })}</span></h3>
      <ol className="lb-cal">
        {Array.from({ length: 7 }, (_, i) => (
          <li key={`w${i}`} className="wd" aria-hidden="true">{weekday.format(new Date(Date.UTC(2024, 0, 1 + i)))}</li>
        ))}
        {Array.from({ length: lead }, (_, i) => <li key={`b${i}`} aria-hidden="true" />)}
        {Array.from({ length: days }, (_, i) => {
          const d = i + 1;
          const here = byDay.get(d);
          const now = iso(d) === today ? ' today' : '';
          if (!here) return <li key={d} className={`d${now}`} aria-hidden="true">{d}</li>;
          if (here.length === 1) {
            const x = here[0];
            return (
              <li key={d}>
                <Link to={`/bo/${x.edition}/${x.key}`} className={`d${now}${cls(x)}`} aria-label={said(x)} title={said(x)}>
                  <b>{d}</b><small>{x.number}</small>{x.suffix ? <small>{t(`corpus.suffix.${x.suffix}`)}</small> : null}
                </Link>
              </li>
            );
          }
          return (
            <li key={d} className={`d two${now}`}>
              <b aria-hidden="true">{d}</b>
              {/* A «مكرر» shares its number: the number once, then the word. */}
              {here.map((x, k) => (
                <Link key={x.key + x.edition} to={`/bo/${x.edition}/${x.key}`} aria-label={said(x)} title={said(x)} className={cls(x).trim() || undefined}>
                  {k && x.suffix ? t(`corpus.suffix.${x.suffix}`) : x.number}
                </Link>
              ))}
            </li>
          );
        })}
      </ol>
    </section>
  );
}
