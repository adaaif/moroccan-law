import { useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { Stamp } from '@/features/corpus/article/Stamp';
import type { SpeedPost } from '../blog.api';
import { Head } from '../Head';
import { Figure } from '../kit';
import { day } from '../clock/names';
import { n } from '../viz';
import { Dial } from './Dial';
import { Orders } from './Orders';
import { shareDial } from './share';
import '@/shared/design/french.css';
import '../post.css';
import './speed.css';

/**
 * «السرعة في الجريدة الرسمية» (the blog's twenty-second post): a speedometer whose needle moves to each speed the Bulletin
 * wrote for a road, year by year from the cars its 1913 news pages timed to the 2010 code, each with its words and its
 * page; the ministers' orders that set a limit section by section, one dot an order; and the limits since 2010 as the
 * road's own signs, each opening its article.
 */
export default function Speed({ post }: { post: SpeedPost }) {
  const { t, i18n } = useTranslation('blog');
  const lang = i18n.language;
  const rtl = lang !== 'fr';
  const fig = post.figures;
  const tx = fig.texts;
  const [key, setKey] = useState('y1924');
  const [sharing, setSharing] = useState(false);
  const heroRef = useRef<HTMLElement>(null);
  const era = post.eras.find((e) => e.key === key)!;
  const all = [...new Set(post.eras.flatMap((e) => [e.kmh, ...(e.marks ?? [])]))].sort((a, b) => a - b);

  const stamp = (k: string) => {
    const f = tx[k];
    if (!f?.viewer) return null;
    const fr = f.edition === 'translation_fr';
    return <Stamp issue={`${f.issue.replace(' bis', rtl ? ' مكرر' : ' bis')}${fr ? (rtl ? ' (النشرة الفرنسية)' : ' (édition française)') : ''}`} page={f.page} to={f.viewer} className="sp-stamp" />;
  };
  const step = (by: number) => {
    const i = post.eras.findIndex((e) => e.key === key);
    setKey(post.eras[Math.min(post.eras.length - 1, Math.max(0, i + by))].key);
  };
  const orders = fig.orders;
  const sixty = orders.filter((o) => o.kmh === 60).length;

  const doShare = async () => {
    if (!heroRef.current) return;
    setSharing(true);
    try {
      await shareDial(heroRef.current, {
        dir: rtl ? 'rtl' : 'ltr', over: `${t('name')} ${t('number', { n: post.number })}`, title: t('speed.share.title'),
        eras: post.eras.map((e) => ({ year: e.year, kmh: e.kmh })), unit: t('speed.unitShort'), source: t('speed.share.source'), site: t('speed.share.site'),
      });
    } finally { setSharing(false); }
  };

  return (
    <article className="bp sp" lang={lang}>
      <Head post={post} />

      <figure className="sp-hero" ref={heroRef} aria-labelledby="sp-hero-q">
        <p className="sp-q" id="sp-hero-q">{t('speed.hero.q')}</p>
        <div className="sp-hero-grid">
          <div className="sp-instrument">
            <Dial kmh={era.kmh} others={all} year={era.year} unit={t('speed.unitShort')} aria={t('speed.hero.aria', { year: era.year, kmh: era.kmh })} />
          <div className="sp-years" role="radiogroup" aria-label={t('speed.hero.pick')}
               onKeyDown={(e) => { if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') { e.preventDefault(); step((e.key === 'ArrowRight') === !rtl ? 1 : -1); } }}>
            {post.eras.map((e) => (
              <button key={e.key} type="button" role="radio" aria-checked={key === e.key} tabIndex={key === e.key ? 0 : -1}
                      className={key === e.key ? 'is-on' : ''} onClick={() => setKey(e.key)}>
                <b>{e.year}</b><span>{e.kmh}</span>
              </button>
            ))}
          </div>
          </div>
          <div className="sp-era" aria-live="polite">
            <p className="sp-era-head"><span className={`sp-kind is-${era.kind}`}>{t(`speed.kind.${era.kind}`)}</span> {tx[era.key] ? day(tx[era.key].published, lang) : era.year}</p>
            <p className="sp-era-say">{t(`speed.eras.${era.key}`)}</p>
            <blockquote className="sp-quote" lang={era.edition === 'fr' ? 'fr' : 'ar'} dir={era.edition === 'fr' ? 'ltr' : 'rtl'}>«{era.words}»</blockquote>
            {era.edition === 'fr' && rtl ? <p className="sp-gloss">{t('speed.gloss1924')}</p> : null}
            {era.marks ? <p className="sp-marks">{t(`speed.marks.${era.key}`)}</p> : null}
            <p className="sp-src">{tx[era.key]?.path ? <Link to={tx[era.key].path!}>{t('speed.openText')}</Link> : null} {stamp(era.key)}</p>
          </div>
        </div>
        <div className="sp-share-row">
          <button type="button" className="sp-share" disabled={sharing} onClick={doShare}>
            <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 3v12" /><path d="m7 8 5-5 5 5" /><path d="M5 14v5a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-5" /></svg>
            {t('speed.hero.share')}
          </button>
        </div>
      </figure>

      <section className="bp-sec" aria-labelledby="sp-s1">
        <h2 id="sp-s1">{t('speed.first.h')}</h2>
        <p className="bp-p">{t('speed.first.p1')}</p>
        <blockquote className="sp-quote" lang="ar" dir="rtl">«{post.first_rule.words}»</blockquote>
        <p className="sp-src">{tx.first ? day(tx.first.published, lang) : null} {stamp('first')}</p>
        <p className="bp-p">{t('speed.first.p2')}</p>
      </section>

      <section className="bp-sec" aria-labelledby="sp-s2">
        <h2 id="sp-s2">{t('speed.orders.h')}</h2>
        <p className="bp-p">{t('speed.orders.p1', { n: n(orders.length, lang) })}</p>
        <Figure id="sp-orders" q={t('speed.orders.q')} unit={t('speed.orders.unit')} wide
                so={t('speed.orders.so', { sixty, n: orders.length })}
                source={t('fig.source', { from: post.orders.from, to: post.orders.to })}>
          <Orders orders={orders} from={post.orders.from} to={post.orders.to} aria={t('speed.orders.aria', { n: orders.length, sixty })} />
        </Figure>
      </section>

      <section className="bp-sec" aria-labelledby="sp-s3">
        <h2 id="sp-s3">{t('speed.today.h')}</h2>
        <p className="bp-p">{t('speed.today.p1')}</p>
        <ul className="sp-signs">
          {post.today.map((s) => (
            <li key={s.key}>
              <span className="sp-sign" aria-hidden="true"><b>{s.kmh}</b></span>
              <span className="sp-sign-words">{t(`speed.today.${s.key}`)}</span>
              <span className="sp-sign-src">
                {tx[`t-${s.key}`]?.path ? <Link to={`${tx[`t-${s.key}`].path}/art_${s.art}`}>{t('speed.today.art', { n: s.art })}</Link> : t('speed.today.art', { n: s.art })}
              </span>
            </li>
          ))}
        </ul>
        <p className="sp-src">{t('speed.today.source', { number: rtl ? post.code.number : post.code.number.replace(/\./g, '-') })} {stamp('t-town')} {stamp('t-motorway')}</p>
        <p className="sp-note">{t('speed.today.note')} <Link to="/topics/road">{t('speed.today.roadTopic')}</Link></p>
      </section>

      <section className="bp-method" aria-labelledby="sp-method">
        <h2 id="sp-method">{t('speed.method.h')}</h2>
        <ul>
          {(['eras', 'orders', 'today', 'check'] as const).map((k) => <li key={k}>{t(`speed.method.${k}`)}</li>)}
          <li>{t('speed.method.on', { on: day(post.counted_on, lang) })}</li>
        </ul>
      </section>
    </article>
  );
}
