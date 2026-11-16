import { useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { Stamp } from '@/features/corpus/article/Stamp';
import type { WhatsappPost } from '../blog.api';
import { Head } from '../Head';
import { Figure } from '../kit';
import { Print } from '../Print';
import { day } from '../clock/names';
import { n } from '../viz';
import { Decades } from './Decades';
import { Mediator } from './Mediator';
import { Pictogram, Screens } from './Screens';
import { passed, textsKey } from './screens';
import { shareScreens } from './share';
import '@/shared/design/french.css';
import '../post.css';
import './absent.css';

/**
 * «القانون يعرف البرقية، ولا يعرف واتساب» (the blog's nineteenth post): two home screens, the law's machines with the texts
 * that still write them and the Moroccans' networks with the none that name them; each machine's decades and its last
 * text; how the networks came into the Bulletin, page by page, two of them cut from their pages; what reached the
 * Mediator by fax and by WhatsApp; and how the law writes them without naming them. Every count is figures.json's, every
 * quote the meta's, read on its page.
 */
export default function Absent({ post }: { post: WhatsappPost }) {
  const { t, i18n } = useTranslation('blog');
  const lang = i18n.language;
  const rtl = lang !== 'fr';
  const fig = post.figures;
  const tx = fig.texts;
  const [year, setYear] = useState(2023);
  const [sharing, setSharing] = useState(false);
  const heroRef = useRef<HTMLElement>(null);

  /** «1.199 نصا», «نصان», «210 textes». */
  const texts = (v: number) => t(`whatsapp.texts.${textsKey(v)}`, { n: n(v, lang) });
  const name = (o: { ar: string; fr: string }) => (rtl ? o.ar : o.fr);
  const stamp = (key: string) => {
    const f = tx[key];
    return f?.viewer ? <Stamp issue={f.issue.replace(' bis', rtl ? ' مكرر' : ' bis')} page={f.page} to={f.viewer} className="wa-stamp" /> : null;
  };
  const count = (k: string) => fig.machines.find((m) => m.key === k) ?? fig.generics.find((m) => m.key === k)!;
  const app = (k: string) => fig.apps.find((a) => a.key === k)!;
  const telegram = count('telegram');

  const screens = {
    machines: post.machines.map((m) => ({ key: m.key, name: name(m), standing: count(m.key).standing })),
    apps: post.apps.filter((a) => a.pct).map((a) => ({ key: a.key, name: name(a), pct: a.pct!, texts: app(a.key).texts })),
  };
  const none = screens.apps.every((a) => a.texts === 0) ? 0 : screens.apps.reduce((s, a) => s + a.texts, 0);

  const doShare = async () => {
    if (!heroRef.current) return;
    setSharing(true);
    try {
      await shareScreens(heroRef.current, {
        dir: rtl ? 'rtl' : 'ltr', over: `${t('name')} ${t('number', { n: post.number })}`, title: t('whatsapp.share.title'),
        law: t('whatsapp.hero.law'), people: t('whatsapp.hero.people'), machines: screens.machines.map((m) => ({ ...m, shown: n(m.standing, lang) })),
        apps: screens.apps.map((a) => ({ name: a.name, pct: a.pct, shown: n(a.texts, lang) })), lang,
        zero: String(none), zeroWords: t('whatsapp.hero.zeroWords'), source: t('whatsapp.share.source'), site: t('whatsapp.share.site'),
      });
    } finally { setSharing(false); }
  };

  // The firsts, one row a page: Facebook and YouTube share the CESE's 2015 page, Messenger and Pinterest its 2024 table.
  const rows: { keys: string[]; first: WhatsappPost['apps'][number]['first'] }[] = [];
  for (const a of [...post.apps].sort((x, y) => x.first.date!.localeCompare(y.first.date!))) {
    const same = rows.find((r) => r.first.issue === a.first.issue && r.first.page === a.first.page);
    if (same) same.keys.push(a.key); else rows.push({ keys: [a.key], first: a.first });
  }
  const clip = (k: string) => post.clippings.find((c) => c.key === k);
  const kinds = ['opinion', 'report', 'quote'] as const;

  const med = post.mediator.years;
  const pickedYear = med.find((d) => d.year === year)!;
  const passedAt = passed(med.map((d) => ({ year: d.year, a: d.fax, b: d.whatsapp })));
  const formula = post.naming.formula;
  const times = fig.formula;

  return (
    <article className="bp wa" lang={lang}>
      <Head post={post} />

      <figure className="wa-hero" ref={heroRef} aria-label={t('whatsapp.share.title')}>
        <Screens machines={screens.machines} apps={screens.apps}
                 labels={{ law: t('whatsapp.hero.law'), people: t('whatsapp.hero.people'), lawNote: t('whatsapp.hero.lawNote'), peopleNote: t('whatsapp.hero.peopleNote') }} />
        <div className="wa-zero">
          <p className="wa-zero-line"><span className="wa-zero-n">{n(none, lang)}</span><span className="wa-zero-words">{t('whatsapp.hero.zeroWords')}</span></p>
          <p className="wa-zero-more">{t('whatsapp.hero.zeroMore', { n: texts(telegram.standing) })}</p>
          <p className="wa-zero-src">{t('whatsapp.hero.source')} {stamp('cese')}</p>
        </div>
        <div className="wa-share-row">
          <button type="button" className="wa-share" disabled={sharing} onClick={doShare}>
            <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 3v12" /><path d="m7 8 5-5 5 5" /><path d="M5 14v5a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-5" /></svg>
            {t('whatsapp.hero.share')}
          </button>
        </div>
      </figure>

      <section className="bp-sec" aria-labelledby="wa-s1">
        <h2 id="wa-s1">{t('whatsapp.machines.h')}</h2>
        <p className="bp-p">{t('whatsapp.machines.p1')}</p>
        <ul className="wa-machines">
          {post.machines.map((m) => {
            const c = count(m.key);
            const ex = m.example;
            const kind = ex.akn?.includes('/loi/') ? 'law' : ex.akn?.includes('/decret/') ? 'decree' : 'dahir';
            const to = fig.articles[`m-${m.key}`] ?? tx[`m-${m.key}`]?.path;
            const textName = t(`whatsapp.machines.text.${kind}`, { number: rtl ? ex.number : ex.number.replace(/\./g, '-'), art: ex.art });
            return (
              <li key={m.key} className="wa-machine">
                <div className="wa-machine-head">
                  <span className="wa-machine-icon" aria-hidden="true"><Pictogram k={m.key} /></span>
                  <h3 className="wa-machine-name">{name(m)}</h3>
                  <p className="wa-machine-n"><span className="wa-machine-num">{n(c.standing, lang)}</span>
                    <span className="wa-machine-unit">{t(`whatsapp.machines.standing.${textsKey(c.standing)}`)}</span></p>
                </div>
                <Decades decades={fig.decades} counts={c.decades} aria={t('whatsapp.machines.aria', { name: name(m) })} />
                <p className="wa-machine-ex">{t(`whatsapp.machines.example.${m.key}`)}</p>
                <blockquote className="wa-quote" lang="ar" dir="rtl">«{ex.words}»</blockquote>
                {lang === 'fr' ? <p className="wa-gloss">{t(`whatsapp.machines.gloss.${m.key}`)}</p> : null}
                <p className="wa-machine-src">{to ? <Link to={to}>{textName}</Link> : textName} · {day(ex.date!, lang)} {stamp(`m-${m.key}`)}</p>
              </li>
            );
          })}
        </ul>
        <p className="wa-note">{t('whatsapp.machines.note')}</p>
      </section>

      <section className="bp-sec" aria-labelledby="wa-s2">
        <h2 id="wa-s2">{t('whatsapp.firsts.h')}</h2>
        <p className="bp-p">{t('whatsapp.firsts.p1')}</p>
        <ul className="wa-kinds" aria-hidden="true">
          {kinds.map((k) => <li key={k}><i className={`wa-k is-${k}`} />{t(`whatsapp.firsts.kinds.${k}`)}</li>)}
        </ul>
        <ol className="wa-firsts">
          {rows.map((r) => {
            const lead = r.keys[0];
            const c = r.keys.map((k) => clip(k)).find(Boolean);
            const v = c ? tx[`c-${c.key}`] : null;
            const words = post.words[lead];
            return (
              <li key={lead} className={`wa-first is-${r.first.kind}`}>
                <span className="wa-first-day">{day(r.first.date!, lang)}</span>
                <div className="wa-first-body">
                  <p className="wa-first-names">
                    {r.keys.map((k, i) => <span key={k}>{i ? t('whatsapp.firsts.and') : ''}<b dir="auto">{name(post.apps.find((a) => a.key === k)!)}</b></span>)}
                    <span className="wa-first-kind">{t(`whatsapp.firsts.kinds.${r.first.kind}`)}</span>
                  </p>
                  <p className="wa-first-what">{t(`whatsapp.firsts.what.${lead === 'youtube' ? 'facebook' : lead === 'pinterest' ? 'messenger' : lead}`, { number: clip('whatsapp')?.number })} {stamp(`a-${lead}`)}</p>
                  {c && v?.viewer ? (
                    <>
                      <Print viewer={v.viewer} crop={c.crop} alt={t('whatsapp.firsts.alt', { words: c.words, page: c.page, issue: v.issue })} />
                      {lang === 'fr' ? <p className="wa-gloss">{t(`whatsapp.firsts.gloss.${c.key}`)}</p> : null}
                    </>
                  ) : words ? <blockquote className="wa-quote is-small" lang="ar" dir="rtl">«{words}»</blockquote> : null}
                </div>
              </li>
            );
          })}
        </ol>
        <p className="wa-note">{t('whatsapp.firsts.telegraph', { words: post.telegraph.words })} {stamp('telegraph')}</p>
      </section>

      <section className="bp-sec" aria-labelledby="wa-s3">
        <h2 id="wa-s3">{t('whatsapp.mediator.h')}</h2>
        <p className="bp-p">{t('whatsapp.mediator.p1')}</p>
        <Figure id="wa-med" q={t('whatsapp.mediator.q')} unit={t('whatsapp.mediator.unit')} so={t('whatsapp.mediator.so')} source={t('whatsapp.mediator.source')}
                pick={<>{t(pickedYear.whatsapp === undefined ? 'whatsapp.mediator.pickNoWa' : pickedYear.files ? 'whatsapp.mediator.pickFiles' : 'whatsapp.mediator.pick', {
                  year: pickedYear.year, fax: n(pickedYear.fax, lang), wa: n(pickedYear.whatsapp ?? 0, lang), total: n(pickedYear.total, lang) })}{' '}
                  {stamp(`r-${pickedYear.year >= 2024 ? 2024 : 2023}`)}</>}>
          <Mediator years={med} picked={year} onPick={setYear} passed={passedAt}
                    labels={{ fax: t('whatsapp.mediator.fax'), whatsapp: t('whatsapp.mediator.whatsapp'), passed: t('whatsapp.mediator.passed') }}
                    aria={t('whatsapp.mediator.aria')} />
        </Figure>
      </section>

      <section className="bp-sec" aria-labelledby="wa-s4">
        <h2 id="wa-s4">{t('whatsapp.naming.h')}</h2>
        <p className="bp-p">{t('whatsapp.naming.p1', { times: t(`whatsapp.naming.times.${textsKey(times)}`, { n: times }) })}</p>
        <figure className="wa-formula" lang="ar" dir="rtl">
          <ol>
            {formula.parts.map((p, i) => <li key={p}><span className="wa-or">{i === 0 ? 'بما في ذلك' : 'أو'}</span> {p}</li>)}
          </ol>
          <figcaption>
            {fig.articles['n-formula'] ? <Link to={fig.articles['n-formula']}>{rtl ? `القانون التنظيمي ${formula.number}` : `loi organique ${formula.number.replace('.', '-')}`}</Link> : null}
            {' '}{stamp('n-formula')}
          </figcaption>
        </figure>
        {lang === 'fr' ? <p className="wa-gloss">{t('whatsapp.naming.gloss')}</p> : null}
        <p className="bp-p">{t('whatsapp.naming.p2')}</p>
        <blockquote className="wa-quote" lang="ar" dir="rtl">«{post.naming.group.words}»</blockquote>
        <p className="wa-machine-src">{fig.articles['n-group'] ? <Link to={fig.articles['n-group']}>{rtl ? `القرار ${post.naming.group.number}` : `décision ${post.naming.group.number}`}</Link> : null} {stamp('n-group')}</p>
        <p className="bp-p">{t('whatsapp.naming.p3')}</p>
        <blockquote className="wa-quote" lang="ar" dir="rtl">«{post.naming.doctor.words}»</blockquote>
        <p className="wa-machine-src">{fig.articles['n-doctor'] ? <Link to={fig.articles['n-doctor']}>{rtl ? `المرسوم ${post.naming.doctor.number}، المادة 26` : `décret ${post.naming.doctor.number.replace(/\./g, '-')}, article 26`}</Link> : null} {stamp('n-doctor')}</p>
        <p className="bp-p">{t('whatsapp.naming.generics', { internet: texts(count('internet').standing), email: texts(count('email').standing), social: texts(count('social').standing) })}</p>
        <p className="bp-p">{t('whatsapp.naming.council')}</p>
        <blockquote className="wa-quote" lang="ar" dir="rtl">«{post.naming.council.words}»</blockquote>
        <p className="wa-machine-src">{stamp('n-council')}</p>
        <p className="bp-p wa-close">{t('whatsapp.naming.close')}</p>
      </section>

      <section className="bp-method" aria-labelledby="wa-method">
        <h2 id="wa-method">{t('whatsapp.method.h')}</h2>
        <ul>
          {(['rules', 'forms', 'left', 'pages', 'check'] as const).map((k) => <li key={k}>{t(`whatsapp.method.${k}`)}</li>)}
          <li>{t('whatsapp.method.on', { on: day(post.counted_on, lang) })}</li>
        </ul>
      </section>
    </article>
  );
}
