import { useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import type { MarquisePost } from '../blog.api';
import { Head } from '../Head';
import { Figure, Table } from '../kit';
import { useWidth } from '../viz';
import { day } from '../clock/names';
import { Draw, FIRST_GUESS, LAST_YEAR, type Mode } from './Draw';
import { Ref } from './Ref';
import { shareGuess } from './share';
import { compare, dirhams, hm, month, segments, wageOn, yearOf } from './price';
import '@/shared/design/french.css';
import '../post.css';
import './marquise.css';

/** A sum as the Bulletin prints it: «1,40», «31». */
const money = (v: number) => (Number.isInteger(v) ? String(v) : v.toFixed(2).replace('.', ','));

/**
 * «ماركيز، قرارا بعد قرار» (the blog's fourteenth post): the reader draws the price of a pack from 1960 to today, the
 * orders draw theirs over it, and the staircase turns into hours of work at the minimum wage; then the ten centimes for
 * Palestine every pack has carried since 1970, who decides the price (the verb of the orders' titles), and a pack a day as
 * a month's work. Every price is the meta's, read in its order; every count is computed here (price.ts).
 */
export default function Marquise({ post }: { post: MarquisePost }) {
  const { t, i18n } = useTranslation('blog');
  const lang = i18n.language;
  const side = lang === 'fr' ? 'fr' : 'ar';
  const wage = post.figures.wage;
  const steps = useMemo(() => post.prices.filter((p) => p.date >= '1960'), [post]);
  const segs = useMemo(() => segments(steps, wage, post.counted_on, post.gap), [steps, wage, post]);
  const [guess, setGuess] = useState<(number | null)[]>(() => Array(LAST_YEAR - FIRST_GUESS + 1).fill(null));
  const [revealed, setRevealed] = useState(false);
  const [mode, setMode] = useState<Mode>('dh');
  const [picked, setPicked] = useState<number | null>(null);
  const [packs, setPacks] = useState(1);
  const [sharing, setSharing] = useState(false);
  const drawn = guess.filter((g) => g !== null).length;
  const lastDrawn = guess.reduce<number>((a, g, i) => (g !== null ? FIRST_GUESS + i : a), 0);

  const first = steps[0], now = steps[steps.length - 1];
  const hFirst = dirhams(first) / wageOn(wage, first.date)!, hNow = dirhams(now) / wageOn(wage, now.date)!;
  const times = Math.floor(dirhams(now) / dirhams(first));
  const ranged = segs.filter((s) => s.hours !== null);
  const low = ranged.reduce((a, b) => (b.hours! < a.hours! ? b : a)), high = ranged.reduce((a, b) => (b.hours! > a.hours! ? b : a));
  const misses = useMemo(() => compare(guess, FIRST_GUESS, post.prices, post.gap), [guess, post]);
  const worst = misses.reduce<(typeof misses)[number] | null>((a, b) => (!a || Math.abs(b.guess - b.truth) > Math.abs(a.guess - a.truth) ? b : a), null);
  const mean = misses.length ? misses.reduce((s, x) => s + Math.abs(x.guess - x.truth), 0) / misses.length : 0;
  const above = misses.filter((x) => x.guess > x.truth).length;
  // «ساعة و44 دقيقة», «ساعتين و21 دقيقة»; «1 h 44» in French.
  const hmText = (h: number) => {
    const v = hm(h);
    return t(v.h === 1 ? 'marquise.hm1' : v.h === 2 ? 'marquise.hm2' : 'marquise.hmN', { h: v.h, m: v.m, mw: t('marquise.min', { count: v.m }) }).trim();
  };

  const pickedStep = picked !== null ? steps[picked] : null;
  const pickedHours = pickedStep ? dirhams(pickedStep) / (wageOn(wage, pickedStep.date) ?? NaN) : null;
  const ref = (key: string, compact = false) => <Ref k={key} post={post} lang={lang} compact={compact} />;

  const levied = post.prices.filter((p) => p.palestine);
  const firstLevy = levied[0], lastLevy = levied[levied.length - 1];
  const share = (p: typeof firstLevy) => Math.round((p.palestine! / p.price) * 1000) / 10;
  const mon = month(packs, dirhams(now), wageOn(wage, post.counted_on)!);
  const monthHours = post.hours_a_year / 12;
  const src = t('fig.source', { from: 1956, to: 2026 });

  const doShare = async (el: HTMLElement | null) => {
    if (!el) return;
    setSharing(true);
    try {
      await shareGuess(steps, segs, guess, el, {
        dir: lang === 'fr' ? 'ltr' : 'rtl', over: `${t('name')} ${t('number', { n: post.number })}`, title: t('marquise.share.title'),
        sub: drawn ? t('marquise.share.sub', { err: money(Math.round(mean * 100) / 100) }) : t('marquise.share.subNone'),
        legend: [t('marquise.draw.keyPrice'), t('marquise.draw.keyGuess')], source: t('marquise.share.source', { n: post.prices.length }),
        site: t('marquise.share.site'),
      });
    } finally { setSharing(false); }
  };
  const figRef = useRef<HTMLElement>(null);

  return (
    <article className="bp mq" lang={lang}>
      <Head post={post} />

      <figure className="mq-hero" ref={figRef} aria-labelledby="mq-q">
        <div className="mq-hero-head">
          <p className="mq-q" id="mq-q">{t(revealed ? 'marquise.draw.qDone' : 'marquise.draw.q')}</p>
          <p className="mq-how">{t(revealed ? (mode === 'h' ? 'marquise.draw.howH' : 'marquise.draw.howDone') : 'marquise.draw.how')}</p>
        </div>
        <div className={`mq-numbers${revealed ? ' is-on' : ''}`} aria-hidden={!revealed}>
          {[first, now].map((p, i) => (
            <div key={p.date} className="mq-number">
              <span className="mq-number-year">{p.date.slice(0, 4)}</span>
              <span className="mq-number-value">
                {mode === 'dh'
                  ? <><bdi>{money(p.unit === 'franc' ? p.price : dirhams(p))}</bdi><small>{p.unit === 'franc' ? t('marquise.franc') : t('marquise.dh')}</small></>
                  : <><bdi dir="ltr">{`${hm(i ? hNow : hFirst).h}:${String(hm(i ? hNow : hFirst).m).padStart(2, '0')}`}</bdi><small>{t('marquise.hUnit')}</small></>}
              </span>
            </div>
          ))}
          <div className="mq-number is-times">
            <span className="mq-number-year">{mode === 'dh' ? t('marquise.timesLabel') : t('marquise.sameLabel')}</span>
            <span className="mq-number-value"><bdi dir="ltr">{mode === 'dh' ? `×${times}` : '='}</bdi></span>
          </div>
        </div>
        <ul className="mq-legend" dir="ltr">
          <li><i className="mq-key-price" aria-hidden="true" /><span dir="auto">{t('marquise.draw.keyPrice')}</span></li>
          {mode === 'dh' ? <li><i className="mq-key-guess" aria-hidden="true" /><span dir="auto">{t('marquise.draw.keyGuess')}</span></li> : null}
          {revealed ? <li><i className="mq-key-gap" aria-hidden="true" /><span dir="auto">{t('marquise.draw.keyGap')}</span></li> : null}
        </ul>
        <Draw segs={segs} steps={steps} opening={post.prices[0]} guess={guess} setGuess={setGuess} revealed={revealed} mode={mode}
              picked={picked} onPick={setPicked} aria={t('marquise.draw.aria')} />
        {!revealed ? (
          <div className="mq-actions">
            <button type="button" className="mq-reveal" onClick={() => setRevealed(true)} data-ready={lastDrawn >= 2015 || undefined}>
              {t(drawn ? 'marquise.draw.reveal' : 'marquise.draw.skip')}
            </button>
            <span className="mq-hint">{drawn ? t(lastDrawn >= 2015 ? 'marquise.draw.ready' : 'marquise.draw.more', { year: lastDrawn }) : t('marquise.draw.start')}</span>
          </div>
        ) : (
          <>
            {misses.length ? (
              <p className="mq-verdict" aria-live="polite">
                {t('marquise.draw.verdict', { err: money(Math.round(mean * 100) / 100), year: worst!.year, guess: money(Math.round(worst!.guess * 10) / 10), truth: money(worst!.truth) })}{' '}
                {t(above > misses.length / 2 ? 'marquise.draw.above' : 'marquise.draw.below')}
              </p>
            ) : null}
            <div className="mq-switch" role="group" aria-label={t('marquise.draw.switch')}>
              {(['dh', 'h'] as const).map((md) => (
                <button key={md} type="button" aria-pressed={mode === md} onClick={() => setMode(md)}>{t(`marquise.draw.mode_${md}`)}</button>
              ))}
            </div>
            <p className="mq-pick" aria-live="polite">
              {pickedStep ? (
                <>
                  <b>{day(pickedStep.date, lang)}:</b>{' '}
                  {t('marquise.draw.pick', { price: money(pickedStep.unit === 'franc' ? pickedStep.price : dirhams(pickedStep)), unit: pickedStep.unit === 'franc' ? t('marquise.franc') : t('marquise.dh'), name: pickedStep.name })}{' '}
                  {pickedHours && Number.isFinite(pickedHours) ? t('marquise.draw.pickHours', { hm: hmText(pickedHours) }) : null}{' '}
                  {ref(`p${pickedStep.date}`)}
                </>
              ) : t('marquise.draw.hint')}
            </p>
            <div className="mq-share-row">
              <button type="button" className="mq-share" disabled={sharing} onClick={() => doShare(figRef.current)}>
                <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 3v12" /><path d="m7 8 5-5 5 5" /><path d="M5 14v5a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-5" /></svg>
                {t(drawn ? 'marquise.share.button' : 'marquise.share.buttonNone')}
              </button>
              <span className="bp-src">{src}</span>
            </div>
          </>
        )}
      </figure>

      <section className="bp-sec" aria-labelledby="mq-s1">
        <h2 id="mq-s1">{t('marquise.hours.h', { hm: hmText(hNow) })}</h2>
        {p('marquise.hours.p1', { first: money(dirhams(first) * 100), now: money(dirhams(now)), times, w1: money(wageOn(wage, first.date)! * 100), w2: money(wageOn(wage, now.date)!), hm: hmText(hNow) })}
        {p('marquise.hours.p2', { low: hmText(low.hours!), lowYear: low.from.slice(0, 4), high: hmText(high.hours!), highYear: high.from.slice(0, 4) })}
        {p('marquise.hours.p3', { from: post.gap.from.slice(0, 4), to: post.gap.to.slice(0, 4) })}
      </section>

      <section className="bp-sec" aria-labelledby="mq-s2">
        <h2 id="mq-s2">{t('marquise.levy.h')}</h2>
        <p className="bp-p">{t('marquise.levy.p1')} {ref('levy')}</p>
        <blockquote className="mq-quote">{post.palestine.words[side]}</blockquote>
        {p('marquise.levy.p2', { ordinary: money(post.palestine.ordinary), premium: money(post.palestine.premium), c1: money(post.palestine.cinema[0]), c2: money(post.palestine.cinema[1]), t1: money(post.palestine.theatre[0]), t2: money(post.palestine.theatre[1]) })}
        <Figure id="mq-levy" q={t('marquise.levy.q')} unit={t('marquise.levy.unit', { from: firstLevy.date.slice(0, 4), to: lastLevy.date.slice(0, 4) })} source={src}
                so={t('marquise.levy.so', { a: String(share(firstLevy)).replace('.', ','), aYear: firstLevy.date.slice(0, 4), b: String(share(lastLevy)).replace('.', ','), bYear: lastLevy.date.slice(0, 4) })}
                table={<Table head={[t('marquise.levy.thDay'), t('marquise.levy.thCompany'), t('marquise.levy.thPalestine'), t('marquise.levy.thPublic')]}
                              rows={levied.map((x) => [day(x.date, lang), money(x.company!), money(x.palestine!), money(x.price)])} />}>
          <Ledger rows={levied} lang={lang} />
        </Figure>
        <p className="bp-p">{t('marquise.levy.p3')} {ref(`changed2003-01-01`)} {ref('applied')}</p>
      </section>

      <section className="bp-sec" aria-labelledby="mq-s3">
        <h2 id="mq-s3">{t('marquise.who.h')}</h2>
        <p className="bp-p">{t('marquise.who.p1')} {ref('delegate')}</p>
        <Figure id="mq-who" q={t('marquise.who.q')} unit={t('marquise.who.unit', { n: post.figures.orders.length })} source={src}
                so={t('marquise.who.so', { set: post.figures.orders.filter((o) => o[1] === 'set').length, approve: post.figures.orders.filter((o) => o[1] === 'approve').length })}>
          <ul className="mq-legend" dir="ltr">
            <li><i className="mq-key-set" aria-hidden="true" /><span dir="auto">{t('marquise.who.keySet')}</span></li>
            <li><i className="mq-key-approve" aria-hidden="true" /><span dir="auto">{t('marquise.who.keyApprove')}</span></li>
          </ul>
          <Verbs orders={post.figures.orders} gap={post.gap} labels={{ 1976: t('marquise.who.l1976'), 2013: t('marquise.who.l2013') }} lang={lang} />
        </Figure>
        <p className="bp-p">{t('marquise.who.p2')} {ref('approve')}</p>
        <blockquote className="mq-quote">{post.approve.words[side]}</blockquote>
      </section>

      <section className="bp-sec" aria-labelledby="mq-s4">
        <h2 id="mq-s4">{t('marquise.month.h')}</h2>
        {p('marquise.month.p')}
        <div className="mq-month">
          <div className="mq-month-ask" role="group" aria-label={t('marquise.month.ask')}>
            <span className="mq-month-label">{t('marquise.month.ask')}</span>
            {[0.5, 1, 1.5, 2].map((n) => (
              <button key={n} type="button" className="mq-chip" aria-pressed={packs === n} onClick={() => setPacks(n)}>{t('marquise.month.packs', { n: String(n).replace('.', ',') })}</button>
            ))}
          </div>
          <div className="mq-month-answer" aria-live="polite">
            <div className="mq-month-figure"><span className="mq-month-big" dir="ltr">{Math.round(mon.cost)}</span><span>{t('marquise.month.dh')}</span></div>
            <div className="mq-month-figure"><span className="mq-month-big" dir="ltr">{Math.round(mon.hours)}</span><span>{t('marquise.month.hours')}</span></div>
            <div className="mq-month-figure"><span className="mq-month-big" dir="ltr">{Math.round((mon.hours / monthHours) * 100)}%</span><span>{t('marquise.month.share', { h: Math.round(monthHours) })}</span></div>
          </div>
          <div className="mq-month-bar" aria-hidden="true"><i style={{ width: `${Math.min(100, (mon.hours / monthHours) * 100)}%` }} /></div>
          <p className="bp-src">{t('marquise.month.src', { price: money(dirhams(now)), wage: money(wageOn(wage, post.counted_on)!), h: post.hours_a_year })}</p>
        </div>
      </section>

      <section className="bp-method" aria-labelledby="mq-method">
        <h2 id="mq-method">{t('marquise.method.h')}</h2>
        <ul>
          {(['read', 'pack', 'images', 'wage', 'gap', 'francs', 'check'] as const).map((k) => (
            <li key={k}>{t(`marquise.method.${k}`, { n: post.prices.length })}</li>
          ))}
          <li>{t('marquise.method.renamed')} {ref('renamed', true)}</li>
          <li>{t('marquise.method.on', { on: day(post.counted_on, lang) })}</li>
        </ul>
      </section>
    </article>
  );

  function p(key: string, values: Record<string, unknown> = {}) {
    return <p className="bp-p">{t(key, values)}</p>;
  }
}

/** The orders of 1976–1987 as they print a pack's price: the company's part, Palestine's ten centimes, the public price;
 *  drawn as one bar each, the ten centimes in the Bulletin's violet. */
function Ledger({ rows, lang }: { rows: MarquisePost['prices']; lang: string }) {
  const [ref, width] = useWidth<HTMLDivElement>(640);
  const max = Math.max(...rows.map((r) => r.price));
  const label = 96, bar = width - label - 56;
  return (
    <div ref={ref} className="mq-ledger" dir="ltr">
      {rows.map((r) => (
        <div key={r.date} className="mq-ledger-row">
          <span className="mq-ledger-day">{day(r.date, lang).replace(/^\S+\s/, '')}</span>
          <span className="mq-ledger-bar" style={{ width: Math.max(8, (r.price / max) * bar) }}>
            <i className="mq-ledger-co" style={{ flexGrow: r.company }} />
            <i className="mq-ledger-pa" style={{ flexGrow: r.palestine }} />
          </span>
          <span className="mq-ledger-sum">{r.price.toFixed(2).replace('.', ',')}</span>
        </div>
      ))}
    </div>
  );
}

/** Every order on tobacco prices since 1956, a dot each on a line of years, the verb of its title as its colour. */
function Verbs({ orders, gap, labels, lang }: { orders: [string, 'set' | 'approve'][]; gap: { from: string; to: string }; labels: Record<number, string>; lang: string }) {
  const [ref, width] = useWidth<HTMLDivElement>(640);
  const x = (yr: number) => 8 + ((yr - 1955) / (2027.5 - 1955)) * (width - 16);
  // Orders in one year stack upwards.
  const stacks: Record<number, number> = {};
  const dots = orders.map(([d, v]) => { const yr = Math.floor(yearOf(d)); const k = (stacks[yr] = (stacks[yr] ?? 0) + 1); return { d, v, yr: yearOf(d), k }; });
  const top = Math.max(...Object.values(stacks));
  const h = 40 + top * 11 + 26;
  const base = h - 30;
  return (
    <div ref={ref} className="mq-verbs" dir="ltr">
      <svg width={width} height={h} role="img" aria-hidden="true">
        <rect x={x(yearOf(gap.from)) + 6} y={base - top * 11 - 4} width={x(yearOf(gap.to)) - x(yearOf(gap.from)) - 12} height={top * 11 + 8} className="mq-verbs-gap" />
        <line x1={4} x2={width - 4} y1={base + 6} y2={base + 6} className="mq-axis" />
        {dots.map((o) => <circle key={`${o.d}-${o.k}`} cx={x(o.yr)} cy={base - (o.k - 1) * 11} r={4.4} className={`mq-verb is-${o.v}`} />)}
        {[1960, 1980, 2000, 2020].map((yr) => <text key={yr} x={x(yr)} y={h - 4} textAnchor="middle" className="mq-tick">{yr}</text>)}
        {Object.entries(labels).map(([yr, text]) => (
          <text key={yr} x={x(+yr)} y={base - top * 11 - 10} textAnchor={+yr > 2000 ? (lang === 'fr' ? 'end' : 'start') : (lang === 'fr' ? 'start' : 'end')}
                direction={lang === 'fr' ? 'ltr' : 'rtl'} className="mq-tick is-strong">{text}</text>
        ))}
      </svg>
    </div>
  );
}
