import { useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { Stamp } from '@/features/corpus/article/Stamp';
import type { StrikePost } from '../blog.api';
import { Head } from '../Head';
import { Figure } from '../kit';
import { Print } from '../Print';
import { day } from '../clock/names';
import { Promises } from './Promises';
import { shareSentence } from './share';
import { changed, days, span } from './wait';
import { Wait } from './Wait';
import '@/shared/design/french.css';
import '../post.css';
import './strike.css';

/**
 * «حق الإضراب مضمون» (the blog's eighteenth post): the sentence as six constitutions printed it, cut from their pages and
 * stacked; the words that changed between them; sixty-two years on one line, drawn once, and the law's path day by day;
 * the law by its numbers; the 2011 Constitution's organic laws against the deadline its article 86 set. Every quote is the
 * meta's, read on its page; the spans are counted here.
 */
export default function Strike({ post }: { post: StrikePost }) {
  const { t, i18n } = useTranslation('blog');
  const lang = i18n.language;
  const side = lang === 'fr' ? 'fr' : 'ar';
  const rtl = lang !== 'fr';
  const [picked, setPicked] = useState('97.15');
  const [sharing, setSharing] = useState(false);
  const heroRef = useRef<HTMLElement>(null);
  const tx = post.figures.texts;
  const at = (k: string) => post.path.find((p) => p.key === k)!.date;
  const first = post.constitutions[0];
  const waited = span(first.date, post.law.published).years;
  const house = span(at('filed'), at('house1'));
  /** «سنة», «سنتان», «سنوات», «سنة»: the years after a number as Arabic writes them. */
  const yearsWord = (n: number) => t(n === 1 ? 'strike.years.one' : n === 2 ? 'strike.years.two' : n % 100 >= 3 && n % 100 <= 10 ? 'strike.years.few' : 'strike.years.many');
  const num = (v: string) => (rtl ? v : v.replace(/\./g, '-'));
  /** «بعد يوم واحد», «بعد يومين», «بعد 10 أيام», «بعد 41 يوما», «بعد 3.001 يوم»: the days after a number as Arabic writes them. */
  const gapWords = (n: number) => {
    const shown = n.toLocaleString(rtl ? 'en-US' : 'fr-FR').replace(/,/g, '.').replace(/\u202f/g, ' ');
    const r = n % 100;
    return n === 1 ? t('strike.wait.gapOne') : n === 2 ? t('strike.wait.gapTwo')
      : t(r >= 3 && r <= 10 ? 'strike.wait.gapFew' : r >= 11 ? 'strike.wait.gapMany' : 'strike.wait.gapUnit', { n: shown });
  };

  const stamp = (key: string) => {
    const f = tx[key];
    return f ? <Stamp issue={f.issue.replace(' bis', rtl ? ' مكرر' : ' bis')} page={f.page} to={f.viewer} className="st-stamp" /> : null;
  };
  const art = (n: string) => {
    const to = post.figures.articles[n];
    const words = t('strike.numbers.art', { n });
    return to ? <Link to={to} className="st-art">{words}</Link> : <span>{words}</span>;
  };

  const doShare = async () => {
    if (!heroRef.current) return;
    setSharing(true);
    try {
      await shareSentence(heroRef.current, {
        dir: rtl ? 'rtl' : 'ltr', over: `${t('name')} ${t('number', { n: post.number })}`, title: t('strike.share.title'),
        slips: post.constitutions.map((c) => ({ year: c.year, viewer: tx[`c-${c.year}`]?.viewer ?? '', crop: c.crop })),
        count: waited, countWords: t('strike.hero.count'), source: t('strike.share.source'), site: t('strike.share.site'),
      });
    } finally { setSharing(false); }
  };

  const pickedLaw = post.organic.find((o) => o.number === picked);

  return (
    <article className="bp st" lang={lang}>
      <Head post={post} />

      <figure className="st-hero" ref={heroRef} aria-labelledby="st-kicker">
        <div className="st-hero-count">
          <p className="st-kicker" id="st-kicker">{t('strike.hero.kicker')}</p>
          <p className="st-big"><span className="st-big-n">{waited}</span><span className="st-big-unit">{t('strike.hero.count')}</span></p>
          <p className="st-between">{t('strike.hero.between')}</p>
          <p className="st-hero-law">{tx.law?.path ? <Link to={tx.law.path}>{rtl ? `القانون التنظيمي ${post.law.number}` : `loi organique ${num(post.law.number)}`}</Link> : null} {stamp('law')}</p>
        </div>
        <ol className="st-slips">
          {post.constitutions.map((c) => {
            const v = tx[`c-${c.year}`];
            const artName = t('strike.hero.art', { n: c.n });
            return (
              <li key={c.year} className="st-slip">
                <p className="st-slip-head">
                  <Link to={`/constitution/${c.year}/${c.n}`} className="st-slip-year">{c.year}</Link>
                  <span className="st-slip-art">{artName}</span>
                </p>
                {v?.viewer ? <Print viewer={v.viewer} crop={c.crop} alt={t('strike.hero.alt', { art: artName, year: c.year, page: c.page, issue: v.issue })} /> : null}
                <p className="st-slip-stamp">{stamp(`c-${c.year}`)}</p>
              </li>
            );
          })}
        </ol>
        <div className="st-share-row">
          <button type="button" className="st-share" disabled={sharing} onClick={doShare}>
            <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 3v12" /><path d="m7 8 5-5 5 5" /><path d="M5 14v5a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-5" /></svg>
            {t('strike.hero.share')}
          </button>
        </div>
      </figure>

      <section className="bp-sec" aria-labelledby="st-s1">
        <h2 id="st-s1">{t('strike.words.h')}</h2>
        <p className="bp-p">{t('strike.words.p1')}</p>
        <ol className="st-words" lang="ar" dir="rtl">
          {post.constitutions.map((c, i) => {
            const words = changed(i ? post.constitutions[i - 1].words : null, c.words);
            return (
              <li key={c.year}>
                <span className="st-words-year" dir="ltr">{c.year}</span>
                <span className="st-words-text">
                  {words.map((w, k) => <span key={k} className={`${w.changed ? 'is-new' : ''}${k < 3 ? ' is-first' : ''}`}>{w.word}{k < words.length - 1 ? ' ' : ''}</span>)}
                </span>
              </li>
            );
          })}
        </ol>
        <p className="st-note">{t('strike.words.note')}</p>
      </section>

      <section className="bp-sec" aria-labelledby="st-s2">
        <h2 id="st-s2">{t('strike.wait.h')}</h2>
        <Figure id="st-wait" q={t('strike.wait.q')} unit={t('strike.wait.unit')} so={t('strike.wait.so')} source={t('fig.source', { from: 1962, to: 2025 })} wide>
          <Wait from={first.date} to={post.law.published} rings={post.constitutions.map((c) => ({ year: c.year, date: c.date }))}
                band={[at('filed'), at('house1')]} rtl={rtl} aria={t('strike.wait.aria')}
                labels={{ band: t('strike.wait.band', { n: house.years }), years: yearsWord, law: t('strike.wait.law') }} />
        </Figure>
        <p className="bp-p">{t('strike.wait.p1')} {tx.decision?.path ? <Link to={tx.decision.path}>{rtl ? `القرار ${post.decision.number}` : `décision ${post.decision.number}`}</Link> : null} {stamp('decision')}</p>
        <ol className="st-path">
          {post.path.map((s, i) => {
            const gap = i ? days(post.path[i - 1].date, s.date) : null;
            return (
              <li key={s.key} className={s.key === 'filed' || s.key === 'house1' ? 'is-key' : ''}>
                <span className="st-path-day">{day(s.date, lang)}</span>
                <span className="st-path-body">
                  {gap !== null ? <span className="st-path-gap">{gapWords(gap)}</span> : null}
                  <span>{t(`strike.wait.steps.${s.key}`)}</span>
                  {s.key === 'filed' ? <span className="st-path-src">{stamp('election')}</span> : null}
                </span>
              </li>
            );
          })}
        </ol>
        <blockquote className="st-quote" lang="ar" dir="rtl">«{post.ruling}»</blockquote>
      </section>

      <section className="bp-sec" aria-labelledby="st-s3">
        <h2 id="st-s3">{t('strike.numbers.h')}</h2>
        <p className="bp-p">{t('strike.numbers.p1')}</p>
        <ul className="st-cards">
          {post.numbers.map((n) => {
            const unit = t(`strike.numbers.cards.${n.key}.unit`);
            return (
              <li key={n.key} className={`st-card is-${n.key}`}>
                <p className="st-card-n" dir={unit === '%' || unit === '٪' ? 'ltr' : undefined}>
                  <span className="st-card-num">{lang === 'fr' ? n.n.replace(/\./g, ' ') : n.n}</span><span className="st-card-unit">{unit}</span>
                </p>
                <p className="st-card-text">{t(`strike.numbers.cards.${n.key}.text`, { bulletin: post.bulletin })}</p>
                <p className="st-card-src">{art(n.art)} {stamp(`n-${n.key}`)}</p>
              </li>
            );
          })}
        </ul>
        <p className="bp-p">{t('strike.numbers.stop')} {art('19')}</p>
        <blockquote className="st-quote is-small" lang="ar" dir="rtl">«{post.stop}»</blockquote>
        <p className="bp-p">{t('strike.numbers.nostrike')} {art('22')}</p>
        <blockquote className="st-quote is-small" lang="ar" dir="rtl">«{post.nostrike}…»</blockquote>
      </section>

      <section className="bp-sec" aria-labelledby="st-s4">
        <h2 id="st-s4">{t('strike.promises.h')}</h2>
        <p className="bp-p">{t('strike.promises.p1')} {stamp('deadline')}</p>
        <blockquote className="st-quote" lang="ar" dir="rtl">«{post.deadline.words}»</blockquote>
        <Figure id="st-promises" q={t('strike.promises.q')} unit={t('strike.promises.unit')} so={t('strike.promises.so')} source={t('fig.source', { from: 2011, to: 2026 })}
                pick={pickedLaw ? (
                  <>
                    {tx[`ol-${pickedLaw.number}`]?.path ? <Link to={tx[`ol-${pickedLaw.number}`].path!}>{t('strike.promises.pickLaw', { number: num(pickedLaw.number) })}</Link>
                      : t('strike.promises.pickLaw', { number: num(pickedLaw.number) })}
                    {t('strike.promises.pickRest', { name: pickedLaw[side], date: day(pickedLaw.date, lang) })}{' '}
                    {stamp(`ol-${pickedLaw.number}`)}
                  </>
                ) : null}>
          <Promises laws={post.organic.map((o) => ({ number: o.number, name: o[side], date: o.date }))} band={['2011-07-30', post.election.date]} filed={at('filed')}
                    picked={picked} onPick={setPicked} labels={{ band: t('strike.promises.band') }} aria={t('strike.promises.aria')} rtl={rtl} />
        </Figure>
      </section>

      <section className="bp-method" aria-labelledby="st-method">
        <h2 id="st-method">{t('strike.method.h')}</h2>
        <ul>
          {(['pages', 'law', 'organic', 'election', 'check'] as const).map((k) => <li key={k}>{t(`strike.method.${k}`)}</li>)}
          <li>{t('strike.method.on', { on: day(post.counted_on, lang) })}</li>
        </ul>
      </section>
    </article>
  );
}
