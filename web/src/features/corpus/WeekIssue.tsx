import '@/shared/locales/pages';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { useIssue, type IssueSummary } from './corpus.api';
import { AR, issueNo, issueDate } from './format';
import { textName } from './names';
import { LinesSkeleton } from '@/shared/components/ui';

/** An issue headed the way the BO heads its own pages (the review of 18 Oct 2026): its number large, its date
 *  beside it; then its texts that make rules (the general section), the others counted. `limit` shows the first
 *  ones (the home, where the page's sheet is not drawn). */
export function WeekIssue({ issue, limit }: { issue: IssueSummary; limit?: number }) {
  const { t, i18n } = useTranslation();
  const d = useIssue(issue.edition, issue.key).data;
  const general = d?.texts.filter((x) => x.section === 'general') ?? [];
  const special = (d?.texts.length ?? 0) - general.length;
  const shown = limit ? general.slice(0, limit) : general;
  const path = `/bo/${issue.edition}/${issue.key}`;
  return (
    <section className={`flex flex-col gap-3 ${limit ? '' : 'rounded-control bg-sheet px-5 pb-4 pt-6 sm:px-10'}`}>
      <Masthead issue={issue} big rule={!limit} />
      {d ? (
        <ul className="m-0 list-none p-0">
          {shown.map((x) => limit ? (
            // The home: a headline each, by its name (P15 of the polish review: the rubric and the title said it twice).
            <li key={x.id} className="border-t border-rule-soft first:border-t-0">
              <Link to={x.path} lang={i18n.language === 'fr' && !x.name?.fr ? 'ar' : undefined}
                    className="flex min-h-12 items-center py-2 text-body font-medium leading-snug text-ink no-underline hover:text-stamp">
                {textName(x, i18n.language, 90)}
              </Link>
            </li>
          ) : (
            <li key={x.id} className="border-t border-rule-soft py-3 first:border-t-0 first:pt-1">
              <span {...AR} className="block text-meta font-medium text-stamp">{x.rubric || t(`corpus.types.${x.type}`)}</span>
              <Link {...AR} to={x.path} className="font-law text-law leading-snug text-ink no-underline hover:text-stamp">{x.title}</Link>
            </li>
          ))}
          {special ? (
            <li className="border-t border-rule-soft pt-3 text-body">
              <Link to={path} className="font-medium no-underline">{t('pages:new.special', { count: special })}</Link>
            </li>
          ) : null}
        </ul>
      ) : <LinesSkeleton />}
    </section>
  );
}

/** An issue's head alone: its number, its date, the way in. */
export function Masthead({ issue, big, rule }: { issue: IssueSummary; big?: boolean; rule?: boolean }) {
  const { t, i18n } = useTranslation();
  const Heading = big ? 'h2' : 'h3';
  return (
    <div className={`flex flex-wrap items-baseline gap-x-4 gap-y-1 ${rule ? 'border-t-[3px] border-double border-ink pt-4' : ''}`}>
      <Heading className={`m-0 font-law font-bold leading-none ${big ? 'text-h1' : 'text-h1'}`}>
        {t('corpus.issueTitleShort', { number: issueNo(issue, t) })}
      </Heading>
      <span className="text-body text-ink-soft">{issueDate(issue.date, issue.hijri_date, i18n.language)}</span>
      <Link to={`/bo/${issue.edition}/${issue.key}`} className={`text-body font-medium no-underline ${big ? 'ms-auto' : 'basis-full'}`}>
        {t('corpus.openIssue')}
      </Link>
    </div>
  );
}
