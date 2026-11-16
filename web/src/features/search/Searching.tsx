import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { topicColour } from '@/features/topics/colour';
import { TopicIcon } from '@/features/topics/TopicIcon';
import { textName } from '@/features/corpus/names';
import { Skeleton } from '@/shared/components/ui';
import { useSuggest } from './search.api';

/** When the wait is said to take a few seconds: the search reads every text, and on the server it takes that long. */
const SLOW_MS = 2500;

// A bar that runs while the search does, its keyframes here and not in the stylesheet (at its 15 KB budget).
const KEYFRAMES = `@keyframes search-run{from{inset-inline-start:-35%}to{inset-inline-start:100%}}
@media (prefers-reduced-motion:reduce){[data-run]{animation:none!important;inset-inline-start:0!important}}`;

/** The thin bar that says the search is at work: over this page while a new question is asked, over the answers
 *  while a filter or a page changes them. */
export function Running() {
  return (
    <div aria-hidden="true" className="relative h-1 overflow-hidden rounded-full bg-rule-soft">
      <style>{KEYFRAMES}</style>
      <span data-run className="absolute inset-y-0 rounded-full bg-stamp"
            style={{ width: '35%', animation: 'search-run 1.1s ease-in-out infinite' }} />
    </div>
  );
}

/** A new question while its answers come (seconds on the server, with the meaning model): the bar, what the search is
 *  doing, what the box's suggestions already found for these words (they answer at once: «البيرمي بالنقط» is the
 *  road's points before the search has read a text), and the answers' own shape: a text's name, its line, an article's
 *  number in violet and two lines of the law. The grey cards it replaced looked like nothing at all was happening. */
export function Searching({ q }: { q: string }) {
  const { t, i18n } = useTranslation();
  const lang = i18n.language === 'fr' ? 'fr' : 'ar';
  const asked = q.trim();
  const suggest = useSuggest(asked);
  const s = suggest.data?.query === asked ? suggest.data : undefined;
  const [slow, setSlow] = useState(false);
  useEffect(() => {
    const id = window.setTimeout(() => setSlow(true), SLOW_MS);
    return () => window.clearTimeout(id);
  }, []);
  const pick = (both: { ar: string; fr: string }) => (lang === 'fr' && both.fr) || both.ar;
  const quick = s ? [
    ...s.topics.map((x) => ({ key: `p-${x.slug}`, path: x.path, label: pick(x.name), detail: t('search.topic'), topic: x.slug })),
    ...s.guides.map((x) => ({ key: `g-${x.slug}`, path: x.path, label: pick(x.title), detail: x.lead ? pick(x.lead) : t('search.guide'), topic: x.topic })),
    ...s.texts.filter((x) => x.in_corpus).map((x) => ({ key: `t-${x.path}`, path: x.path, label: textName(x, lang, 60), detail: undefined, topic: undefined })),
    ...s.words.map((x) => ({ key: `w-${x.slug}`, path: x.path, label: pick(x.term), detail: t('search.word'), topic: undefined })),
  ].slice(0, 5) : [];

  return (
    <div aria-busy="true" className="flex flex-col gap-5">
      <div className="flex flex-col gap-2.5">
        <Running />
        <p role="status" className="m-0 text-body text-ink-soft">
          {t('pages:search.waiting')}{slow ? ` ${t('pages:search.waitingSlow')}` : ''}
        </p>
      </div>
      {quick.length ? (
        <section className="flex flex-col gap-2">
          <h2 className="m-0 text-meta font-semibold text-ink-soft">{t('pages:search.waitingMaybe')}</h2>
          <ul className="m-0 list-none rounded-card bg-sheet p-0 px-5 sm:px-8">
            {quick.map((x) => (
              <li key={x.key} className="border-t border-rule first:border-t-0" style={x.topic ? topicColour(x.topic) : undefined}>
                <Link to={x.path} lang={lang} className="flex min-h-14 items-center gap-3 py-3 text-ink no-underline hover:text-stamp">
                  {x.topic ? <span className="text-[color:var(--t)]"><TopicIcon slug={x.topic} size={22} /></span> : null}
                  <span className="flex min-w-0 flex-1 flex-col">
                    <span className="text-lead font-medium leading-snug">{x.label}</span>
                    {x.detail ? <span className="text-meta text-ink-soft">{x.detail}</span> : null}
                  </span>
                  <span aria-hidden="true" className="text-ink-soft">›</span>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
      <div aria-hidden="true" className="flex flex-col gap-3">
        <Skeleton className="h-5 w-40" />
        <div className="rounded-card bg-sheet px-5 sm:px-8">
          {[0, 1, 2].map((i) => (
            <div key={i} className="flex flex-col gap-2.5 border-t border-rule py-5 first:border-t-0">
              <Skeleton className={`h-7 ${i % 2 ? 'w-1/2' : 'w-2/3'}`} />
              <Skeleton className="h-4 w-2/5" />
              <div className="mt-2 flex flex-col gap-2 border-t border-rule-soft pt-3">
                <span className="block h-5 w-24 rounded-control motion-safe:animate-pulse"
                      style={{ background: 'color-mix(in srgb, var(--color-stamp) 18%, transparent)' }} />
                <Skeleton className="h-5 w-full" />
                <Skeleton className="h-5 w-3/4" />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
