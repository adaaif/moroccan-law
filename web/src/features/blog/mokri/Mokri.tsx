import { useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { Stamp } from '@/features/corpus/article/Stamp';
import type { MokriPost } from '../blog.api';
import { Head } from '../Head';
import { Figure, Table } from '../kit';
import { Print } from '../Print';
import { day } from '../clock/names';
import { n } from '../viz';
import { Relay } from './Relay';
import { runs, texts } from './runs';
import { shareRelay } from './share';
import '@/shared/design/french.css';
import '../post.css';
import './mokri.css';

/**
 * «محمد المقري» (the blog's twenty-fifth post): one name under 11,679 texts of the Protectorate, year by year, with the
 * eleven Residents General who authorised their publication in turn; the signature cut from the Bulletin's thousandth
 * issue; what a Grand Vizier signed, from airships to the price of a cinema seat; and the last text that carries the name.
 */
export default function Mokri({ post }: { post: MokriPost }) {
  const { t, i18n } = useTranslation('blog');
  const lang = i18n.language;
  const rtl = lang !== 'fr';
  const fig = post.figures;
  const tx = fig.texts;
  const [year, setYear] = useState(1931);
  const [sharing, setSharing] = useState(false);
  const heroRef = useRef<HTMLElement>(null);
  const years = fig.years.filter((y) => y.year <= 1955);
  const names = Object.fromEntries(post.residents.map((r) => [r.key, rtl ? r.ar : r.fr]));
  const picked = years.find((y) => y.year === year)!;
  const sum = (k: 'dahir' | 'order') => years.reduce((s, y) => s + y[k], 0);
  const peak = years.reduce((a, b) => (texts(b) > texts(a) ? b : a));
  const stamp = (key: string) => {
    const f = tx[key];
    return f?.viewer ? <Stamp issue={f.issue.replace(' bis', rtl ? ' مكرر' : ' bis')} page={f.page} to={f.viewer} className="mk-stamp" /> : null;
  };
  const count = (v: number) => t(`mokri.texts.${v === 1 ? 'one' : v === 2 ? 'two' : v % 100 >= 3 && v % 100 <= 10 ? 'few' : 'many'}`, { n: n(v, lang) });

  const doShare = async () => {
    if (!heroRef.current) return;
    setSharing(true);
    try {
      await shareRelay(heroRef.current, {
        dir: rtl ? 'rtl' : 'ltr', over: `${t('name')} ${t('number', { n: post.number })}`, title: post.title[rtl ? 'ar' : 'fr'],
        years: years.map((y) => ({ year: y.year, n: texts(y) })), runs: runs(years).map(([k, a, b]) => ({ name: names[k], a, b })),
        nameLabel: t('mokri.hero.name'), source: t('mokri.share.source'), site: t('mokri.share.site'),
      });
    } finally { setSharing(false); }
  };

  return (
    <article className="bp mk" lang={lang}>
      <Head post={post} />

      <section className="mk-hero" ref={heroRef} aria-labelledby="mk-hero-name">
        <p className="mk-signature" id="mk-hero-name" lang="ar" dir="rtl">محمد المقري</p>
        <p className="mk-count"><b>{n(fig.total, lang)}</b> <span>{t('mokri.hero.count', { dahirs: n(sum('dahir'), lang), orders: n(sum('order'), lang) })}</span></p>
        <Figure id="mk-relay" q={t('mokri.hero.q')} unit={t('mokri.hero.unit')} wide
                so={t('mokri.hero.so', { peak: peak.year, peakN: n(texts(peak), lang), changes: t(`mokri.times.${runs(years).length - 1 <= 10 ? 'few' : 'many'}`, { n: runs(years).length - 1 }) })}
                source={t('fig.source', { from: 1913, to: 1956 })}
                pick={t('mokri.hero.pick', { year: picked.year, texts: count(texts(picked)), dahirs: n(picked.dahir, lang), orders: n(picked.order, lang), resident: picked.resident ? names[picked.resident] : '—' })}
                table={<Table head={[t('mokri.hero.year'), t('mokri.hero.dahirs'), t('mokri.hero.orders'), t('mokri.hero.resident')]}
                              rows={years.map((y) => [y.year, y.dahir, y.order, y.resident ? names[y.resident] : '—'])} />}>
          <Relay years={years} picked={year} onPick={setYear} names={names} nameLabel={t('mokri.hero.name')} aria={t('mokri.hero.aria')} />
        </Figure>
        <div className="mk-share-row">
          <button type="button" className="mk-share" disabled={sharing} onClick={doShare}>
            <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 3v12" /><path d="m7 8 5-5 5 5" /><path d="M5 14v5a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-5" /></svg>
            {t('mokri.hero.share')}
          </button>
        </div>
      </section>

      <section className="bp-sec" aria-labelledby="mk-s1">
        <h2 id="mk-s1">{t('mokri.clip.h')}</h2>
        <p className="bp-p">{t('mokri.clip.p1')}</p>
        <div className="mk-clip">
          {tx.clip?.viewer ? <Print viewer={tx.clip.viewer} crop={post.clip.crop} alt={t('mokri.clip.alt', { issue: tx.clip.issue, page: tx.clip.page })} /> : null}
          <p className="mk-src">{tx.clip ? day(tx.clip.published, lang) : null} {stamp('clip')}</p>
        </div>
        <p className="bp-p">{t('mokri.clip.p2')}</p>
      </section>

      <section className="bp-sec" aria-labelledby="mk-s2">
        <h2 id="mk-s2">{t('mokri.signed.h')}</h2>
        <p className="bp-p">{t('mokri.signed.p1')}</p>
        <ol className="mk-signed">
          {post.signed.map((s) => (
            <li key={s.year}>
              <span className="mk-signed-year">{s.year}</span>
              <span className="mk-signed-body">
                <span className="mk-signed-title" lang="ar" dir="rtl">{tx[`s-${s.year}`]?.path ? <Link to={tx[`s-${s.year}`].path!}>{s.title}</Link> : s.title}</span>
                <span className="mk-src">{t(`mokri.signed.what.y${s.year}`)} {stamp(`s-${s.year}`)}</span>
              </span>
            </li>
          ))}
        </ol>
      </section>

      <section className="bp-sec" aria-labelledby="mk-s3">
        <h2 id="mk-s3">{t('mokri.end.h')}</h2>
        <p className="bp-p">{t('mokri.end.p1', { first: day(fig.first.date, lang), last: day(fig.last.date, lang) })}</p>
        <ul className="mk-ends">
          <li><span>{t('mokri.end.first')}</span> <Link to={fig.first.path} lang="ar" dir="rtl">{fig.first.title}</Link></li>
          <li><span>{t('mokri.end.last')}</span> <Link to={fig.last.path} lang="ar" dir="rtl">{fig.last.title}</Link></li>
        </ul>
        <p className="bp-p">{t('mokri.end.p2')}</p>
      </section>

      <section className="bp-method" aria-labelledby="mk-method">
        <h2 id="mk-method">{t('mokri.method.h')}</h2>
        <ul>
          {(['which', 'residents', 'names', 'check'] as const).map((k) => <li key={k}>{t(`mokri.method.${k}`)}</li>)}
          <li>{t('mokri.method.on', { on: day(post.counted_on, lang) })}</li>
        </ul>
      </section>
    </article>
  );
}
