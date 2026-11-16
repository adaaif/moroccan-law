import { useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { Stamp } from '@/features/corpus/article/Stamp';
import type { DeathPost } from '../blog.api';
import { Head } from '../Head';
import { Figure } from '../kit';
import { Print } from '../Print';
import { day } from '../clock/names';
import { n } from '../viz';
import { Code } from './Code';
import { peopleKey, tally } from './code';
import { People } from './People';
import { shareCode } from './share';
import '@/shared/design/french.css';
import '../post.css';
import './death.css';

/**
 * «الإعدام في القانون المغربي» (the blog's twentieth post), documentary: the penal code drawn article by article, the
 * thirty that punish with death inked in; the other texts in force that punish with it, the 1959 dahir on dangerous food
 * cut from its page; the procedure from the sentence to the burial, each step an article as printed; and the people under
 * a death sentence at each of the CNDH's reports printed in the Bulletin. No position: every sentence is a text's.
 */
export default function Death({ post }: { post: DeathPost }) {
  const { t, i18n } = useTranslation('blog');
  const lang = i18n.language;
  const rtl = lang !== 'fr';
  const fig = post.figures;
  const tx = fig.texts;
  const [picked, setPicked] = useState('393');
  const [year, setYear] = useState(2024);
  const [sharing, setSharing] = useState(false);
  const heroRef = useRef<HTMLElement>(null);

  const stamp = (key: string) => {
    const f = tx[key];
    return f?.viewer ? <Stamp issue={f.issue.replace(' bis', rtl ? ' مكرر' : ' bis')} page={f.page} to={f.viewer} className="dp-stamp" /> : null;
  };
  const kinds = Object.fromEntries(post.articles.map((a) => [a.n, a.kind])) as Record<string, 'death' | 'rule'>;
  const count = tally(post.articles);
  const all = fig.cells.length;
  const codePath = (num: string) => `/ma/dahir/1-59-413/art_${num}`;
  const names = Object.fromEntries(post.groups.map((g) => [g.key, t(`death.groups.${g.key}`)]));
  const cell = fig.cells.find((c) => c.n === picked);
  const meta = post.articles.find((a) => a.n === picked)!;
  const num = (v: string) => (rtl ? v : v.replace(/\./g, '-'));
  const people = (v: number) => t(`death.people.${peopleKey(v)}`, { n: n(v, lang) });

  const doShare = async () => {
    if (!heroRef.current) return;
    setSharing(true);
    try {
      await shareCode(heroRef.current, {
        dir: rtl ? 'rtl' : 'ltr', over: `${t('name')} ${t('number', { n: post.number })}`, title: t('death.share.title'),
        cells: fig.cells.map((c) => kinds[c.n] ?? null), lines: [t('death.hero.all', { n: n(all, lang) }), t('death.hero.death', { n: count.death })],
        legend: [t('death.legend.death'), t('death.legend.rule')], source: t('death.share.source'), site: t('death.share.site'),
      });
    } finally { setSharing(false); }
  };

  const o = post.others;
  const food = tx.food;
  const pickedYear = post.cndh.years.find((y) => y.year === year)!;

  return (
    <article className="bp dp" lang={lang}>
      <Head post={post} />

      <figure className="dp-hero" ref={heroRef} aria-labelledby="dp-hero-h">
        <p className="dp-say" id="dp-hero-h">
          <span>{t('death.hero.all', { n: n(all, lang) })}</span>{' '}
          <span className="dp-say-death">{t('death.hero.death', { n: count.death })}</span>
        </p>
        <p className="dp-say-more">{t('death.hero.more', { since: count.since1962, rule: count.rule })}</p>
        <ul className="dp-legend" aria-hidden="true">
          <li><i className="dp-cell is-death is-lit" />{t('death.legend.death')}</li>
          <li><i className="dp-cell is-rule is-lit" />{t('death.legend.rule')}</li>
          <li><i className="dp-cell" />{t('death.legend.other')}</li>
        </ul>
        <Code cells={fig.cells} kinds={kinds} picked={picked} onPick={setPicked} names={names} rtl={rtl}
              label={(v) => t(kinds[v] === 'death' ? 'death.pick.labelDeath' : 'death.pick.labelRule', { n: v })} />
        <div className="dp-pick" aria-live="polite">
          <p className="dp-pick-head">
            <Link to={codePath(picked)} className="dp-pick-n">{t('death.pick.art', { n: picked })}</Link>
            <span className={`dp-pick-kind is-${meta.kind}`}>{t(`death.legend.${meta.kind}`)}</span>
            <span className="dp-pick-since">{meta.since ? t('death.pick.since2003') : meta.was ? t('death.pick.sinceWas', { was: meta.was }) : t('death.pick.since1962')}</span>
            {stamp(`p-${picked}`)}
          </p>
          {cell?.clause ? <blockquote className="dp-quote" lang="ar" dir="rtl">«{cell.clause}»</blockquote> : null}
        </div>
        <div className="dp-share-row">
          <button type="button" className="dp-share" disabled={sharing} onClick={doShare}>
            <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 3v12" /><path d="m7 8 5-5 5 5" /><path d="M5 14v5a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-5" /></svg>
            {t('death.hero.share')}
          </button>
        </div>
      </figure>

      <details className="dp-list">
        <summary>{t('death.list.summary', { n: count.death + count.rule })}</summary>
        <ol>
          {fig.cells.filter((c) => kinds[c.n]).map((c) => (
            <li key={c.n} className={`is-${kinds[c.n]}`}>
              <Link to={codePath(c.n)} className="dp-list-n">{t('death.pick.art', { n: c.n })}</Link>
              <span className="dp-list-words" lang="ar" dir="rtl">{c.clause}</span>
            </li>
          ))}
        </ol>
      </details>

      <section className="bp-sec" aria-labelledby="dp-s1">
        <h2 id="dp-s1">{t('death.others.h')}</h2>
        <p className="bp-p">{t('death.others.p1')}</p>
        <div className="dp-food">
          <div className="dp-food-print">
            {food?.viewer ? <Print viewer={food.viewer} crop={o.food.crop} alt={t('death.others.foodAlt', { issue: food.issue, page: food.page })} /> : null}
            <p className="dp-food-src">{tx.food?.path ? <Link to={fig.articles.food ?? tx.food.path}>{t('death.others.dahir', { number: num(o.food.number) })}</Link> : null} · {day(o.food.date!, lang)} {stamp('food')}</p>
          </div>
          <div className="dp-food-words">
            <h3>{t('death.others.foodH')}</h3>
            <p className="bp-p">{t('death.others.foodP')}</p>
            <blockquote className="dp-quote" lang="ar" dir="rtl">«{o.food.art2}»</blockquote>
            <p className="bp-p">{t('death.others.victims')} {stamp('victims')}</p>
            <blockquote className="dp-quote is-small" lang="ar" dir="rtl">«{o.victims.words}»</blockquote>
            <p className="dp-note">{t('death.others.standing')}</p>
          </div>
        </div>
        <h3 className="dp-h3">{t('death.others.militaryH', { n: o.military.arts.length })}</h3>
        <ul className="dp-arts">
          {o.military.arts.map((a) => (
            <li key={a.n}>
              <p className="dp-arts-head">{fig.articles[`m-${a.n}`] ? <Link to={fig.articles[`m-${a.n}`]}>{t('death.others.military', { number: num(o.military.number), n: a.n })}</Link> : null} {stamp(`m-${a.n}`)}</p>
              <blockquote className="dp-quote is-small" lang="ar" dir="rtl">«{a.words}»</blockquote>
            </li>
          ))}
        </ul>
        <h3 className="dp-h3">{t('death.others.railwayH')}</h3>
        <blockquote className="dp-quote is-small" lang="ar" dir="rtl">«{o.railway.words}»</blockquote>
        <p className="dp-src">{fig.articles.railway ? <Link to={fig.articles.railway}>{t('death.others.railway', { number: num(o.railway.number), n: o.railway.art })}</Link> : null} · {day(o.railway.date!, lang)} {stamp('railway')}</p>
      </section>

      <section className="bp-sec" aria-labelledby="dp-s2">
        <h2 id="dp-s2">{t('death.steps.h')}</h2>
        <p className="bp-p">{t('death.steps.p1')}</p>
        <ol className="dp-steps">
          {post.steps.map((s) => (
            <li key={s.key} className="dp-step">
              <h3 className="dp-step-h">{t(`death.steps.${s.key}`)}{s.since ? <span className="dp-since">{t('death.steps.since', { year: s.since })}</span> : null}</h3>
              <blockquote className="dp-quote is-small" lang="ar" dir="rtl">«{s.words}»</blockquote>
              {s.key === 'witnesses' ? (
                <ul className="dp-witnesses">{post.witnesses.map((w) => <li key={w}>{t(`death.witnesses.${w}`)}</li>)}</ul>
              ) : null}
              {s.was ? (
                <p className="dp-was"><span className="dp-was-year">{s.was.year}</span> <span lang="ar" dir="rtl">«{s.was.words}»</span> {stamp(`w-${s.key}`)}</p>
              ) : null}
              <p className="dp-src">{fig.articles[`s-${s.key}`] ? <Link to={fig.articles[`s-${s.key}`]}>{t(s.akn?.includes('/decret/') ? 'death.steps.decree' : 'death.steps.code', { n: s.art })}</Link> : null} {stamp(`s-${s.key}`)}</p>
            </li>
          ))}
        </ol>
      </section>

      <section className="bp-sec" aria-labelledby="dp-s3">
        <h2 id="dp-s3">{t('death.cndh.h')}</h2>
        <p className="bp-p">{t('death.cndh.p1')}</p>
        <blockquote className="dp-quote" lang="ar" dir="rtl">«{post.cndh.halt.words}»</blockquote>
        <p className="dp-src">{t('death.cndh.haltSrc')} {stamp('c-halt')}</p>
        <Figure id="dp-people" q={t('death.cndh.q')} unit={t('death.cndh.unit')} so={t('death.cndh.so', { pardons: n(post.cndh.pardons.n, lang) })}
                source={t('death.cndh.source')}
                pick={<>{t('death.cndh.pick', { year: pickedYear.year, people: people(pickedYear.n) })} {stamp(`c-${pickedYear.year}`)}</>}>
          <People years={post.cndh.years} picked={year} onPick={setYear} aria={t('death.cndh.aria')} />
        </Figure>
        <p className="bp-p">{t('death.cndh.vote')}</p>
        <blockquote className="dp-quote is-small" lang="ar" dir="rtl">«{post.cndh.vote.words}»</blockquote>
        <p className="dp-src">{stamp('c-vote')}</p>
      </section>

      <section className="bp-method" aria-labelledby="dp-method">
        <h2 id="dp-method">{t('death.method.h')}</h2>
        <ul>
          {(['code', 'pages', 'others', 'steps', 'cndh', 'check'] as const).map((k) => <li key={k}>{t(`death.method.${k}`)}</li>)}
          <li>{t('death.method.on', { on: day(post.counted_on, lang) })}</li>
        </ul>
      </section>
    </article>
  );
}
