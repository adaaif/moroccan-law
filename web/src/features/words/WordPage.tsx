import { useTranslation } from 'react-i18next';
import { Link, useParams } from 'react-router-dom';
import { AR } from '@/features/corpus/format';
import { WORDS, type Word } from '@/features/corpus/article/words';
import { firstRegister, useWord } from '@/features/explain/explain.api';
import { useSearchResults } from '@/features/search/search.api';
import { topicColour } from '@/features/topics/colour';
import { TopicIcon } from '@/features/topics/TopicIcon';
import { useTopics } from '@/features/topics/topics.api';
import '@/shared/locales/pages';
import { usePageTitle } from '@/shared/services/title';
import { Page, PageSkeleton } from '@/shared/components/ui';
import { textName } from '@/features/corpus/names';
import { LoadError } from '@/features/corpus/NotFound';
import { useSession } from '@/shared/stores/session';

/** /words/:slug (R9 of the for-everyone review): a word that opens the law — what it means, as people wrote it and a
 *  reviewer checked it (or as the reading page says it, for its own words), where the law uses it, its topic. */
export default function WordPage() {
  const { slug = '' } = useParams();
  const { t, i18n } = useTranslation();
  const signedIn = useSession((x) => Boolean(x.tokens));
  const lang = i18n.language === 'fr' ? 'fr' : 'ar';
  const word = useWord(slug);
  const topics = useTopics();
  const builtIn = (WORDS as readonly string[]).includes(slug);
  const concept = word.data?.concept;
  usePageTitle([concept?.term ? (concept.term[lang] || concept.term.ar) : null, t('words.title')]);
  const search = concept?.search ?? '';
  const where = useSearchResults({ q: search, type: '', year: '', repealed: false, page: 1 });
  if (word.isLoading) return <Main><PageSkeleton /></Main>;
  if (!concept) return <Main><LoadError error={word.error} retry={() => void word.refetch()} /></Main>;
  const registers = word.data?.registers ?? {};
  const register = firstRegister(registers, i18n.language);
  const meaning = register ? registers[register]!.body : builtIn ? t(`pages:wordMeans.${slug as Word}`) : '';
  const term = concept.term?.[lang] ?? (builtIn ? t(`words.items.${slug as Word}.term`) : slug);
  const topic = topics.data?.find((x) => x.slug === concept.topic);
  return (
    <Main>
      <Link to="/words" className="text-body text-ink-soft no-underline hover:text-stamp">{t('words.all')}</Link>
      <section className="flex flex-col gap-3 rounded-card bg-sheet px-5 py-6 sm:px-8">
        <h1 lang={lang} className="m-0 text-h1 font-bold leading-tight">{term}</h1>
        {meaning ? (
          <div className="flex flex-col gap-2 rounded-card bg-people-wash px-4 py-3.5">
            <p dir="auto" className="m-0 text-lead leading-[1.8]">{meaning}</p>
            {register ? <p className="m-0 text-meta text-ink-soft">{t('pages:explain.notLaw')}</p> : null}
          </div>
        ) : null}
        {/* «كتابة الشرح الأول» for someone who can write (C2 of the where-it-trips review): sign-up is closed, and a visitor was
            asked to write what they came to read. */}
        {!builtIn && (meaning || signedIn) ? <Link to={`/explain/words/${slug}`} className="self-start text-body font-medium no-underline">{meaning ? t('pages:explain.more') : t('pages:explain.write')}</Link> : null}
      </section>

      {search ? (
        <section className="flex flex-col gap-2 rounded-card bg-sheet px-5 py-6 sm:px-8">
          <h2 className="m-0 text-lead font-semibold">{t('pages:words.where')}</h2>
          {where.data?.results.length ? (
            <ul className="m-0 flex list-none flex-col p-0">
              {where.data.results.slice(0, 5).map((r) => (
                <li key={r.text.path} className="border-t border-rule py-3 first:border-t-0">
                  <span dir="auto" className="block text-body text-ink-soft">{textName(r.text, i18n.language)}</span>
                  <ul className="m-0 mt-1.5 flex list-none flex-wrap gap-2 p-0">
                    {r.articles.slice(0, 4).map((a) => (
                      <li key={a.path}><Link {...AR} to={a.path} className="inline-flex rounded-full bg-paper px-3 py-1 text-meta font-semibold no-underline">{a.label}</Link></li>
                    ))}
                  </ul>
                </li>
              ))}
            </ul>
          ) : <p className="m-0 text-body text-ink-soft">{where.isLoading ? t('corpus.loading') : t('pages:words.nowhere')}</p>}
          <Link to={`/search?q=${encodeURIComponent(search)}`} className="self-start text-body font-medium no-underline">{t('pages:words.searchAll')}</Link>
        </section>
      ) : null}

      {topic ? (
        <Link to={`/topics/${topic.slug}`} style={topicColour(topic.slug)}
              className="flex items-center gap-3 rounded-card bg-sheet px-5 py-4 text-ink no-underline hover:text-stamp sm:px-8">
          <span className="grid size-11 place-items-center rounded-card bg-[color-mix(in_srgb,var(--t)_15%,var(--color-sheet))] text-[color:var(--t)]"><TopicIcon slug={topic.slug} /></span>
          <span lang={lang} className="text-lead font-semibold">{topic.name[lang]}</span>
        </Link>
      ) : null}
    </Main>
  );
}

function Main({ children }: { children: React.ReactNode }) {
  return <Page width="reading" className="gap-4">{children}</Page>;
}
