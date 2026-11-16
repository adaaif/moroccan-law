import { useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { Stamp } from '@/features/corpus/article/Stamp';
import type { ParliamentPost } from '../blog.api';
import { Head } from '../Head';
import { Figure, Table } from '../kit';
import { day } from '../clock/names';
import { n } from '../viz';
import { Hands } from './Hands';
import { Reading } from './Reading';
import { shareSheets } from './share';
import { arabicKey, daysToRead, span, withoutParliament } from './time';
import '@/shared/design/french.css';
import '../post.css';
import './parliament.css';

/**
 * «على كل قانون يصوّت عليه البرلمان» (the blog's twenty-first post): one law and the sheets that follow it (the decrees and
 * the ministers' orders, as many as the Bulletin printed for each law since 1963); who made the laws year by year, the
 * King's texts «بمثابة قانون» in the years without a House, with the constitutions' own words; and how long the law in
 * force takes to read, at the time a day the reader picks.
 */
const MINUTES = [10, 30, 60, 480] as const;

export default function Parliament({ post }: { post: ParliamentPost }) {
  const { t, i18n } = useTranslation('blog');
  const lang = i18n.language;
  const rtl = lang !== 'fr';
  const fig = post.figures;
  const tx = fig.texts;
  const [year, setYear] = useState(1975);
  const [minutes, setMinutes] = useState<number>(30);
  const [sharing, setSharing] = useState(false);
  const heroRef = useRef<HTMLElement>(null);

  const stamp = (key: string) => {
    const f = tx[key];
    return f?.viewer ? <Stamp issue={f.issue.replace(' bis', rtl ? ' مكرر' : ' bis')} page={f.page} to={f.viewer} className="pl-stamp" /> : null;
  };
  const counted = (key: string, v: number) => t(`parliament.words.${key}.${arabicKey(v)}`, { n: n(v, lang) });
  const { decrees, orders, share } = fig.ratio;
  const voted = fig.forms['hand-voted'];

  // The years when the King's texts outnumber the voted laws, in runs.
  const lone = withoutParliament(fig.years);
  const bands: [number, number][] = [];
  for (const yr of lone) {
    const last = bands[bands.length - 1];
    if (last && last[1] === yr - 1) last[1] = yr; else bands.push([yr, yr]);
  }
  const votedYears = fig.years.filter((y) => y.year >= 2000 && y.year < post.span[1]);
  const thin = votedYears.reduce((a, b) => (b.voted < a.voted ? b : a));
  const full = votedYears.reduce((a, b) => (b.voted > a.voted ? b : a));
  const picked = fig.years.find((y) => y.year === year)!;
  const parts = (['voted', 'dfl', 'rdl', 'dlaw'] as const).filter((k) => picked[k] > 0).map((k) => counted(k, picked[k]));

  const spanWords = (days: number) => {
    const s = span(days);
    const bit = (k: 'years' | 'months' | 'days', v: number) => (v ? t(`parliament.time.${k}.${arabicKey(v)}`, { n: v }) : null);
    return [bit('years', s.y), bit('months', s.m), bit('days', s.d)].filter(Boolean).join(t('parliament.time.and'));
  };
  const layers = fig.reading.map((l) => ({ ...l, name: t(`parliament.reading.layers.${l.key}`), time: spanWords(daysToRead(l.words, post.reading.wpm, minutes)) }));
  const allDays = fig.reading.reduce((s, l) => s + daysToRead(l.words, post.reading.wpm, minutes), 0);
  const lawsHours = Math.round(fig.reading[0].words / post.reading.wpm / 60);

  const doShare = async () => {
    if (!heroRef.current) return;
    setSharing(true);
    try {
      await shareSheets(heroRef.current, {
        dir: rtl ? 'rtl' : 'ltr', over: `${t('name')} ${t('number', { n: post.number })}`, title: post.title[rtl ? 'ar' : 'fr'],
        rows: [{ n: 1, label: t('parliament.hero.law') }, { n: decrees, label: counted('decrees', decrees) }, { n: orders, label: counted('orders', orders) }],
        source: t('parliament.share.source', { all: n(fig.forms.all, lang), voted: n(voted, lang) }), site: t('parliament.share.site'),
      });
    } finally { setSharing(false); }
  };

  const row = (count: number, kind: string, label: string, who: string) => (
    <div className={`pl-row is-${kind}`}>
      <p className="pl-row-label"><b>{label}</b> <span>{who}</span></p>
      <div className="pl-sheets" dir="ltr" aria-hidden="true">
        {Array.from({ length: count }, (_, i) => <i key={i} className="pl-sheet" />)}
      </div>
    </div>
  );

  return (
    <article className="bp pl" lang={lang}>
      <Head post={post} />

      <figure className="pl-hero" ref={heroRef} aria-labelledby="pl-hero-h">
        <p className="pl-kicker" id="pl-hero-h">{t('parliament.hero.kicker')}</p>
        {row(1, 'law', t('parliament.hero.law'), t('parliament.hero.lawWho'))}
        {row(decrees, 'decree', counted('decrees', decrees), t('parliament.hero.decreesWho'))}
        {row(orders, 'order', counted('orders', orders), t('parliament.hero.ordersWho'))}
        <p className="pl-hero-more">{t('parliament.hero.more', { all: n(fig.forms.all, lang), voted: n(voted, lang), share })}</p>
        <div className="pl-share-row">
          <button type="button" className="pl-share" disabled={sharing} onClick={doShare}>
            <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 3v12" /><path d="m7 8 5-5 5 5" /><path d="M5 14v5a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-5" /></svg>
            {t('parliament.hero.share')}
          </button>
        </div>
      </figure>

      <section className="bp-sec" aria-labelledby="pl-s1">
        <h2 id="pl-s1">{t('parliament.hands.h')}</h2>
        <p className="bp-p">{t('parliament.hands.p1')}</p>
        <Figure id="pl-hands" q={t('parliament.hands.q')} unit={t('parliament.hands.unit')} wide
                so={t('parliament.hands.so', { thin: thin.year, thinN: thin.voted, full: full.year, fullN: full.voted })}
                source={t('fig.source', { from: post.span[0], to: post.span[1] })}
                pick={t('parliament.hands.pick', { year: picked.year, parts: parts.length ? parts.join(t('parliament.time.and')) : t('parliament.hands.none') })}
                table={<Table head={[t('parliament.hands.year'), ...(['voted', 'dfl', 'rdl', 'dlaw'] as const).map((k) => t(`parliament.legend.${k}`))]}
                              rows={fig.years.map((y) => [y.year, y.voted, y.dfl, y.rdl, y.dlaw])} />}>
          <ul className="pl-legend">
            {(['voted', 'dfl', 'rdl', 'dlaw'] as const).map((k) => <li key={k}><i className={`pl-${k}`} />{t(`parliament.legend.${k}`)}</li>)}
            <li><i className="pl-band-key" />{t('parliament.hands.band')}</li>
          </ul>
          <Hands years={fig.years} bands={bands} marks={[thin.year, full.year]} picked={year} onPick={setYear}
                 aria={t('parliament.hands.aria')} />
        </Figure>
        <p className="bp-p">{t('parliament.hands.p2')}</p>
        <blockquote className="pl-quote" lang="ar" dir="rtl">«{post.exception.decree.words}»</blockquote>
        <p className="pl-src">{tx.decree?.path ? <Link to={tx.decree.path}>{t('parliament.hands.decree', { number: post.exception.decree.number })}</Link> : null} · {day(post.exception.decree.date!, lang)} {stamp('decree')}</p>
        <p className="bp-p">{t('parliament.hands.p3')}</p>
        <blockquote className="pl-quote is-small" lang="ar" dir="rtl">«{post.exception.indemnities.words}»</blockquote>
        <p className="pl-src">{tx.indemnities?.path ? <Link to={tx.indemnities.path}>{t('parliament.hands.decree', { number: post.exception.indemnities.number })}</Link> : null} {stamp('indemnities')}</p>
        <p className="bp-p">{t('parliament.hands.p4')}</p>
        <ol className="pl-consts">
          {post.constitutions.map((c) => (
            <li key={c.year}>
              <p className="pl-const-head"><Link to={`/constitution/${c.year}`} className="pl-const-year">{c.year}</Link> <span>{t('parliament.hands.art', { n: c.art })}</span> {stamp(`c-${c.year}`)}</p>
              <blockquote className="pl-quote is-small" lang="ar" dir="rtl">«{c.words}»</blockquote>
            </li>
          ))}
        </ol>
      </section>

      <section className="bp-sec" aria-labelledby="pl-s2">
        <h2 id="pl-s2">{t('parliament.reading.h')}</h2>
        <p className="bp-p">{t('parliament.reading.p1', { laws: n(fig.reading[0].words, lang), hours: n(lawsHours, lang), wpm: post.reading.wpm })}</p>
        <Figure id="pl-read" q={t('parliament.reading.q')} unit={t('parliament.reading.unit', { wpm: post.reading.wpm })}
                so={t('parliament.reading.so', { all: spanWords(allDays) })}
                source={t('parliament.reading.source')}>
          <div className="pl-chips" role="radiogroup" aria-label={t('parliament.reading.choose')}>
            {MINUTES.map((mn) => (
              <button key={mn} type="button" role="radio" aria-checked={minutes === mn} className={minutes === mn ? 'is-on' : ''} onClick={() => setMinutes(mn)}>
                {t(`parliament.reading.minutes.${mn}`)}
              </button>
            ))}
          </div>
          <Reading layers={layers} wpm={post.reading.wpm} minutes={minutes} aria={t('parliament.reading.aria', { all: spanWords(allDays) })}
                   yearsWord={() => t('parliament.reading.axis')} />
        </Figure>
        <p className="pl-note">{t('parliament.reading.note', { laws: n(fig.reading[0].texts, lang), decrees: n(fig.reading[1].texts, lang), orders: n(fig.reading[2].texts, lang) })}</p>
      </section>

      <section className="bp-method" aria-labelledby="pl-method">
        <h2 id="pl-method">{t('parliament.method.h')}</h2>
        <ul>
          {(['forms', 'hands', 'reading', 'check'] as const).map((k) => <li key={k}>{t(`parliament.method.${k}`)}</li>)}
          <li>{t('parliament.method.on', { on: day(post.counted_on, lang) })}</li>
        </ul>
      </section>
    </article>
  );
}
