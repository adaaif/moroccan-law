import { useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import type { ClockPost } from '../blog.api';
import { Head } from '../Head';
import { Figure, Table } from '../kit';
import { Face } from './Face';
import { hands } from './time';
import { Finder } from './Finder';
import { Hero } from './Hero';
import { type Outline, type Pick, Grid } from './Grid';
import { day, hourOf, months, textName, weekdayDay } from './names';
import { Notice } from './Notice';
import { share } from './share';
import { TextLink } from './TextLink';
import { at, beforeRamadan, type Clock as ClockData, daysBetween, longestRun, notices, row, slotDay, slotOf, summary } from './time';
import '@/shared/design/french.css';
import '../post.css';
import './clock.css';

const FIRST = 1913, LAST = 2026;
/** The steps the grid walks through, each the years it lights; the Ramadan step outlines each year's month. */
const STEPS: { key: string; focus: [number, number] | null; ramadan?: boolean }[] = [
  { key: 's1913', focus: [1913, 1917] },
  { key: 's1918', focus: [1918, 1918] },
  { key: 's1919', focus: [1918, 1939] },
  { key: 's1939', focus: [1939, 1946] },
  { key: 's1950', focus: [1950, 1950] },
  { key: 's1967', focus: [1967, 1967] },
  { key: 's1974', focus: [1974, 1989] },
  { key: 's1990', focus: [1989, 2008] },
  { key: 's2008', focus: [2008, 2018] },
  { key: 's2018', focus: [2018, 2026] },
  { key: 'sRamadan', focus: [2008, 2026], ramadan: true },
  { key: 's2026', focus: [2026, 2026] },
  { key: 'sAll', focus: null },
];
const NOTES = [1918, 1943, 1950, 1967, 1985, 1989, 1999, 2014, 2022, 2026];

/** Years, months and days between two days, as a reader says a length of time. */
function span(from: string, to: string) {
  const [y0, m0, d0] = from.slice(0, 10).split('-').map(Number), [y1, m1, d1] = to.slice(0, 10).split('-').map(Number);
  let months = (y1 - y0) * 12 + (m1 - m0) - (d1 < d0 ? 1 : 0);
  const years = Math.floor(months / 12);
  months -= years * 12;
  return { years, months };
}

/**
 * «من غرينيتش إلى غرينيتش» (the blog's thirteenth post): the night of 20 September 2026 on a clock face; Rabat half an
 * hour behind Casablanca before the legal time; every day since 1913 as one picture, walked step by step; any day's
 * hour; how long before a move the Bulletin printed it; and what is left after 2026. Every move is the meta's, read in
 * its text; every count is computed here from them (time.ts), so the words and the picture cannot disagree.
 */
export default function Clock({ post }: { post: ClockPost }) {
  const { t, i18n } = useTranslation('blog');
  const lang = i18n.language;
  const side = lang === 'fr' ? 'fr' : 'ar';
  const c: ClockData = useMemo(() => ({ legal_from: post.legal_from, moves: post.moves, unknown: post.unknown }), [post]);
  const rows = useMemo(() => Array.from({ length: LAST - FIRST + 1 }, (_, i) => row(c, FIRST + i)), [c]);
  const texts = useMemo(() => Object.fromEntries(post.texts.map((x) => [x.key, x])), [post]);
  const sum = useMemo(() => summary(c, post.texts.length, post.counted_on), [c, post]);
  const notice = useMemo(() => notices(c, post.figures.texts), [c, post]);
  const ramadan = useMemo(() => beforeRamadan(c, post.figures.hijri), [c, post]);
  const run = longestRun(ramadan.map((r) => r.year));
  const [step, setStep] = useState(0);
  const [picked, setPicked] = useState<Pick | null>(null);
  const [dot, setDot] = useState<number | null>(null);
  const stepRefs = useRef<(HTMLLIElement | null)[]>([]);
  const gridRef = useRef<HTMLDivElement>(null);
  const [sharing, setSharing] = useState(false);
  const monthNames = useMemo(() => months(lang), [lang]);
  const notes = useMemo(() => Object.fromEntries(NOTES.map((y) => [y, t(`clock.notes.y${y}`)])), [t]);

  // A desk reads the step at the screen's middle; a phone below its sticky picture, above the bottom bar.
  const [desk, setDesk] = useState(() => typeof window !== 'undefined' && window.matchMedia('(min-width: 1000px)').matches);
  const [tall, setTall] = useState(() => (typeof window !== 'undefined' ? window.innerHeight : 900));
  useEffect(() => {
    const mq = window.matchMedia('(min-width: 1000px)');
    const hear = () => { setDesk(mq.matches); setTall(window.innerHeight); };
    mq.addEventListener('change', hear);
    window.addEventListener('resize', hear);
    return () => { mq.removeEventListener('change', hear); window.removeEventListener('resize', hear); };
  }, []);
  useEffect(() => {
    const io = new IntersectionObserver((es) => es.forEach((e) => {
      if (e.isIntersecting) setStep(stepRefs.current.indexOf(e.target as HTMLLIElement));
    }), { rootMargin: desk ? '-45% 0px -50% 0px' : '-70% 0px -22% 0px' });
    stepRefs.current.forEach((el) => el && io.observe(el));
    return () => io.disconnect();
  }, [desk]);

  const s = STEPS[Math.max(0, step)];
  const outlines: Outline[] = useMemo(() => (s.ramadan ? ramadan.map((r) => {
    const end = post.figures.hijri.shawwal[String(r.year)];
    const last = end && end.slice(0, 4) === r.first.slice(0, 4) ? slotOf(end) - 1 : 365;
    return { year: r.year, from: slotOf(r.first), to: last };
  }) : []), [s, ramadan, post]);

  const longest = sum.longestAhead, shortest = sum.shortestAhead, calm = sum.longestGmt;
  const war = span(longest.from!.at, longest.to!.at);
  const late = notice.filter((n) => n.days < 0);
  const lastLate = late.reduce((a, b) => (b.move.at > a.move.at ? b : a), late[0]);
  const end = post.moves[post.moves.length - 1];
  const finalNotice = notice.find((n) => n.move === end)!;
  const src = t('fig.source', { from: FIRST, to: LAST });
  const p = (key: string, values: Record<string, unknown> = {}) => <p className="bp-p">{t(key, values)}</p>;
  const ref = (key: string) => <TextLink t={texts[key]} post={post} lang={lang} />;
  const short = (key: string) => <TextLink t={texts[key]} post={post} lang={lang} compact />;
  const words = (key: string) => post.words[key][side];

  // What the grid's picked day says.
  const pickedDay = picked ? slotDay(picked.year, picked.slot) : null;
  const pickedAt = pickedDay ? at(c, `${pickedDay}T12:00`) : null;
  const tell = pickedDay && pickedAt ? (
    <>
      <b>{weekdayDay(pickedDay, lang)}{lang === 'fr' ? ' :' : ':'}</b>{' '}{t(`clock.grid.${pickedAt.state}`)}
      {pickedAt.state !== 'none' && pickedAt.state !== 'unknown' ? (
        <>{' '}{t(pickedAt.until ? 'clock.grid.from_to' : 'clock.grid.from', { from: day(pickedAt.since?.at ?? post.legal_from, lang), to: pickedAt.until ? day(pickedAt.until.at, lang) : '' })}{' '}
          {ref(pickedAt.since?.text ?? 'd1913')}</>
      ) : null}
    </>
  ) : t('clock.grid.hint');

  const doShare = async () => {
    if (!gridRef.current) return;
    setSharing(true);
    try {
      await share(rows, { dir: lang === 'fr' ? 'ltr' : 'rtl', over: `${t('name')} ${t('number', { n: post.number })}`, title: t('clock.share.title'),
                          sub: t('clock.share.sub', { from: FIRST, to: LAST }), legend: [t('clock.legend.ahead'), t('clock.legend.gmt')],
                          source: t('clock.share.source', { n: sum.texts }), site: t('clock.share.site'), first: FIRST, last: LAST }, gridRef.current);
    } finally { setSharing(false); }
  };

  const noticeRows = notice;
  const noticeLabels = useMemo(() => ({
    '2026-09-20': t('clock.notice.label2026', { n: finalNotice.days }),
    '1967-06-03': t('clock.notice.label1967', { n: -notice.find((n) => n.move.at.startsWith('1967-06-03'))!.days }),
    '2011-07-31': t('clock.notice.label2011', { n: notice.find((n) => n.move.at.startsWith('2011-07-31'))!.days }),
  }), [t, finalNotice, notice]);
  const dotRow = dot !== null ? noticeRows[dot] : null;

  return (
    <article className="bp ck" lang={lang}>
      <Head post={post} />

      <Hero when={t('clock.hero.when', { day: weekdayDay(end.at, lang), hour: hourOf(end.at) })} quote={words('d226530')} stamp={ref('d226530')} />

      <section className="bp-sec" aria-labelledby="ck-s1">
        <h2 id="ck-s1">{t('clock.before.h')}</h2>
        {p('clock.before.p1', { m: post.before.rabat.minutes, s: post.before.rabat.seconds })}
        <figure className="ck-cities">
          {[['casablanca', 12, 0, 0], ['rabat', 11, 32, 30]].map(([city, h, m, sec]) => (
            <div key={city as string} className="ck-city">
              <Face size={118} at={hands(h as number, m as number, sec as number)} label={t(`clock.before.${city}`, { time: `${h}:${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}` })} />
              <p className="ck-city-name">{t(`clock.before.${city}Name`)}</p>
              <p className="ck-city-time" dir="ltr">{`${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`}</p>
            </div>
          ))}
          <figcaption className="bp-src">{t('clock.before.src', { issue: post.before.rabat.issue, page: post.before.rabat.page })}</figcaption>
        </figure>
        {p('clock.before.p2')}
        <p className="bp-p">{t('clock.before.p3')} {ref('d1913')}</p>
      </section>

      <section className="ck-century" aria-labelledby="ck-s2">
        <div className="bp-sec">
          <h2 id="ck-s2">{t('clock.century.h', { years: LAST - FIRST })}</h2>
          {p('clock.century.p', { moves: sum.moves, texts: sum.texts, years: (sum.aheadDays / 365.25).toFixed(1).replace('.', ',') })}
        </div>
        <p className="bp-q ck-q-phone">{t('clock.grid.q')}</p>
        <div className="ck-scrolly">
          <div className="ck-sticky">
            <div className="ck-sticky-in">
              <p className="bp-q ck-q-desk">{t('clock.grid.q')}</p>
              <ul className="ck-legend" dir="ltr">
                <li><i className="ck-key-ahead" aria-hidden="true" /><span dir="auto">{t('clock.legend.ahead')}</span></li>
                <li><i className="ck-key-gmt" aria-hidden="true" /><span dir="auto">{t('clock.legend.gmt')}</span></li>
                <li><i className="ck-key-unknown" aria-hidden="true" /><span dir="auto">{t('clock.legend.unknown')}</span></li>
                {s.ramadan ? <li><i className="ck-key-ramadan" aria-hidden="true" /><span dir="auto">{t('clock.legend.ramadan')}</span></li> : null}
              </ul>
              <div ref={gridRef}>
                <Grid rows={rows} first={FIRST} focus={s.focus} outlines={outlines} picked={picked} onPick={setPicked}
                      aria={t('clock.grid.aria')} monthNames={monthNames} lang={lang} labelled={notes} tall={desk ? tall - 190 : 0} />
              </div>
              <p className={`ck-tell${picked ? '' : ' is-hint'}`} aria-live="polite">{tell}</p>
            </div>
          </div>
          <ol className="ck-steps">
            {STEPS.map((x, i) => (
              <li key={x.key} ref={(el) => { stepRefs.current[i] = el; }} className={i === step ? 'is-on' : ''}>
                {x.focus ? <p className="ck-step-years" dir="ltr">{x.focus[0] === x.focus[1] ? x.focus[0] : `${x.focus[0]}–${x.focus[1]}`}</p> : null}
                <h3>{t(`clock.steps.${x.key}.h`, { years: Math.round(calm.days / 365.25), y: war.years, m: war.months, run: run[1] - run[0] + 1 })}</h3>
                {stepBody(x.key)}
              </li>
            ))}
          </ol>
        </div>
        <div className="ck-share-row">
          <button type="button" className="ck-share" onClick={doShare} disabled={sharing}>
            <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 3v12" /><path d="m7 8 5-5 5 5" /><path d="M5 14v5a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-5" />
            </svg>
            {t('clock.share.button')}
          </button>
          <span className="bp-src">{src}</span>
        </div>
      </section>

      <section className="bp-sec" aria-labelledby="ck-s3">
        <h2 id="ck-s3">{t('clock.finder.h')}</h2>
        {p('clock.finder.p')}
        <Finder c={c} post={post} lang={lang} />
      </section>

      <section className="bp-sec" aria-labelledby="ck-s4">
        <h2 id="ck-s4">{t('clock.notice.h')}</h2>
        {p('clock.notice.p1', { late: late.length, all: notice.length })}
        <Figure id="ck-notice" q={t('clock.notice.q')} unit={t('clock.notice.unit')} source={src}
                pick={dotRow ? (
                  <>{day(dotRow.move.at, lang)}: {ref(dotRow.move.text)}{' '}
                    {t(dotRow.days > 0 ? 'clock.notice.before' : dotRow.days < 0 ? 'clock.notice.after' : 'clock.notice.same', { n: Math.abs(dotRow.days), printed: day(dotRow.printed, lang), count: Math.abs(dotRow.days) })}</>
                ) : t('clock.notice.hint')}
                so={t('clock.notice.so', { late: late.length, all: notice.length, last: lastLate ? Number(lastLate.move.at.slice(0, 4)) : '' })}
                table={<Table head={[t('clock.notice.thMove'), t('clock.notice.thText'), t('clock.notice.thPrinted'), t('clock.notice.thDays')]}
                              rows={noticeRows.map((n) => [day(n.move.at, lang), textNameOf(n.move.text), day(n.printed, lang), n.days])} />}>
          <ul className="ck-legend" dir="ltr">
            <li><i className="ck-key-dot" aria-hidden="true" /><span dir="auto">{t('clock.notice.keyBefore')}</span></li>
            <li><i className="ck-key-late" aria-hidden="true" /><span dir="auto">{t('clock.notice.keyAfter')}</span></li>
          </ul>
          <Notice rows={noticeRows} picked={dot} onPick={setDot} aria={t('clock.notice.aria')} labels={noticeLabels} />
        </Figure>
        {p('clock.notice.p2')}
      </section>

      <section className="bp-sec" aria-labelledby="ck-s5">
        <h2 id="ck-s5">{t('clock.after.h')}</h2>
        <p className="bp-p">{t('clock.after.p1')} {ref('d226530')}</p>
        <blockquote className="ck-quote is-law">{words('r45567').split(' … ')[0]}</blockquote>
        {p('clock.after.p2', { on: day(post.counted_on, lang), from: run[0], to: run[1] })}
      </section>

      <section className="bp-method" aria-labelledby="ck-method">
        <h2 id="ck-method">{t('clock.method.h')}</h2>
        <ul>
          {(['read', 'pages', 'day', 'zone', 'missing', 'ramadan', 'french', 'check'] as const).map((k) => (
            <li key={k}>{t(`clock.method.${k}`, { cut: post.texts.length - Object.values(post.figures.texts).filter((x) => !x.path).length, uncut: Object.values(post.figures.texts).filter((x) => !x.path).length })}</li>
          ))}
          <li>{t('clock.method.on', { on: day(post.counted_on, lang) })}</li>
        </ul>
      </section>
    </article>
  );

  function textNameOf(key: string) {
    return texts[key] ? textName(texts[key], lang) : key;
  }

  /** A step's words: its sentences, the texts it names as links, and its quote. */
  function stepBody(k: string) {
    const sentence = (key: string, values: Record<string, unknown> = {}) => <p>{t(`clock.steps.${k}.${key}`, values)}</p>;
    switch (k) {
      case 's1913': return <>{sentence('p')}<p>{short('d1913')}</p></>;
      case 's1918': return <>{sentence('p')}<p>{short('d1918a')}</p><p>{short('d1918b')}</p></>;
      case 's1919': return sentence('p', { years: Math.round(calm.days / 365.25) });
      case 's1939': return <>{sentence('p1')}<p>{short('d1939')}</p><p>{short('d1940')}</p>{sentence('p2', { y: war.years, m: war.months })}<p>{short('d1945a')}</p><p>{short('d1945b')}</p><p>{short('d1946')}</p></>;
      case 's1950': return <>{sentence('p')}<blockquote className="ck-quote is-law">{words('d1950a')}</blockquote><p>{short('d1950a')}</p></>;
      case 's1967': return <>{sentence('p', { late: -notice.find((n) => n.move.at.startsWith('1967-06-03'))!.days })}<p>{short('r45567')}</p></>;
      case 's1974': return <>{sentence('p', { days: Math.round(shortest.days) })}<p>{short('d284215')}</p><p>{short('d289357')}</p></>;
      case 's1990': return sentence('p', { years: Math.floor(daysBetween('1989-07-01', '2008-06-01') / 365.25) });
      case 's2008': return <>{sentence('p1')}<p>{short('d212126')}</p>{sentence('p2')}<p>{short('d213781')}</p></>;
      case 's2018': return <>{sentence('p1')}<p>{short('d218855')}</p>{sentence('p2')}<p>{short('c9019')}</p></>;
      case 'sRamadan': return sentence('p', { from: run[0], to: run[1], n: run[1] - run[0] + 1 });
      case 's2026': return <>{sentence('p', { n: finalNotice.days })}<p>{short('d226530')}</p></>;
      default: return sentence('p', { moves: sum.moves, years: (sum.aheadDays / 365.25).toFixed(1).replace('.', ',') });
    }
  }
}

