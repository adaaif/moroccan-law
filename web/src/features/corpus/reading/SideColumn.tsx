import { lazy, Suspense, useCallback, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDiscussionOpen } from '@/features/accounts/registration';
import { useSearchParams } from 'react-router-dom';
import type { ArticleItem, OutlineEntry, TextDetail } from '../corpus.api';
import { STANDING_TONE, textStanding } from '../article/status';
import { Stamp } from '../article/Stamp';
import { issueNo } from '../format';
import { textName } from '../names';
import { FindInText, JumpField, OutlineTree } from './Navigator';
import { More, Settings } from './ReadingTools';
import { useCurrentArticle } from './useCurrentArticle';

const FollowButton = lazy(() => import('@/features/follows/FollowButton'));
const TextTalk = lazy(() => import('@/features/discussion/TextTalk'));

/** A desk's side column, held while the law scrolls (P11 of the polish review): the text by its name with its source
 *  and «تابع», the search in it, the jump by number and the outline with the current article marked; the size, the
 *  night and the export at its foot. A third of a 1440 px screen used to stay empty once the reader scrolled. */
export function SideColumn({ d, index, loaded, selecting, onSelecting }: {
  d: TextDetail;
  index: OutlineEntry[];
  loaded: ArticleItem[];
  selecting: boolean;
  onSelecting: (on: boolean) => void;
}) {
  const { t, i18n } = useTranslation();
  const talking = useDiscussionOpen();
  const eids = useMemo(() => loaded.map((a) => a.eid), [loaded]);
  const current = useCurrentArticle(eids);
  const [params] = useSearchParams();
  const [finding, setFinding] = useState(Boolean(params.get('find')));
  const onQuery = useCallback((typed: boolean) => setFinding(typed), []);
  const standing = textStanding(d);
  const consolidated = d.version?.consolidation !== 'as_published';
  return (
    <aside data-noprint aria-label={t('reading.where')}
           className="sticky top-4 flex max-h-[calc(100vh-2rem)] flex-col gap-3 rounded-card bg-sheet p-4">
      <div className="flex flex-col gap-1.5 border-b border-rule-soft px-1 pb-3">
        <p lang={i18n.language === 'fr' && !d.name?.fr ? 'ar' : undefined} className="m-0 text-lead font-bold leading-snug">
          {textName(d, i18n.language, 70)}
        </p>
        <p className="m-0 flex flex-wrap items-center gap-x-2 gap-y-1 text-meta text-ink-soft">
          <span>{t(`corpus.types.${d.type}`)}{d.number_as_printed ? ` ${d.number_as_printed}` : ''}</span>
          <span aria-hidden="true">·</span>
          <span>{t('corpus.results', { count: d.total_articles })}</span>
          {standing ? (
            <span className={`inline-flex items-center gap-1.5 ${STANDING_TONE[standing].text}`}>
              <span aria-hidden="true" className={`size-2 rounded-full ${STANDING_TONE[standing].dot}`} />
              {t(`corpus.standing.${standing}`)}
            </span>
          ) : null}
        </p>
        <div className="flex flex-wrap items-center gap-2">
          {consolidated ? <Stamp line consolidated translated={d.version?.consolidation === 'translation'} issued={d.version?.as_issued} /> : d.issue ? <Stamp line issue={issueNo(d.issue, t)} /> : null}
          <span className="ms-auto"><Suspense fallback={null}><FollowButton path={d.path} /></Suspense></span>
        </div>
      </div>
      {finding || !talking ? null : <Suspense fallback={null}><TextTalk textPath={d.path} outline={index} /></Suspense>}
      <div className={finding ? 'flex min-h-0 flex-1 flex-col' : ''}>
        <FindInText textPath={d.path} initial={params.get('find') ?? ''} onQuery={onQuery} />
      </div>
      {finding ? null : (
        <>
          <div className="px-1"><JumpField articles={index} textPath={d.path} /></div>
          <nav data-scroll aria-label={t('reading.outline')} className="-mx-2 min-h-0 flex-1 overflow-y-auto overscroll-contain px-2">
            <h2 className="m-0 px-3 pb-1 text-meta font-semibold text-ink-soft">{t('reading.outline')}</h2>
            <OutlineTree articles={index} textPath={d.path} current={current} />
          </nav>
        </>
      )}
      <div className="flex items-center gap-1 border-t border-rule-soft pt-2">
        <Settings />
        <span className="text-meta text-ink-soft">{t('reading.settings')}</span>
        <span className="ms-auto"><More selecting={selecting} onSelecting={onSelecting} /></span>
      </div>
    </aside>
  );
}
