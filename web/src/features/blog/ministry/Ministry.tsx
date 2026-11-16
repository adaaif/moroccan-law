import { useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import type { MinistryPost } from '../blog.api';
import { Head } from '../Head';
import { Figure, Table } from '../kit';
import { day } from '../clock/names';
import { n, useWidth } from '../viz';
import { shareNames } from './share';
import { strand } from './strands';
import '@/shared/design/french.css';
import '../post.css';
import './ministry.css';

/**
 * «وزارة التعليم: 24 اسما» (the blog's twenty-sixth post): every name the education portfolio signed under, as letterheads
 * on one line of years, left to right on every page: each name its bar from the first to the last year a text carries it,
 * coloured by strand (the schools violet, higher education ochre, both at once in ink), the longest one set apart.
 */
const FROM = 1956, TO = 2026;

export default function Ministry({ post }: { post: MinistryPost }) {
  const { t, i18n } = useTranslation('blog');
  const lang = i18n.language;
  const rtl = lang !== 'fr';
  const fig = post.figures;
  const [ref, width] = useWidth<HTMLDivElement>(640);
  const x = (yr: number) => ((yr - FROM) / (TO + 1 - FROM)) * 100;
  const ticks = [1960, 1980, 2000, 2020];
  const merged = fig.names.filter((nm) => strand(nm.name) === 'both');
  const key = (v: number) => (v === 1 ? 'one' : v === 2 ? 'two' : v % 100 >= 3 && v % 100 <= 10 ? 'few' : 'many');
  const [sharing, setSharing] = useState(false);
  const heroRef = useRef<HTMLElement>(null);
  const longestN = fig.longest.length + t('ministry.hero.ministry').length + 1;
  const doShare = async () => {
    if (!heroRef.current) return;
    setSharing(true);
    try {
      await shareNames(heroRef.current, {
        dir: rtl ? 'rtl' : 'ltr', over: `${t('name')} ${t('number', { n: post.number })}`, title: post.title[rtl ? 'ar' : 'fr'],
        longest: `${t('ministry.hero.ministry')} ${fig.longest}`, note: t('ministry.hero.longest', { n: longestN }),
        names: fig.names.map((nm) => ({ name: nm.name, from: nm.from, to: nm.to, strand: strand(nm.name) })), from: FROM, to: TO,
        legend: { school: t('ministry.strands.school'), higher: t('ministry.strands.higher'), both: t('ministry.strands.both') },
        source: t('ministry.share.source'), site: t('ministry.share.site'),
      });
    } finally { setSharing(false); }
  };
  return (
    <article className="bp mn" lang={lang}>
      <Head post={post} />

      <section className="mn-hero" ref={heroRef} aria-labelledby="mn-hero-q">
        <p className="mn-q" id="mn-hero-q">{t('ministry.hero.q')}</p>
        <p className="mn-longest" lang="ar" dir="rtl">«{t('ministry.hero.ministry')} {fig.longest}»</p>
        <p className="mn-longest-note">{t('ministry.hero.longest', { n: longestN })}</p>
        <div className="mn-share-row">
          <button type="button" className="mn-share" disabled={sharing} onClick={doShare}>
            <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 3v12" /><path d="m7 8 5-5 5 5" /><path d="M5 14v5a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-5" /></svg>
            {t('ministry.hero.share')}
          </button>
        </div>
      </section>

      <section className="bp-sec" aria-labelledby="mn-s1">
        <h2 id="mn-s1">{t('ministry.names.h', { n: fig.names.length })}</h2>
        <p className="bp-p">{t('ministry.names.p1', { texts: n(fig.texts, lang) })}</p>
        <Figure id="mn-names" q={t('ministry.names.q')} unit={t('ministry.names.unit')} wide so={t('ministry.names.so', { merged: t(`ministry.names.times.${key(merged.length)}`, { n: merged.length }) })}
                source={t('fig.source', { from: FROM, to: TO })}
                table={<Table head={[t('ministry.names.name'), t('ministry.names.from'), t('ministry.names.to'), t('ministry.names.texts')]}
                              rows={fig.names.map((nm) => [nm.name, nm.from, nm.to, nm.texts])} />}>
          <ul className="mn-legend">
            {(['school', 'higher', 'both'] as const).map((k) => <li key={k}><i className={`is-${k}`} />{t(`ministry.strands.${k}`)}</li>)}
          </ul>
          <div ref={ref} className={`mn-heads${width < 560 ? ' is-phone' : ''}`}>
            {fig.names.map((nm) => (
              <div key={`${nm.name}-${nm.from}`} className={`mn-head is-${strand(nm.name)}${nm.name === fig.longest ? ' is-longest' : ''}`}>
                <p className="mn-name" lang="ar" dir="rtl">{nm.name}</p>
                <div className="mn-track" dir="ltr" aria-hidden="true">
                  <span className="mn-bar" style={{ left: `${x(nm.from)}%`, width: `${Math.max(1.2, x(nm.to + 1) - x(nm.from))}%` }} />
                </div>
                <p className="mn-years" dir="ltr">{nm.from === nm.to ? nm.from : `${nm.from}–${nm.to}`} · <span dir={rtl ? 'rtl' : 'ltr'}>{t(`ministry.names.count.${key(nm.texts)}`, { n: n(nm.texts, lang) })}</span></p>
              </div>
            ))}
            <div className="mn-head mn-axis-row" aria-hidden="true">
              <span />
              <div className="mn-axis" dir="ltr">{ticks.map((tk) => <span key={tk} style={{ left: `${x(tk)}%` }}>{tk}</span>)}</div>
              <span />
            </div>
          </div>
        </Figure>
        <p className="bp-p">{t('ministry.names.p2')}</p>
      </section>

      <section className="bp-method" aria-labelledby="mn-method">
        <h2 id="mn-method">{t('ministry.method.h')}</h2>
        <ul>
          {(['which', 'fold', 'left', 'generic'] as const).map((k) => <li key={k}>{t(`ministry.method.${k}`)}</li>)}
          <li>{t('ministry.method.on', { on: day(post.counted_on, lang) })}</li>
        </ul>
      </section>
    </article>
  );
}
