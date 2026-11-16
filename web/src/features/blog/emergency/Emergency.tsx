import { useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { Stamp } from '@/features/corpus/article/Stamp';
import type { EmergencyPost } from '../blog.api';
import { Head } from '../Head';
import { Figure } from '../kit';
import { monthNames, n } from '../viz';
import { day as dayName } from '../clock/names';
import { Calendar } from './Calendar';
import { days } from './calendar';
import { shareCalendar } from './share';
import '@/shared/design/french.css';
import '../post.css';
import './emergency.css';

/**
 * «حالة الطوارئ الصحية» (the blog's twenty-seventh post, for March 2027): the declaration and the 33 decrees that extended
 * the emergency, as bands on a wall calendar of three years; the fine and the 300-dirham settlement as printed; and the
 * decree-law that stays, ratified, as the frame of any emergency to come.
 */
export default function Emergency({ post }: { post: EmergencyPost }) {
  const { t, i18n } = useTranslation('blog');
  const lang = i18n.language;
  const rtl = lang !== 'fr';
  const fig = post.figures;
  const tx = fig.texts;
  const start = '2020-03-24';
  const terms = [
    { key: 'declaration', from: start, to: fig.declared_until, kind: 'declared' as const, number: post.declaration.number, printed: tx.declaration?.published ?? '' },
    ...fig.terms.map((tm, i) => ({ key: tm.key, from: i ? fig.terms[i - 1].until : fig.declared_until, to: tm.until, kind: tm.changes ? 'changed' as const : 'extended' as const, number: tm.number, printed: tm.printed })),
  ];
  const last = fig.terms[fig.terms.length - 1];
  const [picked, setPicked] = useState(terms[1].key);
  const pick = terms.find((tm) => tm.key === picked)!;
  const stamp = (key: string) => {
    const f = tx[key];
    return f?.viewer ? <Stamp issue={f.issue.replace(' bis', rtl ? ' مكرر' : ' bis')} page={f.page} to={f.viewer} className="em-stamp" /> : null;
  };
  const total = days(start, last.until);
  const months = monthNames(lang, 'short');
  const num = (v: string) => (rtl ? v : v.replace(/\./g, '-'));
  const [sharing, setSharing] = useState(false);
  const heroRef = useRef<HTMLElement>(null);
  const doShare = async () => {
    if (!heroRef.current) return;
    setSharing(true);
    try {
      await shareCalendar(heroRef.current, {
        dir: rtl ? 'rtl' : 'ltr', over: `${t('name')} ${t('number', { n: post.number })}`, title: post.title[rtl ? 'ar' : 'fr'],
        facts: [
          { n: n(total, lang), label: t('emergency.hero.days', { from: dayName(start, lang), to: dayName(last.until, lang) }) },
          { n: String(fig.terms.length), label: t('emergency.hero.decrees') },
          { n: '300', label: t('emergency.hero.fine') },
        ],
        terms, months,
        legend: { declared: t('emergency.cal.declared'), extended: t('emergency.cal.extended'), changed: t('emergency.cal.changed') }, so: t('emergency.cal.so'),
        source: t('emergency.share.source'), site: t('emergency.share.site'),
      });
    } finally { setSharing(false); }
  };
  return (
    <article className="bp em" lang={lang}>
      <Head post={post} />

      <section className="em-hero" ref={heroRef} aria-labelledby="em-hero-q">
        <p className="em-q" id="em-hero-q">{t('emergency.hero.q')}</p>
        <div className="em-facts">
          <p><b>{fig.terms.length}</b><span>{t('emergency.hero.decrees')}</span></p>
          <p><b>{n(total, lang)}</b><span>{t('emergency.hero.days', { from: dayName(start, lang), to: dayName(last.until, lang) })}</span></p>
          <p><b>300</b><span>{t('emergency.hero.fine')}</span></p>
        </div>
        <Figure id="em-cal" q={t('emergency.cal.q')} unit={t('emergency.cal.unit')} wide so={t('emergency.cal.so')}
                source={t('fig.source', { from: 2020, to: 2023 })}
                pick={<>{t(pick.kind === 'declared' ? 'emergency.cal.pickDeclared' : pick.kind === 'changed' ? 'emergency.cal.pickChanged' : 'emergency.cal.pick',
                  { number: num(pick.number), printed: pick.printed ? dayName(pick.printed, lang) : '', to: dayName(pick.to, lang) })} {stamp(pick.key)}</>}>
          <ul className="em-legend">
            <li><i className="is-declared" />{t('emergency.cal.declared')}</li>
            <li><i className="is-extended" />{t('emergency.cal.extended')}</li>
            <li><i className="is-changed" />{t('emergency.cal.changed')}</li>
          </ul>
          <Calendar terms={terms} months={months} picked={picked} onPick={setPicked}
                    label={(k) => { const x = terms.find((tm) => tm.key === k)!; return t('emergency.cal.label', { number: num(x.number), to: dayName(x.to, lang) }); }} />
        </Figure>
        <div className="em-share-row">
          <button type="button" className="em-share" disabled={sharing} onClick={doShare}>
            <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 3v12" /><path d="m7 8 5-5 5 5" /><path d="M5 14v5a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-5" /></svg>
            {t('emergency.hero.share')}
          </button>
        </div>
      </section>

      <section className="bp-sec" aria-labelledby="em-s1">
        <h2 id="em-s1">{t('emergency.fine.h')}</h2>
        <p className="bp-p">{t('emergency.fine.p1')}</p>
        <blockquote className="em-quote" lang="ar" dir="rtl">«{post.decree_law.art4}»</blockquote>
        <p className="em-src">{tx.decree_law?.path ? <Link to={`${tx.decree_law.path}/art_4`}>{t('emergency.fine.art4', { number: num(post.decree_law.number) })}</Link> : null} {stamp('decree_law')}</p>
        <p className="bp-p">{t('emergency.fine.p2')}</p>
        <blockquote className="em-quote" lang="ar" dir="rtl">«{post.settlement.words}»</blockquote>
        <p className="em-src">{tx.settlement?.path ? <Link to={tx.settlement.path}>{t('emergency.fine.settlement', { number: num(post.settlement.number) })}</Link> : null} {stamp('settlement')}</p>
        <p className="bp-p">{t('emergency.fine.p3')}</p>
        <blockquote className="em-quote is-small" lang="ar" dir="rtl">«{post.on_the_spot.words}»</blockquote>
        <p className="em-src">{tx.on_the_spot?.path ? <Link to={tx.on_the_spot.path}>{t('emergency.fine.spot', { number: num(post.on_the_spot.number) })}</Link> : null} {stamp('on_the_spot')}</p>
      </section>

      <section className="bp-sec" aria-labelledby="em-s2">
        <h2 id="em-s2">{t('emergency.stays.h')}</h2>
        <p className="bp-p">{t('emergency.stays.p1', { number: num(post.ratified.number) })} {stamp('ratified')}</p>
        <blockquote className="em-quote" lang="ar" dir="rtl">«{post.decree_law.art2}»</blockquote>
        <p className="em-src">{tx.decree_law?.path ? <Link to={`${tx.decree_law.path}/art_2`}>{t('emergency.stays.art2', { number: num(post.decree_law.number) })}</Link> : null}</p>
      </section>

      <section className="bp-method" aria-labelledby="em-method">
        <h2 id="em-method">{t('emergency.method.h')}</h2>
        <ul>
          {(['which', 'until', 'start', 'check'] as const).map((k) => <li key={k}>{t(`emergency.method.${k}`)}</li>)}
          <li>{t('emergency.method.on', { on: dayName(post.counted_on, lang) })}</li>
        </ul>
      </section>
    </article>
  );
}
