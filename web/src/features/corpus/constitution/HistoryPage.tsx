import { useQuery } from '@tanstack/react-query';
import { useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { api } from '@/shared/services/api';
import { Page, PageSkeleton } from '@/shared/components/ui';
import { usePageTitle } from '@/shared/services/title';
import { BlogLinks } from '@/features/blog/BlogLinks';
import { Stamp } from '../article/Stamp';
import type { TextDetail } from '../corpus.api';
import { longDate } from '../format';
import { Story } from './Story';
import '@/shared/locales/pages';

type Chapter = NonNullable<TextDetail['constitution']> & { path: string; current: boolean };

/** /constitution/history (C4 of the constitution review): the six constitutions, each with how it was adopted and
 *  printed and its chapter, every claim linked to its article. A draft until a person has read it against the texts:
 *  kept out of search engines, no longer said on the page (15 Nov 2026: «عن «قانون»» says once what no specialist has
 *  reviewed). */
export default function HistoryPage() {
  const { t, i18n } = useTranslation();
  const lang = i18n.language === 'fr' ? 'fr' : 'ar';
  usePageTitle([t('pages:constitution.historyTitle')]);
  const q = useQuery({ queryKey: ['constitution-history'], queryFn: () => api<{ checked: string; chapters: Chapter[] }>('/corpus/constitution/history/') });
  const draft = q.data && !q.data.checked;
  useEffect(() => {
    if (!draft) return;
    const meta = Object.assign(document.createElement('meta'), { name: 'robots', content: 'noindex' });
    document.head.appendChild(meta);
    return () => meta.remove();
  }, [draft]);
  if (!q.data) return <Page width="reading"><PageSkeleton /></Page>;
  const when = (iso: string) => longDate(iso, i18n.language);
  return (
    <Page width="reading" className="gap-6">
      <header className="flex flex-col gap-2">
        <h1 className="m-0 font-law text-display font-bold leading-[1.1]">{t('pages:constitution.historyTitle')}</h1>
        <p className="m-0 max-w-[60ch] text-body text-ink-soft">{t('pages:constitution.historyLead')}</p>
      </header>
      <ol className="m-0 flex list-none flex-col rounded-card bg-sheet p-0 px-5 sm:px-8">
        {[...q.data.chapters].reverse().map((c) => (
          <li key={c.year} className="grid grid-cols-1 gap-x-6 gap-y-2 border-t border-rule py-6 first:border-t-0 sm:grid-cols-[5.5rem_1fr]">
            <span className={`font-law text-[2.6rem] font-bold leading-none ${c.current ? 'text-stamp' : 'text-ink-soft'}`}>{c.year}</span>
            <div className="flex min-w-0 flex-col gap-2">
              <span className="text-meta text-ink-soft">
                {t('pages:constitution.adoptedOn', { referendum: when(c.referendum), published: when(c.published) })}
              </span>
              {c.story?.[lang] ? <p lang={lang} className="m-0 text-body leading-[1.9]"><Story words={c.story[lang]} path={c.path} /></p> : null}
              <span className="flex flex-wrap items-center gap-x-4 gap-y-2">
                <Stamp issue={c.issue} page={c.page} />
                <Link to={c.path} className="inline-flex min-h-11 items-center font-medium">
                  {c.current ? t('pages:constitution.readCurrent') : t('pages:constitution.readOld')}
                </Link>
              </span>
            </div>
          </li>
        ))}
      </ol>
      {/* The six constitutions side by side, as the blog counted them. */}
      <BlogLinks slugs={['six-constitutions']} />
    </Page>
  );
}
