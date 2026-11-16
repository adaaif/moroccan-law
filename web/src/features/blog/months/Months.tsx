import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { longDate } from '@/features/corpus/format';
import type { MonthsPost } from '../blog.api';
import { Head } from '../Head';
import { Bars, Figure, Table } from '../kit';
import { dec, monthNames, n } from '../viz';
import Calendar from './Calendar';
import '@/shared/design/french.css';
import '../post.css';
import './months.css';

/**
 * «دجنبر، شهر الأعداد المكررة، ومارس، شهر القوانين» (the blog's fifth post): seventy years as a calendar of months; then
 * December's pages and bis issues, the laws' own calendar (March, and October's low), and the Hijri months read on the
 * mastheads (Ramadan changes almost nothing). Every figure in the prose comes from the counted figures.
 */
export default function Months({ post }: { post: MonthsPost }) {
  const { t, i18n } = useTranslation('blog');
  const lang = i18n.language;
  const rtl = lang !== 'fr';
  const f = post.figures;
  const [first, last] = f.span;
  const N = (v: number) => n(v, lang);
  const names = monthNames(lang);
  const ticks = Object.fromEntries(names.map((m, i) => [i, m]));
  const hijri = t('months.hijri', { returnObjects: true }) as string[];
  const src = t('fig.source', { from: first, to: last });
  const x = useMemo(() => {
    const since = f.hijri_since - first;
    const recent = f.months.slice(since);
    const sumM = (k: number) => Array.from({ length: 12 }, (_, m) => recent.reduce((s, y) => s + y[m][k], 0));
    const pages = sumM(2), bis = sumM(1), texts = sumM(3);
    const topPages = f.months.map((y) => y.reduce((b, c, m) => (c[2] > y[b][2] ? m : b), 0));
    const perIssue = f.hijri.map(([i, tx]) => (i ? tx / i : 0));
    const allIssues = f.hijri.reduce((s, h) => s + h[0], 0), allTexts = f.hijri.reduce((s, h) => s + h[1], 0);
    const orders = f.kinds.orders;
    // How many years each month's pages were above its year's monthly mean.
    const above = Array.from({ length: 12 }, (_, m) => f.months.filter((y) => y[m][2] > y.reduce((a, c) => a + c[2], 0) / 12).length);
    return { pages, bis, texts, decTop: topPages.filter((m) => m === 11).length, perIssue, avg: allTexts / allIssues, read: allIssues,
             orders, above, avgOrders: orders.reduce((s, v) => s + v, 0) / 12 };
  }, [f, first]);
  const [p1, setP1] = useState<number | null>(null);
  const [p2, setP2] = useState<number | null>(null);
  const [p3, setP3] = useState<number | null>(null);
  const laws = f.kinds.laws;
  const meanPages = x.pages.reduce((s, v) => s + v, 0) / 12;
  const low = x.perIssue.indexOf(Math.min(...x.perIssue)), high = x.perIssue.indexOf(Math.max(...x.perIssue));
  const p = (key: string, values: Record<string, unknown> = {}) => <p className="bp-p">{t(key, values)}</p>;

  return (
    <article className="bp" lang={lang}>
      <Head post={post} />

      <figure className="bp-hero" aria-labelledby="cal-q">
        <div className="bp-hero-words">
          <p className="bp-q" id="cal-q">{t('months.hero.q')}</p>
          <p className="bp-unit">{t('months.hero.how', { from: first, to: last })}</p>
        </div>
        <Calendar post={post} />
        <div className="bp-hero-foot">
          <p className="bp-so"><b>{t('fig.so')}</b> {t('months.hero.so', { dec: x.decTop, years: f.months.length })}</p>
          <p className="bp-src">{src}</p>
        </div>
      </figure>

      <section className="bp-sec" aria-labelledby="months-s1">
        <h2 id="months-s1">{t('months.s1.h')}</h2>
        {p('months.s1.p1', { pages: N(x.pages[11]), more: Math.round((100 * x.pages[11]) / meanPages - 100), texts: N(x.texts[11]),
                             bis: N(x.bis[11]), bisAll: N(x.bis.reduce((s, v) => s + v, 0)) })}
        {p('months.s1.p2', { decOrders: N(x.orders[11]), avgOrders: N(Math.round(x.avgOrders)) })}
        {p('months.s1.p3', { aug: x.above[7], dec: x.above[11], years: f.months.length })}
        <Figure id="dec" q={t('months.s1.q')} unit={t('months.s1.unit')} source={src} so={t('months.s1.so', { pages: N(x.pages[11]), bis: N(x.bis[11]) })}
                pick={p1 === null ? t('fig.hint') : t('months.s1.pick', { month: names[p1], pages: N(x.pages[p1]), bis: N(x.bis[p1]) })}
                table={<Table head={['', t('months.s1.unit')]} rows={names.map((m, i) => [m, `${N(x.pages[i])} · ${N(x.bis[i])}`])} />}>
          <Bars values={x.pages} rtl={rtl} hi={[11]} picked={p1} onPick={setP1} height={180} ticks={ticks}
                labels={Object.fromEntries(x.bis.map((b, i) => [i, N(b)]))} aria={t('months.s1.q')} />
        </Figure>
      </section>

      <section className="bp-sec" aria-labelledby="months-s2">
        <h2 id="months-s2">{t('months.s2.h')}</h2>
        {p('months.s2.p1', { mar: N(laws[2]), sep: N(laws[8]), oct: N(laws[9]) })}
        <Figure id="laws-months" q={t('months.s2.q')} unit={t('months.s2.unit')} source={src} so={t('months.s2.so', { mar: N(laws[2]), oct: N(laws[9]) })}
                pick={p2 === null ? t('fig.hint') : t('months.s2.pick', { month: names[p2], n: N(laws[p2]) })}
                table={<Table head={['', '']} rows={names.map((m, i) => [m, N(laws[i])])} />}>
          <Bars values={laws} rtl={rtl} hi={[2]} picked={p2} onPick={setP2} height={170} ticks={ticks}
                labels={{ 2: N(laws[2]), 9: N(laws[9]) }} aria={t('months.s2.q')} />
        </Figure>
      </section>

      <section className="bp-sec" aria-labelledby="months-s3">
        <h2 id="months-s3">{t('months.s3.h')}</h2>
        {p('months.s3.p1', { ram: dec(x.perIssue[8], 1), avg: dec(x.avg, 1), low: dec(x.perIssue[low], 1), high: dec(x.perIssue[high], 1) })}
        <Figure id="hijri" q={t('months.s3.q')} unit={t('months.s3.unit')} source={src} so={t('months.s3.so', { ram: dec(x.perIssue[8], 1), avg: dec(x.avg, 1) })}
                pick={p3 === null ? t('fig.hint') : t('months.s3.pick', { month: hijri[p3], n: dec(x.perIssue[p3], 1), issues: N(f.hijri[p3][0]) })}
                table={<Table head={['', '', '']} rows={hijri.map((m, i) => [m, dec(x.perIssue[i], 1), N(f.hijri[i][0])])} />}>
          <Bars values={x.perIssue} rtl={rtl} hi={[8]} picked={p3} onPick={setP3} height={170}
                ticks={Object.fromEntries(hijri.map((m, i) => [i, m]))} labels={{ 8: dec(x.perIssue[8], 1) }} aria={t('months.s3.q')} />
        </Figure>
      </section>

      <section className="bp-method" aria-labelledby="months-method">
        <h2 id="months-method">{t('months.method.h')}</h2>
        <ul>
          <li>{t('months.method.issues', { from: first, to: last })}</li>
          <li>{t('months.method.rel')}</li>
          <li>{t('months.method.hijri', { read: N(x.read) })}</li>
          <li>{t('months.method.on', { on: longDate(post.counted_on, lang) })}</li>
        </ul>
      </section>
    </article>
  );
}
