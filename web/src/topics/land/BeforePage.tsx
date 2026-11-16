import { useState } from 'react';
import { LoadError } from '@/features/corpus/NotFound';
import { Button, Page, PageSkeleton } from '@/shared/components/ui';
import { pick, useKitItem, type Checklist } from '../kit/api';
import { Cites, KitPage } from '../kit/parts';
import { whatsapp, here } from '../kit/share';
import { useLandT } from './strings';

/** «قبل ما تشري» (the land review, M13): the check before buying land, drawn as the paper the land registry
 *  issues: a sheet under a double rule in the topic's colour, a line a condition, each with its article; a line ticked
 *  turns green, the ones left are said in red at the foot with what their articles require. The ticks are the
 *  checklist's own (`checklists/before-buying`), kept on the phone only, so the list and the sheet agree. The paper
 *  stays light in both themes, as a paper does. */
export default function BeforePage({ slug }: { slug: string }) {
  const { t, i18n } = useLandT();
  const lang = i18n.language === 'fr' ? 'fr' : 'ar';
  const q = useKitItem<Checklist>(slug, 'checklists', 'before-buying');
  const store = `law.papers.${slug}.before-buying`;
  const [ticks, setTicks] = useState<number[]>(() => {
    try { return JSON.parse(localStorage.getItem(store) ?? '[]') as number[]; } catch { return []; }
  });
  const save = (next: number[]) => {
    setTicks(next);
    try { localStorage.setItem(store, JSON.stringify(next)); } catch { /* kept for this visit only */ }
  };
  if (q.isLoading) return <Page width="reading"><PageSkeleton kind="text" /></Page>;
  const c = q.data;
  if (!c) return <Page width="reading"><LoadError error={q.error} retry={() => void q.refetch()} /></Page>;
  const missed = c.items.map((it, i) => ({ it, i })).filter(({ i }) => !ticks.includes(i));
  const message = [t('before.message'), ...c.items.map((it, i) => `${ticks.includes(i) ? '☑' : '☐'} ${pick(it.label, lang)}`), here()].join('\n');
  return (
    <KitPage slug={slug} item={c} title={t('before.title')} lead={t('before.lead')}>
      <section className="flex flex-col px-4 pb-4 pt-3 sm:px-6" style={PAPER}>
        <div className="flex flex-wrap items-baseline justify-between gap-2 border-b-2 pb-2" style={{ borderColor: '#1E1B2C' }}>
          <h2 lang={lang} className="m-0 text-lead font-bold">{t('before.head')}</h2>
          <span className="text-meta" style={{ color: '#5D586E' }} aria-live="polite">{t('before.count', { done: ticks.length, total: c.items.length })}</span>
        </div>
        <ul className="m-0 flex list-none flex-col p-0">
          {c.items.map((it, i) => {
            const on = ticks.includes(i);
            return (
              <li key={i} className="border-t first:border-t-0" style={{ borderColor: '#E4E0DA' }}>
                <label className="grid min-h-14 cursor-pointer items-start gap-x-3 py-3" style={{ gridTemplateColumns: '28px 1fr' }}>
                  <input type="checkbox" checked={on} onChange={() => save(on ? ticks.filter((x) => x !== i) : [...ticks, i])}
                         className="mt-1 size-5 shrink-0 accent-[var(--t)]" style={{ accentColor: '#0F7B5F' }} />
                  <span className="flex min-w-0 flex-col gap-1">
                    <span lang={lang} className="text-body font-semibold leading-snug">{pick(it.label, lang)}</span>
                    {it.note ? <span lang={lang} className="text-meta" style={{ color: '#5D586E' }}>{pick(it.note, lang)}</span> : null}
                    <Cites cites={it.cites} />
                  </span>
                </label>
              </li>
            );
          })}
        </ul>
        {/* The verdict at the foot of the paper: what is left, in red, with its articles; else that all is ticked. */}
        <div aria-live="polite" className="mt-2 rounded-control px-3 py-2.5 text-body font-semibold"
             style={missed.length ? { background: '#FBEAE8', color: '#8E1D17' } : { background: '#E6F2EC', color: '#0B5E48' }}>
          {pick(missed.length ? c.verdict!.missing : c.verdict!.ok, lang)}
          {missed.length ? (
            <ul className="m-0 mt-1.5 flex list-disc flex-col gap-1 ps-5 font-normal">
              {missed.map(({ it, i }) => <li key={i} lang={lang}>{pick(it.label, lang)}</li>)}
            </ul>
          ) : null}
        </div>
      </section>
      <div className="flex flex-wrap gap-2">
        <Button onClick={() => whatsapp(message)}>{t('share')}</Button>
        {ticks.length ? <Button variant="quiet" onClick={() => save([])}>{t('before.clear')}</Button> : null}
      </div>
    </KitPage>
  );
}

/** The registry's paper: white in both themes, a double rule on top in the topic's colour, a soft shadow under it. */
const PAPER: React.CSSProperties = {
  background: '#fff', color: '#1E1B2C', borderRadius: 4, borderTop: '4px double var(--t)',
  boxShadow: '0 1px 0 #E4E0DA, 0 10px 24px -18px rgba(30,27,44,.5)',
};
