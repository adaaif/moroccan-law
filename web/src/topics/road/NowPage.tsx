import { useEffect, useState } from 'react';
import { Button } from '@/shared/components/ui';
import { pick, refPath, useKitItem, type Journey } from '../kit/api';
import { due } from '../kit/dates';
import { KitPage } from '../kit/parts';
import { Listen } from '../kit/tool/parts';
import { dayWords } from '../kit/tool/days';
import { useTopic } from '@/features/topics/topics.api';
import { KEPT, keptNumbers } from './keep';
import { useRoadT } from './strings';
import { todayIso } from '@/shared/services/today';

/** The accident journey's steps in the order an accident needs them (U1 of the road tools review): the place made
 *  safe, someone hurt, identities, the insurer; the flight and the rest stay in the journey. */
const ORDER = [0, 2, 1, 5];

function kept(): Journey | null {
  try { return JSON.parse(localStorage.getItem(KEPT) ?? 'null') as Journey | null; } catch { return null; }
}

/** «درت أكسيدة؟ شنو دير دابا» (U1, T6): the accident journey said as four big steps, one hand, in order, each
 *  ticked on the phone, read aloud on demand. The journey is kept on the phone the first time it loads, so the page
 *  opens without a network afterwards. A number to call shows only with the official page that gives it (C1 of
 *  the road-signposted review: the DGSN's 19); the step still says whom to call, as art. 94 does. */
export default function NowPage({ slug }: { slug: string }) {
  const { t, i18n } = useRoadT();
  const lang = i18n.language === 'fr' ? 'fr' : 'ar';
  const q = useKitItem<Journey>(slug, 'journeys', 'accident');
  const [done, setDone] = useState<number[]>([]);
  const [copied, setCopied] = useState<string | null>(null);
  const numbers = useTopic(slug).data?.module?.urgent?.numbers ?? keptNumbers();
  useEffect(() => { if (q.data) try { localStorage.setItem(KEPT, JSON.stringify(q.data)); } catch { /* private window */ } }, [q.data]);
  const j = q.data ?? kept();
  const today = todayIso();
  if (!j) return <KitPage slug={slug} title={t('now.title')} lead={t('now.lead')}><p className="m-0 text-body">{t('now.offline')}</p></KitPage>;
  const steps = ORDER.map((i) => ({ i, st: j.steps[i] })).filter((x) => x.st);
  const insurer = due(today, { key: '', path: '', label: '', days: 5 });
  const line = (x: (typeof steps)[number]) => pick(x.st.answer ?? x.st.title, lang) + (x.st.delay ? ` ${t('now.until', { date: dayWords(insurer, lang, false) })}` : '');
  return (
    <KitPage slug={slug} title={t('now.title')} lead={t('now.lead')}>
      {numbers?.length ? (
        <section className="flex flex-col gap-2 rounded-card bg-sign-red px-5 py-4 text-on-sign" aria-label={t('now.numbers')}>
          {numbers.map((n) => (
            <div key={n.number} className="flex flex-wrap items-center gap-3">
              {/* The number as text one can read and select (C1 of the road-signposted review); a tap may call where the phone
                  allows it, and the copy button keeps it for the phone's dialler. */}
              <a href={`tel:${n.number}`} dir="ltr" className="grid min-h-14 min-w-14 place-items-center rounded-full bg-sheet px-3 text-h2 font-bold text-sign-red no-underline hover:text-sign-red">{n.number}</a>
              <span className="text-lead font-semibold">{pick(n.name, lang)}</span>
              <button type="button" onClick={() => void navigator.clipboard?.writeText(n.number).then(() => setCopied(n.number)).catch(() => undefined)}
                      className="min-h-11 rounded-full border border-[color-mix(in_srgb,#fff_60%,transparent)] px-4 text-body">
                {copied === n.number ? t('now.copied') : t('now.copy')}
              </button>
              <a href={n.source.url} target="_blank" rel="noreferrer" className="basis-full text-meta text-on-sign underline underline-offset-2 hover:text-on-sign">
                {t('now.source', { source: pick(n.source.name, lang) })}
              </a>
            </div>
          ))}
        </section>
      ) : null}
      <div className="flex flex-wrap gap-2">
        <Listen text={steps.map((x, n) => `${n + 1}. ${line(x)}`).join(' ')} lang={lang} />
      </div>
      <ol className="m-0 flex list-none flex-col gap-3 p-0">
        {steps.map((x, n) => {
          const on = done.includes(x.i);
          return (
            <li key={x.i}>
              <button type="button" aria-pressed={on} onClick={() => setDone(on ? done.filter((d) => d !== x.i) : [...done, x.i])}
                      className={`flex w-full items-start gap-4 rounded-card px-5 py-5 text-start transition-[background-color,opacity] duration-200 motion-reduce:transition-none ${
                        on ? 'bg-sheet opacity-60' : n === 0 && !done.length ? 'bg-[color-mix(in_srgb,var(--color-repealed)_12%,var(--color-sheet))]' : 'bg-sheet'}`}>
                <span className={`grid size-11 shrink-0 place-items-center rounded-full text-lead font-bold text-sheet ${on ? 'bg-in-force' : 'bg-ink'}`}>{on ? '✓' : n + 1}</span>
                <span className="flex min-w-0 flex-col gap-1">
                  <span className="text-h3 font-bold leading-snug">{pick(x.st.title, lang)}</span>
                  <span className="text-lead leading-relaxed">{line(x)}</span>
                  <span className="text-meta text-ink-soft">{(x.st.cites ?? []).map((c) => c.label).join(' · ')}</span>
                </span>
              </button>
            </li>
          );
        })}
      </ol>
      <p className="m-0 text-body">{t('now.flight')}</p>
      <Button to={refPath(slug, 'journeys/accident')} className="self-start">{t('now.all')}</Button>
    </KitPage>
  );
}
