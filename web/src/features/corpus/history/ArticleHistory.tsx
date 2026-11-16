import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { SHOWN_STATES, type ArticleChange, type ArticleItem } from '../corpus.api';
import { StateChip } from './Links';
import { AR, longDate } from '../format';
import '@/shared/locales/pages';

/** An article's life (row 8): each change with the law that made it and the BO issue that published it, newest
 *  first, and — when this version made one — what changed, word by word. Closed until asked for. */
export function ArticleHistory({ a, beforeDate, show }: {
  a: ArticleItem;
  beforeDate: string | null;
  /** The panel alone, opened from the article's line of words (N7 of the read-and-trusted review). */
  show?: 'diff' | 'history';
}) {
  const { t } = useTranslation();
  const [history, setHistory] = useState(false);
  const [diff, setDiff] = useState(false);
  if (!a.changes.length && !a.diff) return null;
  if (show) {
    return (
      <div className="mt-2" data-noprint>
        {show === 'diff' && a.diff ? <Diff diff={a.diff} since={beforeDate} /> : null}
        {show === 'history' ? (
          <ol className="m-0 flex list-none flex-col gap-0 border-s-2 border-stamp-line p-0 ps-4">
            {[...a.changes].reverse().map((c, i) => <Change key={i} c={c} />)}
          </ol>
        ) : null}
      </div>
    );
  }
  return (
    <div className="mt-4 flex flex-col gap-3" data-noprint>
      <div className="flex flex-wrap gap-2">
        {a.diff ? (
          <button type="button" onClick={() => setDiff((o) => !o)} aria-expanded={diff}
                  className={`rounded-full border px-3 py-1 text-meta font-medium ${diff ? 'border-amended bg-amended-wash text-amended' : 'border-rule text-amended'}`}>
            {t('pages:history.whatChanged')}
          </button>
        ) : null}
        {a.changes.length ? (
          <button type="button" onClick={() => setHistory((o) => !o)} aria-expanded={history}
                  className={`rounded-full border px-3 py-1 text-meta font-medium ${history ? 'border-stamp bg-wash text-stamp' : 'border-rule text-stamp'}`}>
            {t('pages:history.articleHistory', { count: a.changes.length })}
          </button>
        ) : null}
      </div>
      {diff && a.diff ? <Diff diff={a.diff} since={beforeDate} /> : null}
      {history ? (
        <ol className="m-0 flex list-none flex-col gap-0 border-s-2 border-stamp-line p-0 ps-4">
          {[...a.changes].reverse().map((c, i) => <Change key={i} c={c} />)}
        </ol>
      ) : null}
    </div>
  );
}

function Change({ c }: { c: ArticleChange }) {
  const { t, i18n } = useTranslation();
  const law = `${t(`corpus.types.${c.by.kind}`, { defaultValue: c.by.kind })} ${c.by.number.replace(/-/g, '.')}`;
  const issue = c.issue.number
    ? t('pages:history.issue', { number: `${c.issue.number}${c.issue.bis ? ` ${t('corpus.suffix.bis')}` : ''}`, page: c.issue.page ?? '' })
    : '';
  const shown = !c.state || SHOWN_STATES.includes(c.state);
  return (
    <li className="relative py-2.5">
      <span aria-hidden="true" className={`absolute -start-[1.4rem] top-4 size-2.5 rounded-full border-2 bg-sheet ${shown ? 'border-stamp' : 'border-repealed'}`} />
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <strong className="text-body font-semibold">{longDate(c.on, i18n.language)}</strong>
        <span className={`text-body ${shown ? '' : 'text-ink-soft line-through decoration-rule'}`}>{t(`pages:history.verbs.${c.verb}`)}</span>
      </div>
      <p className="m-0 mt-1 text-meta text-ink-soft">
        {c.by_article ? <><bdi {...AR}>{c.by_article}</bdi>{t('pages:history.of')}</> : null}
        {c.by.path ? <Link to={c.by.path} className="no-underline"><bdi {...AR}>{law}</bdi></Link> : <bdi {...AR}>{law}</bdi>}
        {issue ? <>{t('corpus.listSep')}{c.issue.path ? <Link to={c.issue.path} className="no-underline">{issue}</Link> : issue}</> : null}
      </p>
      {c.effective_on && c.effective_on !== c.on ? (
        <p className="m-0 mt-1 text-meta text-ink-soft">{t('links.takesEffect', { date: longDate(c.effective_on, i18n.language) })}</p>
      ) : c.rule === 'condition' ? <p className="m-0 mt-1 text-meta text-amended">{t('links.onCondition')}</p> : null}
      <p className="m-0 mt-1.5 flex flex-wrap gap-1.5 text-meta">
        <StateChip state={c.state} />
        {c.sources.includes('sgg') ? <span className="rounded-full bg-chip px-1.5 py-0.5 text-ink-soft">{t('pages:history.sources.sgg')}</span> : null}
        {c.sources.includes('adala') ? <span className="rounded-full bg-chip px-1.5 py-0.5 text-ink-soft">{t('pages:history.sources.adala')}</span> : null}
        {c.sources.includes('dgi') ? <span className="rounded-full bg-chip px-1.5 py-0.5 text-ink-soft">{t('pages:history.sources.dgi')}</span> : null}
        {c.sources.includes('reading') ? <span className="rounded-full bg-chip px-1.5 py-0.5 text-ink-soft">{t('pages:history.sources.reading')}</span> : null}
        {c.waiting && shown ? <span className="rounded-full bg-amended-wash px-1.5 py-0.5 text-amended">{t(`links.waiting.${c.waiting}`)}</span> : null}
      </p>
    </li>
  );
}

export function Diff({ diff, since, note }: { diff: NonNullable<ArticleItem['diff']>; since: string | null; note?: string }) {
  const { t, i18n } = useTranslation();
  const added = diff.every(([op]) => op !== '=' && op !== '-');
  return (
    <div className="rounded-control border border-rule bg-paper px-4 py-3">
      <p className="m-0 mb-2 text-meta text-ink-soft">
        {note ?? (added ? t('pages:history.newArticle') : since ? t('pages:history.since', { date: longDate(since, i18n.language) }) : t('pages:history.whatChanged'))}
        {added ? null : <> <span className="ms-2 line-through decoration-repealed">{t('pages:history.gone')}</span> <span className="ms-2 rounded-full bg-wash px-1 text-stamp-deep">{t('pages:history.new')}</span></>}
      </p>
      <p {...AR} className="m-0 whitespace-pre-line font-law text-law leading-loose">
        {diff.map(([op, words], i) => op === '=' ? <span key={i}>{words} </span>
          : op === '-' ? <del key={i} className="text-repealed decoration-repealed">{words} </del>
            : <ins key={i} className="rounded bg-wash text-stamp-deep no-underline">{words} </ins>)}
      </p>
    </div>
  );
}
