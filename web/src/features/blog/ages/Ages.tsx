import { type ReactNode, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { Stamp } from '@/features/corpus/article/Stamp';
import type { AgesItem, AgesPost } from '../blog.api';
import { Head } from '../Head';
import { Figure } from '../kit';
import { day } from '../clock/names';
import { byAge, holds, next, years } from './life';
import { Line } from './Line';
import { type Move, Moves } from './Moves';
import { shareAge } from './share';
import '@/shared/design/french.css';
import '../post.css';
import './ages.css';

const SHOWN = 5;

/**
 * «حياتك بأعمار القانون» (the blog's sixteenth post): the reader sets their age on the line of a life and the page says
 * what the law holds for them and what comes next; then every age the laws write, from birth to 65, on a ruler like the
 * door frame a family marks its children on; the seven ages that moved since 1957; the civil servant's retirement by
 * the year of birth. Each age is the meta's, read in its article; each opens its article and its printed page.
 */
export default function Ages({ post }: { post: AgesPost }) {
  const { t, i18n } = useTranslation('blog');
  const lang = i18n.language;
  const side = lang === 'fr' ? 'fr' : 'ar';
  const rtl = lang !== 'fr';
  const [age, setAge] = useState(17);
  const [all, setAll] = useState(false);
  const [sharing, setSharing] = useState(false);
  const heroRef = useRef<HTMLElement>(null);

  /** «17 سنة», «4 سنوات»: the count of years as Arabic writes it after a number (the plural from 3 to 10). */
  const unit = (n: number) => t(n % 100 >= 3 && n % 100 <= 10 ? 'ages.unit.few' : 'ages.unit.many');
  /** «بعد عام», «بعد عامين», «بعد 3 سنوات». */
  const inYears = (n: number) => t(n === 1 ? 'ages.in.one' : n === 2 ? 'ages.in.two' : n % 100 >= 3 && n % 100 <= 10 ? 'ages.in.few' : 'ages.in.many', { n });
  const lawAges = useMemo(() => [...new Set(post.ages.map((a) => a.age))].sort((a, b) => a - b), [post]);
  const groups = useMemo(() => byAge(post.ages), [post]);
  const real = post.ages.filter((a) => !a.echo);
  // What holds now: what the reader gained, the newest first (their last birthdays matter more than the first), then
  // what still shields them.
  const now = holds(post.ages, age).sort((a, b) => (a.side === b.side ? (a.side === 'start' ? b.age - a.age : a.age - b.age) : a.side === 'start' ? -1 : 1));
  const coming = next(post.ages, age);
  const at = (n: number) => real.filter((a) => a.age === n);

  /** A text named: its everyday name and its article, opening the article; and its printed page as a stamp. */
  const src = (key: string, law: string, art?: string, compact = false): ReactNode => {
    const f = post.figures.texts[key];
    const l = post.laws[law];
    const name = l ? l[side] : law;
    const article = l && art ? t(`ages.art.${l.art}`, { n: art }) : l?.art === 'single' ? t('ages.art.single') : null;
    const to = post.figures.articles[key] ?? f?.path ?? null;
    const words = article ? `${name}${lang === 'fr' ? ', ' : '، '}${article}` : name;
    const issue = f?.issue.replace(' bis', lang === 'fr' ? ' bis' : ' مكرر');
    return (
      <span className="ag-src">
        {to ? <Link to={to}>{words}</Link> : <span>{words}</span>}
        {f && !compact ? <>{' '}<Stamp issue={issue} page={f.page} to={f.viewer} className="ag-stamp" /></> : null}
      </span>
    );
  };
  /** What an age says, as a line: an end always after the age it holds until («قبل 18 …»), a start after the age it holds
   *  from only where the list is not already by age (`withAge`). */
  const lead = (a: AgesItem, withAge: boolean) => (a.side === 'end' ? t('ages.until', { age: a.age }) : withAge ? t('ages.since', { age: a.age }) : null);
  /** The words after a lead: in French a sentence's capital goes down after «Dès 16 ans,» (never an acronym's). */
  const after = (head: string | null, words: string) => (head && lang === 'fr' && /^[A-ZÀ-Ý][a-zà-ÿ’']/.test(words) ? words[0].toLowerCase() + words.slice(1) : words);
  const line = (a: AgesItem, withAge: boolean) => { const head = lead(a, withAge); return [head, after(head, a.text[side])].filter(Boolean).join(' '); };
  /** An age's line. On the ruler: its words, its article and its printed page. In the dial's lists (`compact`): its
   *  words and its article in a word; the pages are on the ruler. */
  const item = (a: AgesItem, compact = false, withAge = false) => {
    const head = lead(a, withAge);
    return (
      <li key={a.key} className={`ag-item is-${a.side}${compact ? ' is-compact' : ''}`}>
        <i className="ag-dot" aria-hidden="true" />
        <span className="ag-item-body">
          <span className="ag-item-text">{head ? <><b className="ag-item-age">{head}</b>{' '}</> : null}{after(head, a.text[side])}</span>
          {src(`a-${a.key}`, a.law, a.art, compact)}
        </span>
      </li>
    );
  };

  const moves: Move[] = post.moves.map((m) => {
    const first = m.steps[0].age, last = m.steps[m.steps.length - 1].age;
    const d = last - first;
    return {
      key: m.key, label: t(`ages.moves.rows.${m.key}`), change: t(d > 0 ? 'ages.moves.up' : 'ages.moves.down', { n: Math.abs(d), unit: unit(Math.abs(d)) }),
      steps: m.steps.map((s, i) => ({ age: s.age, year: s.year, viewer: post.figures.texts[`m-${m.key}-${i}`]?.viewer ?? null, source: src(`m-${m.key}-${i}`, s.law, s.art, true) })),
    };
  });

  const doShare = async () => {
    if (!heroRef.current) return;
    setSharing(true);
    try {
      await shareAge(heroRef.current, {
        dir: rtl ? 'rtl' : 'ltr', over: `${t('name')} ${t('number', { n: post.number })}`,
        title: t('ages.share.title', { age, unit: unit(age) }),
        lines: now.map((a) => line(a, true)),
        next: coming ? { head: t('ages.share.next', { in: inYears(coming.age - age), age: coming.age }), lines: coming.items.map((a) => line(a, false)) } : null,
        source: t('ages.share.source'), site: t('ages.share.site'), age,
      });
    } finally { setSharing(false); }
  };

  const before26 = real.filter((a) => a.age < 26).length;
  const retire = post.retire.steps;
  const halfWord = (n: number) => { const y = years(n); return y.half ? t('ages.retire.half', { n: y.whole }) : String(y.whole); };

  return (
    <article className="bp ag" lang={lang}>
      <Head post={post} />

      <figure className="ag-hero" ref={heroRef} aria-labelledby="ag-q">
        <p className="ag-q" id="ag-q">{t('ages.hero.q')}</p>
        <div className="ag-dial">
          <button type="button" className="ag-pm" onClick={() => setAge((a) => Math.max(0, a - 1))} aria-label={t('ages.hero.minus')}>−</button>
          <output className="ag-age" aria-live="polite"><span className="ag-age-num">{age}</span><span className="ag-age-unit">{unit(age)}</span></output>
          <button type="button" className="ag-pm" onClick={() => setAge((a) => Math.min(66, a + 1))} aria-label={t('ages.hero.plus')}>+</button>
        </div>
        <Line age={age} ages={lawAges} onAge={setAge} label={t('ages.hero.slider')} valueText={t('ages.hero.value', { age, unit: unit(age) })} />
        <p className="ag-how">{t('ages.hero.how')}</p>
        <div className="ag-now">
          <section className="ag-col" aria-labelledby="ag-now-h">
            <h2 id="ag-now-h">{t('ages.hero.now', { age, unit: unit(age) })}</h2>
            {now.length ? (
              <>
                <ul className="ag-list">{(all ? now : now.slice(0, SHOWN)).map((a) => item(a, true, true))}</ul>
                {now.length > SHOWN ? (
                  <button type="button" className="ag-more" aria-expanded={all} onClick={() => setAll((v) => !v)}>
                    {all ? t('ages.hero.less') : t('ages.hero.more', { n: now.length - SHOWN })}
                  </button>
                ) : null}
              </>
            ) : <p className="ag-none">{t('ages.hero.nowNone')}</p>}
          </section>
          <section className="ag-col is-next" aria-labelledby="ag-next-h">
            {coming ? (
              <>
                <h2 id="ag-next-h">{t('ages.hero.next', { in: inYears(coming.age - age), age: coming.age, unit: unit(coming.age) })}</h2>
                <ul className="ag-list">{coming.items.map((a) => item(a, true))}</ul>
              </>
            ) : <h2 id="ag-next-h">{t('ages.hero.nextNone')}</h2>}
          </section>
        </div>
        <div className="ag-share-row">
          <button type="button" className="ag-share" disabled={sharing} onClick={doShare}>
            <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 3v12" /><path d="m7 8 5-5 5 5" /><path d="M5 14v5a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-5" /></svg>
            {t('ages.hero.share')}
          </button>
        </div>
      </figure>

      <section className="bp-sec" aria-labelledby="ag-s1">
        <h2 id="ag-s1">{t('ages.ruler.h')}</h2>
        <p className="bp-p">{t('ages.ruler.p1', { before: before26 })}</p>
        <p className="ag-legend"><span className="is-start"><i aria-hidden="true" />{t('ages.ruler.start')}</span><span className="is-end"><i aria-hidden="true" />{t('ages.ruler.end')}</span></p>
        <ol className="ag-ruler">
          {groups.flatMap((g, i) => {
            const prev = groups[i - 1]?.age;
            const rows: ReactNode[] = [];
            if (prev !== undefined && g.age - prev > 4) {
              rows.push(<li key={`gap${g.age}`} className="ag-gap" style={{ ['--gap' as string]: Math.min(g.age - prev, 16) }}><span>{t('ages.ruler.gap', { n: g.age - prev - 1, unit: unit(g.age - prev - 1) })}</span></li>);
            }
            if ((prev === undefined ? -1 : prev) <= age && age < g.age && !groups.some((x) => x.age === age)) {
              rows.push(<li key="you" className="ag-you"><span>{t('ages.ruler.you', { age, unit: unit(age) })}</span></li>);
            }
            rows.push(
              <li key={g.age} id={`age-${g.age}`} className={`ag-row${g.age <= age ? ' is-past' : ''}${g.age === age ? ' is-you' : ''}`}>
                <span className="ag-num">{g.age}{g.age === age ? <small className="ag-num-you">{t('ages.ruler.youShort')}</small> : null}</span>
                <ul className="ag-list">{g.items.map((a) => item(a))}</ul>
              </li>,
            );
            return rows;
          })}
        </ol>
      </section>

      <section className="bp-sec" aria-labelledby="ag-s2">
        <h2 id="ag-s2">{t('ages.at18.h')}</h2>
        <p className="bp-p">{t('ages.at18.p1', { n: at(18).length, texts: new Set(at(18).map((a) => a.law)).size })}</p>
        <p className="bp-p">{t('ages.at18.p2', { n: at(16).length })}</p>
      </section>

      <section className="bp-sec" aria-labelledby="ag-s3">
        <h2 id="ag-s3">{t('ages.moves.h')}</h2>
        <p className="bp-p">{t('ages.moves.p1')}</p>
        <Figure id="ag-moves" q={t('ages.moves.q')} unit={t('ages.moves.unit')} so={t('ages.moves.so')} source={t('fig.source', { from: 1957, to: 2025 })}>
          <Moves rows={moves} yearsWord={unit} arrow={rtl ? '←' : '→'} />
        </Figure>
        <p className="bp-p">{t('ages.moves.equal')} {src('equal', 'family')}</p>
        <blockquote className="ag-quote" lang="ar" dir="rtl">«{post.equal.ar}»</blockquote>
        {lang === 'fr' ? <p className="ag-tr">{t('ages.tr', { text: post.equal.fr })}</p> : null}
      </section>

      <section className="bp-sec" aria-labelledby="ag-s4">
        <h2 id="ag-s4">{t('ages.retire.h')}</h2>
        <p className="bp-p">{t('ages.retire.p1')}</p>
        <Figure id="ag-retire" q={t('ages.retire.q')} unit={t('ages.retire.unit')} so={t('ages.retire.so')} source={t('fig.source', { from: 1971, to: 2016 })}>
          <ol className="ag-stairs" dir="ltr">
            {retire.map((s) => (
              <li key={s.born} style={{ ['--h' as string]: (s.age - 59) / 4 }} className={s.after ? 'is-now' : ''}>
                <span className="ag-stair-age" dir={rtl ? 'rtl' : 'ltr'}>{halfWord(s.age)}</span>
                <i aria-hidden="true" />
                <span className="ag-stair-year" dir={rtl ? 'rtl' : 'ltr'}>{s.before ? t('ages.retire.before', { year: s.born + 1 }) : s.after ? t('ages.retire.after', { year: s.born }) : s.born}</span>
              </li>
            ))}
          </ol>
        </Figure>
        <p className="bp-p">{t('ages.retire.p2')} {src('unknown-day', 'pensions', '2')}</p>
        <blockquote className="ag-quote" lang="ar" dir="rtl">«{post.retire.unknown_day.ar}»</blockquote>
        {lang === 'fr' ? <p className="ag-tr">{t('ages.tr', { text: post.retire.unknown_day.fr })}</p> : null}
      </section>

      <section className="bp-method" aria-labelledby="ag-method">
        <h2 id="ag-method">{t('ages.method.h')}</h2>
        <ul>
          {(['read', 'pages', 'moved', 'which', 'solar', 'check'] as const).map((k) => <li key={k}>{t(`ages.method.${k}`)}</li>)}
          <li>{t('ages.method.on', { on: day(post.counted_on, lang) })}</li>
        </ul>
      </section>
    </article>
  );
}
