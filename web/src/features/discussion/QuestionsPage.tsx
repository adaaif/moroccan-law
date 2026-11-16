import { useSearchParams } from 'react-router-dom';
import { PostCard } from './PostCard';
import { usePlaces, useQuestions } from './discussion.api';
import { useNoIndex } from './noindex';
import { placeName, useT } from './strings';
import { usePageTitle } from '@/shared/services/title';
import { LinesSkeleton, Page } from '@/shared/components/ui';

/** /questions: questions readers asked and nobody answered yet, oldest first; across the topics or in one. */
export default function QuestionsPage() {
  const { t, i18n } = useT();
  usePageTitle([t('questionsPage.title')]);
  const [params, setParams] = useSearchParams();
  const place = params.get('place') ?? '';
  const q = useQuestions(place);
  const names = usePlaces();
  useNoIndex();
  const first = q.data?.pages[0];
  const rows = q.data?.pages.flatMap((p) => p.questions) ?? [];
  const waiting = first?.places ?? [];
  const named = new Map((names.data?.places ?? []).map((p) => [p.path, p.name]));

  return (
    <Page width="reading" className="gap-5">
      <div className="-mx-4 flex flex-col gap-6 bg-sheet px-5 py-8 sm:mx-0 sm:rounded-card sm:px-10">
        <header className="flex flex-col gap-3">
          <h1 className="m-0 font-law text-h1 font-semibold leading-tight">{t('questionsPage.title')}</h1>
          <p className="m-0 max-w-[62ch] text-body text-ink-soft">{t('questionsPage.lede')}</p>
          {waiting.length > 1 || place ? (
            <label className="flex flex-wrap items-center gap-3 text-body">
              {t('questionsPage.filter')}
              <select value={place} onChange={(e) => setParams(e.target.value ? { place: e.target.value } : {})}
                      className="h-10 max-w-full rounded-control border border-field bg-sheet px-3 text-body">
                <option value="">{t('questionsPage.all')}</option>
                {[...new Set([place, ...waiting].filter(Boolean))].map((p) => (
                  <option key={p} value={p}>{placeName(named.get(p), i18n.language) || p}</option>
                ))}
              </select>
            </label>
          ) : null}
        </header>
        {q.isLoading ? <LinesSkeleton lines={6} /> : rows.length ? (
          <ol className="m-0 flex list-none flex-col gap-3 p-0">
            {rows.map((c) => <li key={c.id}><PostCard c={c} label={c.label} /></li>)}
          </ol>
        ) : <p className="m-0 text-body text-ink-soft">{t('questionsPage.none')}</p>}
        {q.hasNextPage ? (
          <button type="button" onClick={() => void q.fetchNextPage()} className="h-11 rounded-control border border-rule text-body text-stamp hover:bg-paper">
            {t('loadMore')}
          </button>
        ) : null}
      </div>
      <p className="m-0 text-meta text-ink-soft">{t('disclaimer')}</p>
    </Page>
  );
}
