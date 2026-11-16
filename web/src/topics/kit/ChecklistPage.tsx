import { useState } from 'react';
import { useParams } from 'react-router-dom';
import { LoadError } from '@/features/corpus/NotFound';
import { Button, Page, PageSkeleton } from '@/shared/components/ui';
import { pick, useKitItem, useKitT, type Checklist } from './api';
import { Cites, KitPage } from './parts';
import { whatsapp } from './share';

/** The papers (F5): the items an article names, each ticked on the reader's phone and kept there only; sent as a list
 *  to WhatsApp, or printed. */
export default function ChecklistPage({ slug }: { slug: string }) {
  const { key = '' } = useParams();
  const { t, i18n } = useKitT();
  const q = useKitItem<Checklist>(slug, 'checklists', key);
  const store = `law.papers.${slug}.${key}`;
  const [ticks, setTicks] = useState<number[]>(() => {
    try { return JSON.parse(localStorage.getItem(store) ?? '[]') as number[]; } catch { return []; }
  });
  const save = (next: number[]) => {
    setTicks(next);
    try { localStorage.setItem(store, JSON.stringify(next)); } catch { /* kept for this visit only */ }
  };
  const lang = i18n.language;
  if (q.isLoading) return <Page width="reading"><PageSkeleton kind="text" /></Page>;
  const c = q.data;
  if (!c) return <Page width="reading"><LoadError error={q.error} retry={() => void q.refetch()} /></Page>;
  const law = c.cites?.map((x) => x.label).join('، ') ?? '';
  const message = [t('checklist.message', { title: pick(c.title, lang), law }),
    ...c.items.map((it, i) => `${ticks.includes(i) ? '☑' : '☐'} ${pick(it.label, lang)}${it.when ? ` (${pick(it.when, lang)})` : ''}`)].join('\n');
  return (
    <KitPage slug={slug} item={c} title={pick(c.title, lang)} lead={pick(c.lead, lang)}>
      <Cites cites={c.cites} />
      <section className="flex flex-col gap-3 rounded-card bg-sheet px-5 py-5 sm:px-7">
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
          <p className="m-0 text-meta text-ink-soft">{t('checklist.lead')}</p>
          <p className="m-0 ms-auto text-meta font-semibold" aria-live="polite">{t('checklist.count', { done: ticks.length, total: c.items.length })}</p>
        </div>
        <ul className="m-0 flex list-none flex-col p-0">
          {c.items.map((it, i) => {
            const on = ticks.includes(i);
            return (
              <li key={i} className="border-t border-rule first:border-t-0">
                <label className="flex min-h-14 cursor-pointer items-start gap-3 py-3">
                  <input type="checkbox" checked={on} onChange={() => save(on ? ticks.filter((x) => x !== i) : [...ticks, i])}
                         className="mt-1 size-5 shrink-0 accent-[var(--t)]" />
                  <span className="flex min-w-0 flex-1 flex-col gap-1">
                    <span lang={lang} className={`text-body leading-snug ${on && !c.verdict ? 'text-ink-soft line-through' : ''}`}>{pick(it.label, lang)}</span>
                    {it.when ? <span lang={lang} className="text-meta text-amended">{t('checklist.when', { when: pick(it.when, lang) })}</span> : null}
                    {it.note ? <span lang={lang} className="text-meta text-ink-soft">{pick(it.note, lang)}</span> : null}
                    <Cites cites={it.cites} />
                  </span>
                </label>
              </li>
            );
          })}
        </ul>
      </section>
      {c.verdict ? <Verdict c={c} ticks={ticks} lang={lang} /> : null}
      <div className="flex flex-wrap gap-2">
        <Button onClick={() => whatsapp(message)}>{t('share')}</Button>
        <Button onClick={() => window.print()}>{t('print')}</Button>
        {ticks.length ? <Button variant="quiet" onClick={() => save([])}>{t('checklist.clear')}</Button> : null}
      </div>
    </KitPage>
  );
}

/** A check's verdict: every condition met, or the ones missed, each with the article that sets it. */
function Verdict({ c, ticks, lang }: { c: Checklist; ticks: number[]; lang: string }) {
  const missed = c.items.map((it, i) => ({ it, i })).filter(({ i }) => !ticks.includes(i));
  const v = c.verdict!;
  return (
    <section aria-live="polite" className={`flex flex-col gap-2 rounded-card px-5 py-4 sm:px-7 ${missed.length ? 'bg-amended-wash' : 'bg-wash'}`}>
      <p lang={lang} className="m-0 text-body font-semibold">{pick(missed.length ? v.missing : v.ok, lang)}</p>
      {missed.length ? (
        <ul className="m-0 flex list-disc flex-col gap-1 ps-5">
          {missed.map(({ it, i }) => <li key={i} lang={lang} className="text-body">{pick(it.label, lang)} <Cites cites={it.cites} /></li>)}
        </ul>
      ) : null}
    </section>
  );
}
