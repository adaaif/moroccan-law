import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { api } from '@/shared/services/api';
import { AR } from '../format';
import '@/shared/locales/pages';

type Words = [string, string][];
type Row = { year: number; label: string; path: string; here: boolean; state: '' | 'same' | 'changed' | 'none'; diff: Words | null };
type Found = { rows: Row[]; before: { year: number; state: 'none' | 'unsure' } | null; checked: string };

/** An article of a constitution in the others (C5 of the constitution review): each year with its counterpart, oldest
 *  first, whether its words stayed or what changed from the year before. Matched by machine (meaning and words) and
 *  said so until a person checks; a pair the machine is unsure of is left unsaid. Closed until asked for. */
export function Lineage({ path }: { path: string }) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const q = useQuery({ queryKey: ['constitution-lineage', path], enabled: open,
                       queryFn: () => api<Found>(`/corpus/constitution/lineage/?path=${encodeURIComponent(path)}`) });
  return (
    <div className="mt-4 flex flex-col gap-3" data-noprint>
      <button type="button" onClick={() => setOpen((o) => !o)} aria-expanded={open}
              className={`self-start rounded-full border px-3 py-1 text-meta font-medium ${open ? 'border-stamp bg-wash text-stamp' : 'border-rule text-stamp'}`}>
        {t('pages:constitution.lineage')}
      </button>
      {open && q.data ? <Chain found={q.data} /> : null}
    </div>
  );
}

function Chain({ found }: { found: Found }) {
  const { t } = useTranslation();
  const { rows, before } = found;
  const alone = before?.state === 'unsure' ? before.year : null;
  return (
    <div className="flex flex-col gap-2">
      <ol className="m-0 flex list-none flex-col border-s-2 border-stamp-line p-0 ps-4">
        {before?.state === 'none' ? <li className="py-2 text-meta text-ink-soft">{t('pages:constitution.lineageNone', { year: before.year })}</li> : null}
        {rows.map((r, i) => <Step key={r.year} r={r} prev={rows[i - 1]?.year} />)}
      </ol>
      {alone ? <p className="m-0 text-meta text-ink-soft">{t('pages:constitution.lineageAlone', { year: alone })}</p> : null}
      {found.checked ? null : <p className="m-0 text-meta text-ink-soft">{t('pages:constitution.lineageDraft')}</p>}
    </div>
  );
}

function Step({ r, prev }: { r: Row; prev?: number }) {
  const { t } = useTranslation();
  const [diff, setDiff] = useState(false);
  if (!r.label) {
    return <li className="py-2 text-meta text-ink-soft">{t('pages:constitution.lineageNone', { year: r.year })}</li>;
  }
  return (
    <li className="relative py-2">
      <span aria-hidden="true" className={`absolute -start-[1.4rem] top-3.5 size-2.5 rounded-full border-2 ${r.here ? 'border-stamp bg-stamp' : 'border-stamp bg-sheet'}`} />
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <strong className={`text-body font-semibold ${r.here ? 'text-stamp' : ''}`}>{r.year}</strong>
        {r.here
          ? <span className="text-body"><bdi {...AR}>{r.label}</bdi>{t('corpus.listSep')}{t('pages:constitution.lineageHere')}</span>
          : <Link to={r.path} className="text-body no-underline"><bdi {...AR}>{r.label}</bdi></Link>}
        {r.state === 'same' ? <span className="text-meta text-ink-soft">{t('pages:constitution.lineageSame')}</span> : null}
        {r.diff ? (
          <button type="button" onClick={() => setDiff((o) => !o)} aria-expanded={diff}
                  className="min-h-8 text-meta font-medium text-amended underline decoration-dotted underline-offset-4">
            {t('pages:constitution.lineageChanged')}
          </button>
        ) : null}
      </div>
      {diff && r.diff ? (
        <div className="mt-2 rounded-control border border-rule bg-paper px-4 py-3">
          <p className="m-0 mb-2 text-meta text-ink-soft">{t('pages:constitution.lineageChangedFrom', { year: prev })}</p>
          <p {...AR} className="m-0 whitespace-pre-line font-law text-law leading-loose">
            {r.diff.map(([op, words], i) => op === '=' ? <span key={i}>{words} </span>
              : op === '-' ? <del key={i} className="text-repealed decoration-repealed">{words} </del>
                : <ins key={i} className="rounded bg-wash text-stamp-deep no-underline">{words} </ins>)}
          </p>
        </div>
      ) : null}
    </li>
  );
}
