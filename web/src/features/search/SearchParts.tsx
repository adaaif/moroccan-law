import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { AR, articleName, splitLabel } from '@/features/corpus/format';
import { ArchWindow } from '@/features/topics/Arch';
import { topicColour } from '@/features/topics/colour';
import { TopicIcon } from '@/features/topics/TopicIcon';
import { noteUse } from '@/topics/kit/use';
import { situationPath } from '@/features/situations/to';
import { chipClass } from '@/shared/components/buttons';
import type { SearchResponse, TopicWord } from './search.api';
import './answer.css';

/* The search page's answer, person first (30 Oct 2026, drawn again): the question said again with the
   law's words under its everyday ones, the topic's answer and the articles it rests on, the questions people asked
   already, then the texts. The law in Markazi and the stamp's violet, people in the conversation's teal. answer.css. */

type Lang = 'ar' | 'fr';
const both = (x: { ar: string; fr: string } | null | undefined, lang: Lang) => (x ? (lang === 'fr' && x.fr) || x.ar : '');

/** «مول الدار بغا يزيد فالكرا» with «الزيادة في الوجيبة الكرائية» under «بغا يزيد فالكرا»: the reader's words, and how the
 *  law names them, from the approved lists alone. The brackets draw once, the law's words rise under them. */
export function Said({ said }: { said: NonNullable<SearchResponse['said']> }) {
  const { t } = useTranslation();
  let n = 0;
  return (
    <section className="sa-said" aria-labelledby="sa-said">
      <h2 id="sa-said" className="sr-only">{t('pages:search2.said')}</h2>
      <p className="line" dir="auto">
        {said.map((s, i) => s.law ? (
          <span key={i} className="g" style={{ ['--i' as string]: n++ }}>
            <span className="top"><span className="w">{s.t.trim()}</span><span className="br" aria-hidden="true" /></span>
            <span {...AR} className="l"><span className="sr-only"> ({t('pages:search2.saidLaw')} </span>{s.law}<span className="sr-only">)</span></span>
          </span>
        ) : s.t.split(/\s+/).filter(Boolean).map((w, j) => <span key={`${i}-${j}`} className="p">{w}</span>))}
      </p>
      <p className="cap" aria-hidden="true">{t('pages:search2.said')}</p>
    </section>
  );
}

/** The door the question names, as the answer: the reader's moment in their words, the answer in one line, the way to
 *  the whole of it (and to a tool when the question names one), then the articles it rests on, the number in the
 *  margin as the law sets it. */
export function DoorAnswer({ doors, articles, words }: {
  doors: NonNullable<SearchResponse['doors']>; articles: NonNullable<SearchResponse['door_articles']>; words: (path: string) => string;
}) {
  const { t, i18n } = useTranslation();
  const lang: Lang = i18n.language === 'fr' ? 'fr' : 'ar';
  const [door, other] = doors;
  const groups = [...new Set(articles.map((a) => both(a.text, lang)))];
  return (
    <section className="sa-ans" style={topicColour(door.topic)} aria-labelledby="sa-ans">
      <div className="top">
        <span className="sit"><TopicIcon slug={door.topic} size={18} /><span lang={lang}>{both(door.title, lang)}</span></span>
        {/* The figure the door carries, said first: «شحال السميك» was answered without its 17,92 (RD7 of the readers review). */}
        {door.mark?.value ? (
          <p className="fig"><b dir="ltr">{door.mark.value}</b>{door.mark.unit ? <span lang={lang}>{both(door.mark.unit, lang)}</span> : null}</p>
        ) : null}
        <h2 id="sa-ans" className="lead" lang={lang}>{both(door.lead, lang) || both(door.title, lang)}</h2>
        <span className="acts">
          <Link to={door.path} onClick={() => noteUse('door', '/search')} className="go">{t('pages:search2.answerOpen')}</Link>
          {other ? (
            <Link to={other.path} onClick={() => noteUse('door', '/search')} className="also" style={topicColour(other.topic)} lang={lang}>
              <TopicIcon slug={other.topic} size={18} />{both(other.title, lang)}
            </Link>
          ) : null}
        </span>
      </div>
      {groups.length ? (
        <div className="sa-law">
          {groups.map((name) => (
            <div key={name}>
              <h3>{t('pages:search.doorFrom', { name })}</h3>
              <ol>
                {articles.filter((a) => both(a.text, lang) === name).map((a) => {
                  return (
                    <li key={a.path}>
                      <Link to={words(a.path)}>
                        {/* On a French page the article's official French, as the results under it show theirs (RD12). */}
                        <Margin label={lang === 'fr' && a.french ? a.french.label : a.label} />
                        {lang === 'fr' && a.french
                          ? <span lang="fr" dir="ltr" className="b fr font-law-fr">{a.french.body}</span>
                          : <span {...AR} className="b">{a.body}</span>}
                      </Link>
                    </li>
                  );
                })}
              </ol>
            </div>
          ))}
        </div>
      ) : null}
    </section>
  );
}

/** No door names the question (HM8 of the hard-moment review): the nearest moments, each a way in with its one
 *  line, asked back before any text, so a question in plain words never lands first on a 1928 dahir. */
export function Nearest({ doors }: { doors: NonNullable<SearchResponse['nearest']> }) {
  const { t, i18n } = useTranslation();
  const lang: Lang = i18n.language === 'fr' ? 'fr' : 'ar';
  return (
    <section className="sa-near" aria-labelledby="sa-near">
      <h2 id="sa-near">{t('pages:search.nearest')}</h2>
      <p>{t('pages:search.nearestHelp')}</p>
      <ul>
        {doors.map((d) => (
          <li key={d.slug}>
            <Link to={d.path} onClick={() => noteUse('door', '/search')} style={topicColour(d.topic)}>
              <TopicIcon slug={d.topic} size={22} />
              <span><b lang={lang}>{both(d.title, lang)}</b>{d.lead ? <span lang={lang}>{both(d.lead, lang)}</span> : null}</span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}

/** An article's label in the margin, as the law page sets it: «المادة» small over «32» large. `data-label` marks it for
 *  the view transition that makes it the article's own number (U7 of the Moroccan-design review). */
export function Margin({ label }: { label: string }) {
  const { t } = useTranslation();
  const [word, number] = splitLabel(articleName(label, t));
  return (
    <span {...AR} data-label className={`sa-n${[...number].length > 4 ? ' long' : ''}`}>
      {word ? <small>{word}</small> : null}{number}
    </span>
  );
}

/** «سولو قبلك»: the questions of the topic's place that asked it already, each with its best answer as the conversation
 *  draws it (the question from the start side, the answer in teal from the end side). People's words, said so. */
export function People({ people, topic }: { people: NonNullable<SearchResponse['people']>; topic: { slug: string; name: { ar: string; fr: string } } }) {
  const { t, i18n } = useTranslation();
  const lang: Lang = i18n.language === 'fr' ? 'fr' : 'ar';
  return (
    <section className="sa-people" aria-labelledby="sa-people">
      <div className="head">
        <h2 id="sa-people">{t('pages:search2.people')}</h2>
        <Link to={`/talk/${topic.slug}`}>{t('pages:search2.peopleAll', { name: both(topic.name, lang) })}</Link>
      </div>
      <ol>
        {people.map((p) => (
          <li key={p.id}>
            <Link to={p.path} className="sa-ex">
              <span className="q" dir="auto">{p.title || p.body}</span>
              {p.answer ? <span className="a" dir="auto">{p.answer.body}</span> : <span className="none">{t('pages:search2.noAnswer')}</span>}
              <span className="meta">
                {p.answer?.accepted ? <span className="yes">✓ {t('pages:search2.accepted')}</span> : null}
                <span>{t('pages:search2.answers', { count: p.answers })}</span>
              </span>
            </Link>
          </li>
        ))}
      </ol>
      <p className="note">{t('pages:search2.peopleNote')}</p>
    </section>
  );
}

/** The part of life the question names (R1–R2 of the for-everyone review): its window, its name, its guides and its words
 *  of the law, each a search. A way in, so the arch. */
export function TopicCard({ topic, words }: { topic: NonNullable<SearchResponse['topics']>[number]; words?: TopicWord[] }) {
  const { t, i18n } = useTranslation();
  const lang: Lang = i18n.language === 'fr' ? 'fr' : 'ar';
  return (
    <section className="sa-topic" style={topicColour(topic.slug)} aria-labelledby={`sa-topic-${topic.slug}`}>
      <Link to={`/topics/${topic.slug}`} className="face">
        <ArchWindow slug={topic.slug} className="w-16" />
        <span className="nm">
          <small>{t('pages:topics.hint')}</small>
          <b id={`sa-topic-${topic.slug}`} lang={lang}>{topic.name[lang]}</b>
          <span className="open">{t('pages:topics.open')}</span>
        </span>
      </Link>
      {topic.situations?.length ? (
        <ul className="guides">
          {topic.situations.map((x) => (
            <li key={x.slug}><Link to={situationPath(x.slug)} lang={lang}>{x.title[lang]}</Link></li>
          ))}
        </ul>
      ) : null}
      {words?.length ? (
        <div className="words">
          <h3>{t('pages:search.lawWords')}</h3>
          <ul>
            {words.map((w) => (
              <li key={w.slug}>
                <Link to={`/search?q=${encodeURIComponent(w.search)}`} lang={lang} className={chipClass(false, 'h-11 text-body')}>{w.term[lang]}</Link>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}
