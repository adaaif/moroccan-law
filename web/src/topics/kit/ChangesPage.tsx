import { Link } from 'react-router-dom';
import { longDate } from '@/features/corpus/format';
import { useTopic } from '@/features/topics/topics.api';
import { Page, PageSkeleton } from '@/shared/components/ui';
import { pick, useKitT, type ChangeLine } from './api';
import { KitPage } from './parts';

/** The stages a change goes through, said first (T14 of the work plan): what is law now, what is law but not yet in
 *  force, what is a bill in parliament, what is only announced. */
const STAGES = ['in_force', 'coming', 'bill', 'announced'] as const;

/** «شنو تبدّل وشنو جاي»: every change a topic follows, grouped by its stage, each leading to its dated record and its
 *  «تابع». */
export default function ChangesPage({ slug }: { slug: string }) {
  const { t, i18n } = useKitT();
  const lang = i18n.language;
  const topic = useTopic(slug);
  if (topic.isLoading) return <Page width="reading"><PageSkeleton kind="text" /></Page>;
  const changes: ChangeLine[] = topic.data?.module?.changes ?? [];
  return (
    <KitPage slug={slug} title={t('changes.title')} lead={t('changes.lead')}>
      {STAGES.map((stage) => {
        const here = changes.filter((c) => c.stage === stage);
        if (!here.length) return null;
        return (
          <section key={stage} className="flex flex-col gap-2 rounded-card bg-sheet px-5 py-5 sm:px-7" aria-labelledby={`stage-${stage}`}>
            <h2 id={`stage-${stage}`} className={`m-0 text-lead font-semibold ${stage === 'in_force' ? 'text-in-force' : 'text-amended'}`}>
              {t(`changes.stage.${stage}`)}
            </h2>
            <ul className="m-0 flex list-none flex-col p-0">
              {here.map((c) => (
                <li key={c.key} className="border-t border-rule first:border-t-0">
                  <Link to={`/topics/${slug}/reform/${c.key}`} className="flex min-h-14 flex-col gap-1 py-3 text-ink no-underline hover:text-stamp">
                    <span lang={lang} className="text-body font-semibold">{pick(c.title, lang)}</span>
                    <span lang={lang} className="text-meta">{pick(c.line, lang)}</span>
                    <span className="text-meta text-ink-soft">{t('reform.lastCheck', { date: longDate(c.checked_on, lang) })}</span>
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        );
      })}
    </KitPage>
  );
}
