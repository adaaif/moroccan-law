import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { BlogLinks } from '@/features/blog/BlogLinks';
import { WORDS } from '@/features/corpus/article/words';
import { useWords, type Concept } from '@/features/explain/explain.api';
import { ArchDoor } from '@/features/topics/Arch';
import { useTopics } from '@/features/topics/topics.api';
import '@/shared/locales/pages';
import { usePageTitle } from '@/shared/services/title';
import { LinesSkeleton, Page } from '@/shared/components/ui';
import '@/features/corpus/library.css';

/** Arabic as one writes it in a hurry: no vowels, every alef one, «ى» as «ي», «ة» as «ه»; French without its accents. */
const fold = (s: string) => s.normalize('NFKD').replace(/[\u0300-\u036f\u064b-\u065f\u0670\u0640]/g, '').replace(/[\u0622\u0623\u0625\u0671]/g, '\u0627')
  .replace(/ى/g, 'ي').replace(/ة/g, 'ه').toLowerCase().trim();

/** /words: the words that open the law (R9 of the for-everyone review), as a lexicon (drawn again on 30 Oct 2026): by life
 *  topic, each under its door and a double rule; each word its headword in the law's type run on into its meaning as
 *  people wrote it and a person checked (people's saffron dot), else a line that says it is not written yet, and the
 *  way to where the law uses it; two columns on a desk. Then the reading page's own words («ظهير»، «نافذ»…). A box
 *  finds a word as one types, vowels and alefs as they come; the topics are an index beside it. */
export default function WordsPage() {
  const { t, i18n } = useTranslation();
  usePageTitle([t('words.title')]);
  const lang = i18n.language === 'fr' ? 'fr' : 'ar';
  const words = useWords();
  const topics = useTopics();
  const [q, setQ] = useState('');
  const want = fold(q);
  const waiting = words.isLoading || topics.isLoading;
  const concepts = words.data?.concepts ?? [];
  const hit = (...s: (string | null | undefined)[]) => !want || s.some((x) => x && fold(x).includes(want));
  const groups = (topics.data ?? [])
    .map((topic) => ({ topic, here: concepts.filter((c) => c.topic === topic.slug && hit(c.term?.ar, c.term?.fr, c.search, c.means?.[lang], c.means?.ar)) }))
    .filter((g) => g.here.length);
  const reading = WORDS.filter((w) => hit(t(`words.items.${w}.term`), t(`pages:wordMeans.${w}`)));
  const shown = groups.reduce((n, g) => n + g.here.length, 0) + reading.length;
  return (
    <Page width="wide" className="lb">
      <header className="lb-head side">
        <div>
          <h1>{t('words.title')}</h1>
          <p className="lead">{t(concepts.some((c) => !c.means) ? 'pages:words.leadIndex' : 'pages:words.lead2')}</p>
        </div>
        <div className="lb-find" role="search">
          <label htmlFor="words-find">{t('pages:lex.find')}</label>
          <span className="row"><input id="words-find" type="search" dir="auto" value={q} onChange={(e) => setQ(e.target.value)} placeholder={t('pages:lex.findHint')} /></span>
          <small aria-live="polite">{want ? t('pages:lex.shown', { count: shown }) : t('pages:lex.total', { count: concepts.length + WORDS.length })}</small>
        </div>
      </header>

      <div className="lb-lexwrap">
        <nav className="lb-index" aria-label={t('pages:words.index')}>
          {groups.map(({ topic, here }) => (
            <a key={topic.slug} href={`#t-${topic.slug}`} lang={lang}>{topic.name[lang]}<span>{here.length}</span></a>
          ))}
          {reading.length ? <a href="#reading">{t('pages:words.reading')}<span>{reading.length}</span></a> : null}
        </nav>
        <div className="lb-lex">
          {/* Both answers before any section: the words came first and the page's own words stood at the top, then the
              topics arrived and threw them down a screen (layout shift 0.43 to 0.47: RD16 of the readers review). */}
          {waiting ? <LinesSkeleton lines={8} /> : null}
          {groups.map(({ topic, here }) => (
            <section key={topic.slug} id={`t-${topic.slug}`} aria-labelledby={`h-${topic.slug}`} className="lb-lexsec">
              <div className="lb-lexhead">
                <h2 id={`h-${topic.slug}`} lang={lang}><ArchDoor slug={topic.slug} className="w-10" />{topic.name[lang]}</h2>
                <span className="n">{t('pages:lib2.wordsN', { count: here.length, n: here.length })}</span>
                <Link to={`/topics/${topic.slug}`}>{t('pages:lex.topic')}</Link>
              </div>
              <dl className="lb-entries">{here.map((c) => <Entry key={c.slug} concept={c} lang={lang} />)}</dl>
            </section>
          ))}
          {reading.length && !waiting ? (
            <section id="reading" aria-labelledby="h-reading" className="lb-lexsec">
              <div className="lb-lexhead">
                <h2 id="h-reading">{t('pages:words.reading')}</h2>
                <span className="n">{t('pages:words.readingLead')}</span>
              </div>
              <dl className="lb-entries">
                {reading.map((w) => (
                  <div key={w} id={w} className="lb-entry">
                    <dt><Link to={`/words/${w}`}>{t(`words.items.${w}.term`)}</Link></dt>
                    <dd className="def">{t(`pages:wordMeans.${w}`)}</dd>
                  </div>
                ))}
              </dl>
            </section>
          ) : null}
          {want && !shown ? (
            <p className="lb-empty">{t('pages:lex.none', { q })} <Link to={`/search?q=${encodeURIComponent(q)}`}>{t('pages:words.searchAll')}</Link></p>
          ) : null}
        </div>
      </div>
      {/* When words entered the law, as the blog counted it. */}
      <BlogLinks slugs={['words-in-the-law']} />
    </Page>
  );
}

/** A word: its headword as the law writes it, run on into its meaning as a reader wrote it (people's saffron dot) or
 *  the line that says it is not written yet; then the way to where the law uses it. */
function Entry({ concept: c, lang }: { concept: Concept; lang: 'ar' | 'fr' }) {
  const { t } = useTranslation();
  const means = c.means?.[lang] ?? c.means?.ar;
  return (
    <div className="lb-entry" lang={lang}>
      <dt><Link to={`/words/${c.slug}`}>{c.term?.[lang] ?? c.search}</Link></dt>
      {/* An index until its meanings are written (C2 of the where-it-trips review): 58 of 59 rows said none was. */}
      {means ? (
        <dd className="def" lang={c.means?.[lang] ? lang : 'ar'}><span className="by" aria-hidden="true" />{means}</dd>
      ) : null}
      <dd className="where"><Link to={`/words/${c.slug}`}>{t('pages:words.whereOnly')}</Link></dd>
    </div>
  );
}
