import { useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { Stamp } from '@/features/corpus/article/Stamp';
import type { ExpropriationPost } from '../blog.api';
import { Head } from '../Head';
import { Figure, Table } from '../kit';
import { day } from '../clock/names';
import { n } from '../viz';
import { shareYears } from './share';
import { percent, sums, total } from './sums';
import { Years } from './Years';
import '@/shared/design/french.css';
import '../post.css';
import './expropriation.css';

/**
 * «نزع الملكية» (the blog's twenty-fourth post): every decree that declares the public good and expropriates, year by year
 * since 1956, the part for water in blue; what they were for in the 2010s and since 2020, side by side; the last decree
 * for each purpose as the Bulletin titled it; and the law and the Constitution that allow it, as printed.
 */
const FROM = 1956;

export default function Expropriation({ post }: { post: ExpropriationPost }) {
  const { t, i18n } = useTranslation('blog');
  const lang = i18n.language;
  const rtl = lang !== 'fr';
  const fig = post.figures;
  const tx = fig.texts;
  const [year, setYear] = useState(2024);
  const [sharing, setSharing] = useState(false);
  const heroRef = useRef<HTMLElement>(null);
  const last = post.span[1];
  const years = fig.years.filter((y) => y.year >= FROM);
  const now = sums(fig.years, 2020, last), before = sums(fig.years, 2010, 2019);
  const nowAll = Object.values(now).reduce((a, b) => a + b, 0), beforeAll = Object.values(before).reduce((a, b) => a + b, 0);
  const span = last - 2020 + (new Date(`${post.counted_on}T12:00:00Z`).getUTCMonth() + 1) / 12;
  const pace = Math.round(nowAll / span), pacePrev = Math.round(beforeAll / 10);
  const keys = [...post.purposes.map((p) => p.key), 'other'].sort((a, b) => (now[b] ?? 0) - (now[a] ?? 0));
  const picked = years.find((y) => y.year === year)!;
  const stamp = (key: string) => {
    const f = tx[key];
    return f?.viewer ? <Stamp issue={f.issue.replace(' bis', rtl ? ' مكرر' : ' bis')} page={f.page} to={f.viewer} className="ex-stamp" /> : null;
  };

  const doShare = async () => {
    if (!heroRef.current) return;
    setSharing(true);
    try {
      await shareYears(heroRef.current, {
        dir: rtl ? 'rtl' : 'ltr', over: `${t('name')} ${t('number', { n: post.number })}`, title: post.title[rtl ? 'ar' : 'fr'],
        years: years.map((y) => ({ year: y.year, all: total(y), water: y.water ?? 0 })), water: t('expropriation.legend.water'), rest: t('expropriation.legend.rest'),
        source: t('expropriation.share.source'), site: t('expropriation.share.site'),
      });
    } finally { setSharing(false); }
  };

  return (
    <article className="bp ex" lang={lang}>
      <Head post={post} />

      <figure className="ex-hero" ref={heroRef} aria-labelledby="ex-hero-q">
        <p className="ex-q" id="ex-hero-q">{t('expropriation.hero.q')}</p>
        <div className="ex-facts">
          <p><b>{n(nowAll, lang)}</b><span>{t('expropriation.hero.since')}</span></p>
          <p><b>{n(pace, lang)}</b><span>{t('expropriation.hero.pace', { prev: pacePrev })}</span></p>
          <p className="is-water"><b dir="ltr">{rtl ? `\u2066${percent(now.water ?? 0, nowAll)}٪\u2069` : `${percent(now.water ?? 0, nowAll)}\u202f%`}</b><span>{t('expropriation.hero.water', { prev: percent(before.water ?? 0, beforeAll) })}</span></p>
        </div>
        <ul className="ex-legend">
          <li><i className="ex-water" />{t('expropriation.legend.water')}</li>
          <li><i className="ex-rest" />{t('expropriation.legend.rest')}</li>
        </ul>
        <Years years={years} picked={year} onPick={setYear} aria={t('expropriation.hero.aria')} ticks={[FROM, 1980, 2000, 2020]} />
        <p className="ex-pick" aria-live="polite">{t('expropriation.hero.pick', { year: picked.year, all: total(picked), water: picked.water ?? 0 })}</p>
        <div className="ex-share-row">
          <button type="button" className="ex-share" disabled={sharing} onClick={doShare}>
            <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 3v12" /><path d="m7 8 5-5 5 5" /><path d="M5 14v5a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-5" /></svg>
            {t('expropriation.hero.share')}
          </button>
        </div>
      </figure>

      <section className="bp-sec" aria-labelledby="ex-s1">
        <h2 id="ex-s1">{t('expropriation.what.h')}</h2>
        <p className="bp-p">{t('expropriation.what.p1')}</p>
        <Figure id="ex-what" q={t('expropriation.what.q')} unit={t('expropriation.what.unit')}
                so={t('expropriation.what.so', { water: percent(now.water ?? 0, nowAll), prev: percent(before.water ?? 0, beforeAll), road: percent(now.road ?? 0, nowAll), roadPrev: percent(before.road ?? 0, beforeAll) })}
                source={t('fig.source', { from: 2010, to: last })}
                table={<Table head={[t('expropriation.what.for'), '2010–2019', `2020–${last}`]} rows={keys.map((k) => [t(`expropriation.purposes.${k}`), before[k] ?? 0, now[k] ?? 0])} />}>
          <ul className="ex-what" dir={rtl ? 'rtl' : 'ltr'}>
            {keys.map((k) => (
              <li key={k} className={k === 'water' ? 'is-water' : ''}>
                <span className="ex-what-name">{t(`expropriation.purposes.${k}`)}</span>
                <span className="ex-what-bars" dir="ltr">
                  <span className="ex-bar is-prev" style={{ inlineSize: `${percent(before[k] ?? 0, beforeAll)}%` }} />
                  <span className="ex-bar is-now" style={{ inlineSize: `${percent(now[k] ?? 0, nowAll)}%` }} />
                </span>
                <span className="ex-what-n" dir="ltr">{percent(before[k] ?? 0, beforeAll)} → <b>{percent(now[k] ?? 0, nowAll)}</b></span>
              </li>
            ))}
          </ul>
          <p className="ex-what-key">{t('expropriation.what.key')}</p>
        </Figure>
      </section>

      <section className="bp-sec" aria-labelledby="ex-s2">
        <h2 id="ex-s2">{t('expropriation.last.h')}</h2>
        <p className="bp-p">{t('expropriation.last.p1')}</p>
        <ul className="ex-cards">
          {keys.filter((k) => fig.examples[k] && k !== 'other').map((k) => (
            <li key={k} className={`ex-card${k === 'water' ? ' is-water' : ''}`}>
              <p className="ex-card-kind">{t(`expropriation.purposes.${k}`)}</p>
              <p className="ex-card-title" lang="ar" dir="rtl">{tx[`e-${k}`]?.path ? <Link to={tx[`e-${k}`].path!}>{fig.examples[k].title}</Link> : fig.examples[k].title}</p>
              <p className="ex-src">{tx[`e-${k}`] ? day(tx[`e-${k}`].published, lang) : null} {stamp(`e-${k}`)}</p>
            </li>
          ))}
        </ul>
        <p className="ex-note">{t('expropriation.last.land')} <Link to="/topics/land">{t('expropriation.last.landLink')}</Link></p>
      </section>

      <section className="bp-sec" aria-labelledby="ex-s3">
        <h2 id="ex-s3">{t('expropriation.law.h')}</h2>
        <p className="bp-p">{t('expropriation.law.p1')}</p>
        <blockquote className="ex-quote" lang="ar" dir="rtl">«{post.constitution.words}»</blockquote>
        <p className="ex-src"><Link to={`/constitution/${post.constitution.year}/${post.constitution.art}`}>{t('expropriation.law.const', { art: post.constitution.art })}</Link> {stamp('constitution')}</p>
        <p className="bp-p">{t('expropriation.law.p2')}</p>
        <blockquote className="ex-quote" lang="ar" dir="rtl">«{post.law.words}»</blockquote>
        <p className="ex-src">{tx.law?.path ? <Link to={`${tx.law.path}/art_1`}>{t('expropriation.law.law', { number: rtl ? post.law.number : post.law.number.replace('.', '-') })}</Link> : null} {stamp('law')}</p>
      </section>

      <section className="bp-method" aria-labelledby="ex-method">
        <h2 id="ex-method">{t('expropriation.method.h')}</h2>
        <ul>
          {(['which', 'what', 'check'] as const).map((k) => <li key={k}>{t(`expropriation.method.${k}`)}</li>)}
          <li>{t('expropriation.method.on', { on: day(post.counted_on, lang) })}</li>
        </ul>
      </section>
    </article>
  );
}
