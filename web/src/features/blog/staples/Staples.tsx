import { useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { Stamp } from '@/features/corpus/article/Stamp';
import type { StaplesPost } from '../blog.api';
import { Head } from '../Head';
import { Figure, Table } from '../kit';
import { day } from '../clock/names';
import { type Price, priceOn, segments, wageOn } from '../marquise/price';
import { Basket, type Item } from './Basket';
import { Gasoil } from './Gasoil';
import { shareBasket } from './share';
import '@/shared/design/french.css';
import '../post.css';
import './staples.css';

/** A sum as the Bulletin prints it: «0,90», «379,75», «94». */
const money = (v: number) => (Number.isInteger(v) ? String(v) : v.toFixed(2).replace('.', ','));
/** A staple's prices alike: with centimes for all three when one has them («4,00», «5,10»), whole when none does («94»). */
const moneyOf = (values: number[]) => (v: number) => (values.every(Number.isInteger) ? String(v) : v.toFixed(2).replace('.', ','));
/** A litre of gasoil from the orders' hectolitre, to the third decimal when the hectolitre has centimes («0,535», «8,54»). */
const litre = (dh: number) => dh.toFixed(3).replace(/0$/, '').replace('.', ',');
const days = (a: string, b: string) => Math.round((Date.parse(`${b}T00:00:00Z`) - Date.parse(`${a}T00:00:00Z`)) / 86_400_000);
/** A day as a number on a line of years, back to its date. */
const dateOf = (yr: number) => {
  const y = Math.floor(yr), d = Math.floor((yr - y) * 365.25);
  return new Date(Date.UTC(y, 0, 1 + d)).toISOString().slice(0, 10);
};

/**
 * «الخبز والغازوال، يوم كانت الجريدة الرسمية تكتب ثمنهما» (the blog's fifteenth post): the five staples of 28 May 1981 and
 * their half-return of 10 June, the loaf's ten days at 0,90; gasoil a litre from 1975 to 2014 in dirhams and in minutes
 * of minimum-wage work; the two times the price left the Bulletin, in the orders' own words. Prices are the meta's, read
 * in each order; the arithmetic is here.
 */
export default function Staples({ post }: { post: StaplesPost }) {
  const { t, i18n } = useTranslation('blog');
  const lang = i18n.language;
  const side = lang === 'fr' ? 'fr' : 'ar';
  const wage = post.figures.wage;
  const [picked, setPicked] = useState('bread');
  const [year, setYear] = useState<number | null>(1984.9);

  const items: Item[] = useMemo(() => post.basket.map((b) => ({ key: b.key, name: t(`staples.items.${b.key}`), values: b.values })), [post, t]);
  /** «9 أيام», «266 يوما»: the count of days as Arabic writes it (the plural from 3 to 10, the singular from 11). */
  const daysWord = (n: number) => t(n % 100 >= 3 && n % 100 <= 10 ? 'staples.daysFew' : 'staples.daysMany', { n });
  const bis = (s: { issue: number; bis?: boolean }) => `${s.issue}${s.bis ? (lang === 'fr' ? ' bis' : ' مكرر') : ''}`;
  const it = post.basket.find((b) => b.key === picked)!;
  const itMoney = moneyOf(it.values);
  const pct = (b: typeof it, i: number) => Math.round(((b.values[i] - b.values[0]) / b.values[0]) * 100);
  const back = (b: typeof it) => Math.round(((b.values[1] - b.values[2]) / (b.values[1] - b.values[0])) * 100);
  const backs = post.basket.map(back);
  const [sep, may, jun] = post.issues;
  // The May orders apply from 29 May, the June ones from 7 June (each order's last article).
  const breadDays = days(may.from, jun.from);
  const minutesOf = (dh: number, on: string) => Math.round((dh / wageOn(wage, on)!) * 60);

  // Gasoil: the orders as steps, in dirhams a litre, from the day each applies; the stretch the ministry published apart.
  const ministry = post.away.find((a) => a.key === 'ministry')!, means = post.away.find((a) => a.key === 'means')!;
  const gas: Price[] = useMemo(() => [...post.gasoil, { ...post.last, name: post.gasoil[post.gasoil.length - 1].name }]
    .map((g) => ({ date: g.from, price: g.price / 100, unit: 'dirham' as const, name: g.name })), [post]);
  const segs = useMemo(() => segments(gas, wage, post.last.from, { from: ministry.from, to: ministry.to! }), [gas, wage, post, ministry]);
  const first = post.gasoil[0], top = post.gasoil.reduce((a, g) => (minutesOf(g.price / 100, g.from) > minutesOf(a.price / 100, a.from) ? g : a));
  const lastPrinted = post.gasoil[post.gasoil.length - 1];
  const late = post.gasoil.filter((g) => !g.printed && days(g.from, g.date) > 60);
  const pickedDay = year !== null ? dateOf(year) : null;
  const pickedPrice = pickedDay ? priceOn(gas, pickedDay, { from: ministry.from, to: ministry.to! }) : null;
  const pickedOrder = pickedDay ? [...post.gasoil, post.last].filter((g) => g.from <= pickedDay).pop() : null;
  const inAway = pickedDay ? post.away.find((a) => pickedDay >= a.from && (!a.to || pickedDay < a.to)) : undefined;

  const ref = (key: string, n?: string) => {
    const f = post.figures.texts[key];
    if (!f) return null;
    const name = t('staples.ref.order', { n: lang === 'fr' ? (n ?? '').replace(/\./g, '-') : n });
    const issue = f.issue.replace(' bis', lang === 'fr' ? ' bis' : ' مكرر');
    return (
      <span className="sp-ref">
        <Link to={f.path ?? f.viewer!}>{name}</Link>{' '}
        <Stamp issue={issue} page={f.page} to={f.viewer} className="sp-ref-stamp" />
      </span>
    );
  };
  const heroRef = useRef<HTMLElement>(null);
  const [sharing, setSharing] = useState(false);
  const columnsOf = (short: boolean) => post.issues.map((s) => [day(s.from, lang), t(short ? 'staples.basket.issueShort' : 'staples.basket.issue', { n: bis(s) })] as [string, string]);
  const spans: [string, string] = [daysWord(days(sep.from, may.from)), daysWord(breadDays)];
  const doShare = async () => {
    if (!heroRef.current) return;
    setSharing(true);
    try {
      const name = t(`staples.items.${it.key}`);
      await shareBasket(heroRef.current, {
        dir: lang === 'fr' ? 'ltr' : 'rtl', over: `${t('name')} ${t('number', { n: post.number })}`, title: t('staples.basket.q', { n: spans[1] }),
        sub: t('staples.share.sub', { name, unit: t(`staples.units.${it.key}`), a: itMoney(it.values[0]), b: itMoney(it.values[1]), c: itMoney(it.values[2]) }),
        source: t('staples.share.source', { orders: it.orders.map((o) => (lang === 'fr' ? o.number.replace(/\./g, '-') : o.number)).join(lang === 'fr' ? ', ' : '، ') }),
        site: t('staples.share.site'), columns: columnsOf(true), spans, items, picked, money: itMoney,
      });
    } finally { setSharing(false); }
  };
  const p = (key: string, values: Record<string, unknown> = {}) => <p className="bp-p">{t(key, values)}</p>;
  const src = t('fig.source', { from: 1975, to: 2014 });

  return (
    <article className="bp sp" lang={lang}>
      <Head post={post} />

      <figure className="sp-hero" ref={heroRef} aria-labelledby="sp-q">
        <div className="sp-hero-head">
          <p className="sp-q" id="sp-q">{t('staples.basket.q', { n: daysWord(breadDays) })}</p>
          <p className="sp-how">{t('staples.basket.how')}</p>
        </div>
        <Basket items={items} picked={picked} onPick={setPicked} aria={t('staples.basket.aria')}
                spans={spans} columns={columnsOf(false).map(([d, n], i) => [d, n, columnsOf(true)[i][1]] as [string, string, string])} />
        <div className="sp-chips" role="group" aria-label={t('staples.basket.pickAria')}>
          {post.basket.map((b) => (
            <button key={b.key} type="button" className="sp-chip" aria-pressed={picked === b.key} onClick={() => setPicked(b.key)}>{t(`staples.items.${b.key}`)}</button>
          ))}
        </div>
        <div className="sp-pick" aria-live="polite">
          <p className="sp-pick-line">
            {t('staples.basket.pick', { name: t(`staples.items.${it.key}`), unit: t(`staples.units.${it.key}`), a: itMoney(it.values[0]), b: itMoney(it.values[1]), c: itMoney(it.values[2]), up: pct(it, 1), kept: pct(it, 2), back: back(it) })}
          </p>
          <ul className="sp-pick-orders">
            {it.orders.map((o, i) => <li key={o.number}><span className="sp-pick-day">{day(post.issues[i].from, lang)}</span> {ref(`b-${it.key}-${i}`, o.number)}</li>)}
          </ul>
        </div>
        <div className="sp-share-row">
          <button type="button" className="sp-share" disabled={sharing} onClick={doShare}>
            <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 3v12" /><path d="m7 8 5-5 5 5" /><path d="M5 14v5a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-5" /></svg>
            {t('staples.share.button', { name: t(`staples.items.${it.key}`) })}
          </button>
        </div>
        <p className="bp-so"><b>{t('fig.so')}</b> {t('staples.basket.so', { min: Math.min(...backs), max: Math.max(...backs) })}</p>
        <p className="bp-src">{t('fig.source', { from: 1980, to: 1981 })}</p>
      </figure>

      <section className="bp-sec" aria-labelledby="sp-s1">
        <h2 id="sp-s1">{t('staples.bread.h', { n: daysWord(breadDays) })}</h2>
        <p className="bp-p">{t('staples.bread.p1', { y75: money(post.bread_1975.value), y80: money(post.basket[0].values[0]), m75: minutesOf(post.bread_1975.value, post.bread_1975.date) })} {ref('bread-1975', post.bread_1975.number)}</p>
        {p('staples.bread.p2', { may: money(post.basket[0].values[1]), jun: money(post.basket[0].values[2]), n: daysWord(breadDays), mMay: minutesOf(post.basket[0].values[1], may.from), mJun: minutesOf(post.basket[0].values[2], jun.from) })}
        <blockquote className="sp-quote">{post.june_words[side]}</blockquote>
        {p('staples.bread.p3')}
        <Figure id="sp-ten" q={t('staples.ten.q')} unit={t('staples.ten.unit')} source={t('fig.source', { from: 1980, to: 1981 })} so={t('staples.ten.so')}>
          <div className="sp-ten">
            {[may, jun].map((iss, i) => (
              <div key={iss.key} className="sp-issue">
                <header className="sp-issue-mast">
                  <b>{t('staples.ten.mast')}</b>
                  <span><span>{t('staples.basket.issueShort', { n: bis(iss) })}</span><span>{day(iss.date, lang)}</span></span>
                </header>
                <ol className="sp-issue-list">
                  {post.basket.map((b) => (
                    <li key={b.key}>
                      <span>{t(`staples.items.${b.key}`)}</span>
                      <span className="sp-issue-price"><s>{moneyOf(b.values)(b.values[i])}</s> <b>{moneyOf(b.values)(b.values[i + 1])}</b></span>
                      {ref(`b-${b.key}-${i + 1}`, b.orders[i + 1].number)}
                    </li>
                  ))}
                </ol>
              </div>
            ))}
          </div>
        </Figure>
      </section>

      <section className="bp-sec" aria-labelledby="sp-s2">
        <h2 id="sp-s2">{t('staples.gas.h', { n: post.gasoil.length })}</h2>
        {p('staples.gas.p1', { first: litre(first.price / 100), last: litre(lastPrinted.price / 100), lastYear: lastPrinted.from.slice(0, 4), n: post.gasoil.length })}
        <Figure id="sp-gas" q={t('staples.gas.q')} unit={t('staples.gas.unit')} source={src}
                pick={pickedDay ? (
                  inAway ? t(`staples.gas.away_${inAway.key}`, { day: day(pickedDay, lang) })
                  : pickedPrice && pickedOrder ? (
                    <>
                      <b>{day(pickedDay, lang)}{lang === 'fr' ? ' :' : ':'}</b>{' '}
                      {t('staples.gas.pick', { dh: litre(pickedPrice.price), min: minutesOf(pickedPrice.price, pickedDay), tank: Math.round((40 * pickedPrice.price) / wageOn(wage, pickedDay)!) })}{' '}
                      {t('staples.gas.since', { from: day(pickedOrder.from, lang) })}{lang === 'fr' ? '' : ' '}
                      {ref(pickedOrder === post.last ? 'last' : `g${pickedOrder.from}`, pickedOrder.number)}
                    </>
                  ) : t('staples.gas.before')
                ) : t('staples.gas.hint')}
                so={t('staples.gas.so', { a: minutesOf(first.price / 100, first.from), aYear: first.from.slice(0, 4), top: minutesOf(top.price / 100, top.from), topYear: top.from.slice(0, 4), b: minutesOf(lastPrinted.price / 100, post.last.from), bYear: post.last.from.slice(0, 4) })}
                table={<Table head={[t('staples.gas.thFrom'), t('staples.gas.thPrice'), t('staples.gas.thMin'), t('staples.gas.thOrder'), t('staples.gas.thPrinted')]}
                              rows={post.gasoil.map((g) => [day(g.from, lang), litre(g.price / 100), minutesOf(g.price / 100, g.from), g.number, day(g.date, lang)])} />}>
          <ul className="sp-legend" dir="ltr">
            <li><i className="sp-key-gas" aria-hidden="true" /><span dir="auto">{t('staples.gas.keyDh')}</span></li>
            <li><i className="sp-key-min" aria-hidden="true" /><span dir="auto">{t('staples.gas.keyMin')}</span></li>
            <li><i className="sp-key-away" aria-hidden="true" /><span dir="auto">{t('staples.gas.keyAway')}</span></li>
          </ul>
          <Gasoil segs={segs} steps={post.gasoil.map((g) => ({ from: g.from, dh: g.price / 100 }))} picked={year} onPick={setYear} aria={t('staples.gas.aria')}
                  away={[{ from: ministry.from, to: ministry.to ?? null, label: t('staples.gas.awayMinistry') }, { from: means.from, to: null, label: t('staples.gas.awayMeans') }]}
                  labels={{ dh: t('staples.gas.unitDh'), minutes: t('staples.gas.unitMin'), hour: t('staples.gas.hour') }} />
        </Figure>
        {p('staples.gas.p2', { n: late.length, worst: Math.max(...late.map((g) => days(g.from, g.date))) })}
        {p('staples.gas.p3')}
      </section>

      <section className="bp-sec" aria-labelledby="sp-s3">
        <h2 id="sp-s3">{t('staples.away.h')}</h2>
        <p className="bp-p">{t('staples.away.p1')} {ref('away-ministry', ministry.text.number)}</p>
        <blockquote className="sp-quote">{ministry.words[side]}</blockquote>
        <p className="bp-p">{t('staples.away.p2', { price: litre(post.last.price / 100) })} {ref('away-means', means.text.number)}</p>
        <blockquote className="sp-quote is-last">{means.words[side]}</blockquote>
        {p('staples.away.p3')}
      </section>

      <section className="bp-method" aria-labelledby="sp-method">
        <h2 id="sp-method">{t('staples.method.h')}</h2>
        <ul>
          {(['read', 'images', 'basket', 'gasoil', 'dots', 'wage', 'check'] as const).map((k) => <li key={k}>{t(`staples.method.${k}`)}</li>)}
          <li>{t('staples.method.on', { on: day(post.counted_on, lang) })}</li>
        </ul>
      </section>
    </article>
  );
}

