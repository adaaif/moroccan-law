import { type CSSProperties, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import type { DeadlinesPost } from '../blog.api';
import { Head } from '../Head';
import { Figure } from '../kit';
import { day } from '../clock/names';
import { n } from '../viz';
import { Scale } from './Scale';
import { shareLeaves } from './share';
import { arabicKey } from './time';
import '@/shared/design/french.css';
import '../post.css';
import './deadlines.css';

/**
 * «15 يوما: الأجل المفضل في القانون المغربي» (the blog's twenty-third post): the four deadlines the law writes most as leaves
 * of a wall calendar, the first in front, a tap bringing another forward; every deadline on one scale of time from an hour
 * to decades; and the most frequent ones in the laws people meet, each with its article's words.
 */
type Row = DeadlinesPost['figures']['deadlines'][number];

export default function Deadlines({ post }: { post: DeadlinesPost }) {
  const { t, i18n } = useTranslation('blog');
  const lang = i18n.language;
  const rtl = lang !== 'fr';
  const rows = post.figures.deadlines;
  const keyOf = (r: Row) => `${r.unit}${r.n}`;
  const [front, setFront] = useState(0);
  const [picked, setPicked] = useState(keyOf(rows[0]));
  const [sharing, setSharing] = useState(false);
  const heroRef = useRef<HTMLElement>(null);

  /** «15 يوما», «6 أشهر», «شهران», «24 ساعة», «15 jours». */
  const said = (r: { unit: string; n: number }) => t(`deadlines.units.${r.unit}.${arabicKey(r.n)}`, { n: r.n });
  const times = (v: number) => t(`deadlines.times.${arabicKey(v)}`, { n: n(v, lang) });
  const lawName = (akn: string) => t(`deadlines.laws.${akn.split('/').pop()}`);
  const art = (eid: string) => eid.replace('art_', '').replace('-bis', ' مكرر');
  const top4 = rows.slice(0, 4);
  const lead = top4[front];
  const pickedRow = rows.find((r) => keyOf(r) === picked)!;
  const ticks = [
    { days: 1 / 24, label: t('deadlines.ticks.hour') }, { days: 1, label: t('deadlines.ticks.day') }, { days: 7, label: t('deadlines.ticks.week') },
    { days: 30.4375, label: t('deadlines.ticks.month') }, { days: 365.25, label: t('deadlines.ticks.year') }, { days: 3652.5, label: t('deadlines.ticks.decade') },
  ];

  const example = (r: Row) => (r.example ? (
    <>
      <blockquote className="dl-quote" lang="ar" dir="rtl">«{r.example.words}»</blockquote>
      <p className="dl-src"><Link to={r.example.path}>{t('deadlines.where', { law: lawName(r.example.akn), art: art(r.example.eid) })}</Link></p>
    </>
  ) : <p className="dl-src">{t('deadlines.noExample')}</p>);

  const doShare = async () => {
    if (!heroRef.current) return;
    setSharing(true);
    try {
      await shareLeaves(heroRef.current, {
        dir: rtl ? 'rtl' : 'ltr', over: `${t('name')} ${t('number', { n: post.number })}`, title: post.title[rtl ? 'ar' : 'fr'],
        leaves: top4.map((r) => ({ n: r.n, unit: t(`deadlines.leafUnit.${r.unit}.${arabicKey(r.n)}`), times: times(r.count) })),
        source: t('deadlines.share.source', { total: n(post.figures.total, lang) }), site: t('deadlines.share.site'),
      });
    } finally { setSharing(false); }
  };

  return (
    <article className="bp dl" lang={lang}>
      <Head post={post} />

      <figure className="dl-hero" ref={heroRef} aria-labelledby="dl-hero-q">
        <p className="dl-q" id="dl-hero-q">{t('deadlines.hero.q')}</p>
        <div className="dl-hero-grid">
          <div className="dl-pad" role="radiogroup" aria-label={t('deadlines.hero.pick')}>
            {top4.map((r, i) => {
              const depth = (i - front + 4) % 4;
              return (
                <button key={keyOf(r)} type="button" role="radio" aria-checked={i === front} className="dl-leaf" style={{ '--depth': depth } as CSSProperties}
                        onClick={() => setFront(i)} aria-label={`${said(r)}: ${times(r.count)}`}>
                  <span className="dl-leaf-rings" aria-hidden="true"><i /><i /><i /></span>
                  <span className="dl-leaf-rank">{t('deadlines.rank', { n: i + 1 })}</span>
                  <span className="dl-leaf-n">{r.n}</span>
                  <span className="dl-leaf-unit">{t(`deadlines.leafUnit.${r.unit}.${arabicKey(r.n)}`)}</span>
                  <span className="dl-leaf-times">{times(r.count)}</span>
                </button>
              );
            })}
          </div>
          <div className="dl-hero-words" aria-live="polite">
            <p className="dl-say">{t(front ? 'deadlines.hero.other' : 'deadlines.hero.first', { said: said(lead), times: front ? times(lead.count) : n(lead.count, lang), total: n(post.figures.total, lang) })}</p>
            {example(lead)}
          </div>
        </div>
        <div className="dl-share-row">
          <button type="button" className="dl-share" disabled={sharing} onClick={doShare}>
            <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 3v12" /><path d="m7 8 5-5 5 5" /><path d="M5 14v5a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-5" /></svg>
            {t('deadlines.hero.share')}
          </button>
        </div>
      </figure>

      <section className="bp-sec" aria-labelledby="dl-s1">
        <h2 id="dl-s1">{t('deadlines.scale.h')}</h2>
        <p className="bp-p">{t('deadlines.scale.p1', { total: n(post.figures.total, lang), kinds: rows.length })}</p>
        <Figure id="dl-scale" q={t('deadlines.scale.q')} unit={t('deadlines.scale.unit')} wide so={t('deadlines.scale.so')}
                source={t('deadlines.scale.source')}
                pick={<>{t('deadlines.scale.pick', { said: said(pickedRow), times: times(pickedRow.count) })}{pickedRow.example ? <> <Link to={pickedRow.example.path}>{t('deadlines.where', { law: lawName(pickedRow.example.akn), art: art(pickedRow.example.eid) })}</Link></> : null}</>}>
          <Scale deadlines={rows.map((r) => ({ key: keyOf(r), days: r.days, count: r.count, label: said(r) }))} picked={picked} onPick={setPicked}
                 ticks={ticks} aria={t('deadlines.scale.aria')} rtl={rtl} />
        </Figure>
      </section>

      <section className="bp-sec" aria-labelledby="dl-s2">
        <h2 id="dl-s2">{t('deadlines.list.h')}</h2>
        <p className="bp-p">{t('deadlines.list.p1')}</p>
        <ol className="dl-list">
          {rows.filter((r) => r.example).slice(0, 12).map((r) => (
            <li key={keyOf(r)}>
              <p className="dl-list-head"><b>{said(r)}</b><span className="dl-bar" style={{ inlineSize: `${(r.count / rows[0].count) * 100}%` }} aria-hidden="true" />
                <span className="dl-list-times">{times(r.count)}</span></p>
              {example(r)}
            </li>
          ))}
        </ol>
      </section>

      <section className="bp-method" aria-labelledby="dl-method">
        <h2 id="dl-method">{t('deadlines.method.h')}</h2>
        <ul>
          {(['what', 'words', 'left', 'examples', 'check'] as const).map((k) => <li key={k}>{t(`deadlines.method.${k}`)}</li>)}
          <li>{t('deadlines.method.on', { on: day(post.counted_on, lang) })}</li>
        </ul>
      </section>
    </article>
  );
}
