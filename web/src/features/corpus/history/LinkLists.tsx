import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { SHOWN_STATES, type ArticleItem, type LinkFrom, type TextDetail } from '../corpus.api';
import { AR, longDate } from '../format';
import { Stamp } from '../article/Stamp';
import { StateChip, TextLink } from './Links';
import { issueLabel, textName } from './linkWords';
import '@/shared/locales/pages';

function FromList({ title, rows, count, articles }: { title: string; rows: LinkFrom[]; count?: number; articles?: boolean }) {
  const { t } = useTranslation();
  if (!rows.length) return null;
  return (
    <section className="flex flex-col gap-2">
      <h2 className="m-0 text-body font-semibold">{title} <span className="font-normal text-ink-soft">({count ?? rows.length})</span></h2>
      <ul className="m-0 flex list-none flex-col p-0">
        {rows.map((r, i) => (
          <li key={i} className="border-t border-rule-soft py-2.5 first:border-t-0 first:pt-0">
            {r.from.path ? <Link {...AR} to={r.from.path} className="block font-law text-law leading-snug no-underline">{r.from.title || textName(r.from, t)}</Link>
              : <span {...AR} className="block font-law text-law leading-snug">{textName(r.from, t)}</span>}
            {articles && r.articles.length ? (
              <p className="m-0 mt-1 text-meta text-ink-soft">{t('links.itsArticles', { list: r.articles.map((n) => (n === 'preamble' ? t('corpus.preamble') : n.replace(/^art_/, ''))).join(t('corpus.listSep')) })}</p>
            ) : null}
          </li>
        ))}
      </ul>
    </section>
  );
}

/** The text's links, beside its articles: what changed it and what it changes, what applies it, what cites it,
 *  where a repealed text leads. */
export function TextLinks({ d }: { d: TextDetail }) {
  const { t, i18n } = useTranslation();
  const amendedBy = d.amended_by ?? [];
  return (
    <>
      {amendedBy.length ? (
        <section className="flex flex-col gap-2">
          <h2 className="m-0 text-body font-semibold">{t('corpus.amendedBy')} <span className="font-normal text-ink-soft">({amendedBy.length})</span></h2>
          <ul className="m-0 flex list-none flex-col p-0">
            {amendedBy.map((a, i) => (
              <li key={i} className="flex flex-col gap-1.5 border-t border-rule-soft py-3 first:border-t-0 first:pt-0">
                {a.by.path ? <Link {...AR} to={a.by.path} className="block font-law text-law leading-snug no-underline">{a.by.title || textName(a.by, t)}</Link>
                  : <span {...AR} className="font-law text-law">{textName(a.by, t)}</span>}
                <div className="flex flex-wrap items-center gap-1.5 text-meta">
                  {a.issue.number ? <Stamp line issue={issueLabel(a.issue.number, a.issue.bis, t)} page={a.issue.page} /> : null}
                  <StateChip state={a.state} />
                  {a.held_back && a.state !== 'conflict' && a.state !== 'unclear'
                    ? <span className="rounded-full bg-amended-wash px-1.5 py-0.5 text-meta text-repealed">{t('links.heldBack', { count: a.held_back })}</span> : null}
                  {a.whole ? <span className="rounded-full bg-amended-wash px-2 py-0.5 text-amended">{t(`links.verbs.${a.verbs.includes('repealed') ? 'repealed' : 'whole'}`)}</span> : null}
                  {a.articles.slice(0, 12).map((n) => <span key={n} className="rounded-full bg-amended-wash px-2 py-0.5 tabular-nums text-amended">{t('links.article', { number: n })}</span>)}
                  {a.articles.length > 12 ? <span className="text-ink-soft">+{a.articles.length - 12}</span> : null}
                </div>
                {a.effective_on && a.effective_on !== a.published_on
                  ? <p className="m-0 text-meta text-ink-soft">{t('links.takesEffect', { date: longDate(a.effective_on, i18n.language) })}</p>
                  : a.rule === 'condition' ? <p className="m-0 text-meta text-amended">{t('links.onCondition')}</p> : null}
              </li>
            ))}
          </ul>
        </section>
      ) : null}
      {d.amends?.length ? (
        <section className="flex flex-col gap-2">
          <h2 className="m-0 text-body font-semibold">{t('corpus.amends')} <span className="font-normal text-ink-soft">({d.amends.length})</span></h2>
          <ul className="m-0 flex list-none flex-col p-0">
            {d.amends.map((a, i) => (
              <li key={i} className="flex flex-col gap-1.5 border-t border-rule-soft py-3 first:border-t-0 first:pt-0">
                <TextLink x={a.target} title />
                <ul className="m-0 flex list-none flex-wrap gap-1.5 p-0 text-meta">
                  {a.changes.slice(0, 16).map((c, k) => (
                    <li key={k} className={`rounded-full px-2 py-0.5 ${SHOWN_STATES.includes(c.state) ? 'bg-amended-wash text-amended' : 'bg-chip text-ink-soft line-through decoration-rule'}`}
                        title={t(`links.states.${c.state || 'read'}`)}>
                      {t(`pages:history.verbs.${c.verb}`)}{c.number ? <> · <span className="tabular-nums">{c.number}</span></> : null}
                    </li>
                  ))}
                  {a.changes.length > 16 ? <li className="text-ink-soft">+{a.changes.length - 16}</li> : null}
                </ul>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
      <FromList title={t('links.redirectedBy')} rows={d.redirected_by ?? []} />
      <FromList title={t('links.keptBy')} rows={d.kept_by ?? []} />
      <FromList title={t('links.appliedBy')} rows={d.applied_by ?? []} articles />
      <FromList title={t('links.correctedBy')} rows={d.corrected_by ?? []} />
      <FromList title={t('links.ruledOnBy')} rows={d.ruled_on_by ?? []} />
      <FromList title={t('links.citedBy')} rows={d.cited_by ?? []} count={d.cited_by_count} articles />
      {d.cites?.length ? (
        <section className="flex flex-col gap-2">
          <h2 className="m-0 text-body font-semibold">{t('corpus.cites')} <span className="font-normal text-ink-soft">({d.cites.length})</span></h2>
          <ul className="m-0 flex list-none flex-col gap-1.5 p-0 text-body">
            {d.cites.slice(0, 30).map((c, i) => <li key={i}><TextLink x={c.to} /></li>)}
          </ul>
        </section>
      ) : null}
    </>
  );
}

/** Under an article: the texts that apply it and those that cite it, closed until asked for. */
export function ArticleLinks({ a, show }: {
  a: ArticleItem;
  /** The list alone, opened from the article's line of words (N7 of the read-and-trusted review). */
  show?: 'applied' | 'cited';
}) {
  const { t } = useTranslation();
  const [chosen, setOpen] = useState<'applied' | 'cited' | null>(null);
  const open = show ?? chosen;
  const applied = a.applied_by ?? [];
  const cited = a.cited_by ?? [];
  if (!applied.length && !cited.length) return null;
  const rows = open === 'applied' ? applied : open === 'cited' ? cited : [];
  return (
    <div className={show ? 'mt-2 flex flex-col gap-2' : 'mt-3 flex flex-col gap-2'} data-noprint>
      <div className={show ? 'hidden' : 'flex flex-wrap gap-2'}>
        {applied.length ? (
          <button type="button" onClick={() => setOpen(open === 'applied' ? null : 'applied')} aria-expanded={open === 'applied'}
                  className={`rounded-full border px-3 py-1 text-meta font-medium ${open === 'applied' ? 'border-stamp bg-wash text-stamp' : 'border-rule text-stamp'}`}>
            {t('links.articleAppliedBy', { count: applied.length })}
          </button>
        ) : null}
        {cited.length ? (
          <button type="button" onClick={() => setOpen(open === 'cited' ? null : 'cited')} aria-expanded={open === 'cited'}
                  className={`rounded-full border px-3 py-1 text-meta font-medium ${open === 'cited' ? 'border-stamp bg-wash text-stamp' : 'border-rule text-ink-soft'}`}>
            {t('links.articleCitedBy', { count: cited.length })}
          </button>
        ) : null}
      </div>
      {rows.length ? (
        <ul className="m-0 flex list-none flex-col gap-1.5 border-s-2 border-stamp-line p-0 ps-4 text-body">
          {rows.map((r, i) => (
            <li key={i}>
              {r.from.path ? <Link {...AR} to={r.eid && r.eid !== 'preamble' ? `${r.from.path}/${r.eid}` : r.from.path} className="font-law text-law no-underline">
                {r.from.title || textName(r.from, t)}</Link> : <bdi {...AR}>{textName(r.from, t)}</bdi>}
              {r.from.status === 'repealed' ? <span className="text-meta text-repealed"> · {t('search.repealedShort')}</span> : null}
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
