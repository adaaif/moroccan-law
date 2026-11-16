import { useState } from 'react';
import { Button, Note } from '@/shared/components/ui';
import { KitPage } from '../kit/parts';
import { whatsapp, here } from '../kit/share';
import { SourceFold, SourceMark } from '../kit/tool/parts';
import { useToolState } from '../kit/tool/state';
import { fold } from '../road/fold';
import { CLAUSE_CITES, CLAUSE_WORDS, KINDS } from './rules/clauses';
import { articleLabel, useConsumerT } from './strings';

/** «واش هاد الشرط تعسفي؟» (T6 of the consumer plan): the seventeen kinds of art. 18 as plain sentences; the reader
 *  types a few words of the clause or picks the kind it looks like → what the law says of that kind and of every abusive
 *  clause. Never «your clause is abusive»: a court decides (art. 18 «تقدير المحاكم»). */
export default function ClausePage({ slug }: { slug: string }) {
  const { t } = useConsumerT();
  const [s, set] = useToolState({ k: '' });
  const [typed, setTyped] = useState('');
  const picked = Number(s.k) || 0;
  const words = fold(typed).split(/\s+/).filter((w) => w.length > 2);
  const hits = typed.trim() ? KINDS.filter((n) => (CLAUSE_WORDS[n] ?? []).some((w) => words.some((x) => fold(w).includes(x) || x.includes(fold(w))))) : [];
  const shown = typed.trim() && hits.length ? hits : KINDS;
  const art18 = '/ma/loi/31-08/art_18';
  return (
    <KitPage slug={slug} title={t('clause.title')} lead={t('clause.lead')}>
      <section className="flex flex-col gap-3 rounded-card bg-sheet px-5 py-5 sm:px-7">
        <label className="flex flex-col gap-1.5 text-body font-semibold">{t('clause.typeAsk')}
          <input type="search" value={typed} onChange={(e) => setTyped(e.target.value)} placeholder={t('clause.placeholder')}
                 className="h-12 w-full rounded-control border border-field bg-sheet px-3 text-body font-normal" />
        </label>
        {typed.trim() ? <p className="m-0 text-meta text-ink-soft">{hits.length ? t('clause.found', { count: hits.length }) : t('clause.noneFound')}</p> : null}
      </section>
      <ol className="m-0 flex list-none flex-col gap-2 p-0">
        {shown.map((n) => {
          const open = picked === n;
          return (
            <li key={n} className={`rounded-card bg-sheet transition-shadow duration-200 ${open ? 'ring-2 ring-[var(--t)]' : ''}`}>
              <button type="button" aria-expanded={open} onClick={() => set({ k: open ? '' : String(n) })}
                      className="flex min-h-14 w-full items-start gap-3 px-5 py-3 text-start sm:px-7">
                <span className="mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-full bg-wash text-meta font-bold text-stamp tabular-nums">{n}</span>
                <span className="text-body font-medium">{t(`clause.kinds.${n}`)}</span>
              </button>
              {open ? (
                <div className="flex flex-col gap-2 px-5 pb-4 sm:px-7">
                  <p className="m-0 text-body">{t('clause.ifSo')}</p>
                  <span className="flex flex-wrap gap-1.5"><SourceMark path={art18} label={articleLabel(art18)} /><SourceMark path="/ma/loi/31-08/art_19" label={articleLabel('/ma/loi/31-08/art_19')} /></span>
                </div>
              ) : null}
            </li>
          );
        })}
      </ol>
      <section className="flex flex-col gap-3 rounded-card bg-sheet px-5 py-5 sm:px-7">
        <h2 className="m-0 text-lead font-semibold">{t('clause.allTitle')}</h2>
        <ul className="m-0 flex flex-col gap-1.5 ps-5">
          {['void', 'burden', 'public', 'court', 'association'].map((k) => <li key={k} className="text-body">{t(`clause.all.${k}`)}</li>)}
        </ul>
        <Note tone="law" quiet><p className="m-0 text-meta">{t('clause.notYours')}</p></Note>
        <SourceFold paths={[...CLAUSE_CITES, '/ma/loi/31-08/art_162']} label={articleLabel} />
        <div className="flex flex-wrap gap-2">
          <Button onClick={() => whatsapp([t('clause.message'), picked ? t(`clause.kinds.${picked}`) : '', t('clause.all.void'), here()].filter(Boolean).join('\n'))}>{t('share')}</Button>
          <Button to={`/topics/${slug}/journeys/clause`}>{t('clause.toJourney')}</Button>
        </div>
      </section>
    </KitPage>
  );
}
