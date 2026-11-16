import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { longDate } from '@/features/corpus/format';
import type { WagePost } from '../blog.api';
import { Head } from '../Head';
import { Bars, Figure, Table } from '../kit';
import { dec, n } from '../viz';
import Stairs, { type Step } from './Stairs';
import '@/shared/design/french.css';
import '../post.css';
import './wage.css';

const years = (a: string, b: string) => (Date.parse(b) - Date.parse(a)) / (365.25 * 864e5);

/** Two decimals the way the Bulletin writes them: «3.416,75». */
function money(v: number, lang: string): string {
  const whole = Math.floor(v), cents = Math.round((v - whole) * 100);
  return `${n(whole, lang)},${String(cents).padStart(2, '0')}`;
}

/**
 * «الحد الأدنى للأجر، مرسوما بعد مرسوم» (the blog's sixth post): the hourly minimum wage as a staircase of its decrees
 * since 1960; then sixty years of decrees (the 1956 raise, the four zones of 1960, thirteen years without a text, the
 * steps since 1973), the month a full year of hours makes today, and the agricultural day against the hour. The amounts
 * are the meta's, read in each decree; every figure in the prose is computed from them.
 */
export default function Wage({ post }: { post: WagePost }) {
  const { t, i18n } = useTranslation('blog');
  const lang = i18n.language;
  const rtl = lang !== 'fr';
  const N = (v: number) => n(v, lang);
  const decrees = post.figures.decrees;
  const x = useMemo(() => {
    const at = (s: WagePost['steps'][number]) => (s.from ?? decrees[s.decree]?.published ?? '');
    const hourly: Step[] = post.steps.filter((s) => s.hourly).map((s) => ({ at: at(s), value: s.hourly!, decree: s.decree, published: Boolean(s.from_published) }));
    const ids = (from: string) => new Set(post.steps.filter((s) => s.decree && at(s) >= from && (s.hourly || s.daily)).map((s) => s.decree));
    let gap2 = { y: 0, from: '', to: '' };
    hourly.forEach((s, i) => {
      if (i && hourly[i - 1].at >= '1973' && years(hourly[i - 1].at, s.at) > gap2.y) gap2 = { y: years(hourly[i - 1].at, s.at), from: hourly[i - 1].at, to: s.at };
    });
    // The agricultural day against the hour, for each decree that sets both.
    const pairs = [...new Set(post.steps.map((s) => s.decree))].map((dcr) => {
      const own = post.steps.filter((s) => s.decree === dcr);
      const h = own.filter((s) => s.hourly).pop(), dd = own.filter((s) => s.daily).pop();
      return h && dd ? { decree: dcr, at: at(h), hourly: h.hourly!, daily: dd.daily!, r: dd.daily! / h.hourly! } : null;
    }).filter(Boolean) as { decree: string; at: string; hourly: number; daily: number; r: number }[];
    const zones = post.steps.find((s) => s.zones)!.zones!;
    const first = hourly[0], last = hourly[hourly.length - 1];
    const before = hourly.findIndex((s) => s.at >= '1973');
    return { hourly, gap: Math.floor(years(hourly[before - 1].at, hourly[before].at)), after: ids('1973').size, gap2, pairs, zones, first, last,
             count: new Set(hourly.map((s) => s.decree)).size };
  }, [post, decrees]);
  const daily = post.steps.filter((s) => s.daily);
  const [pz, setPz] = useState<number | null>(null);
  const [pr, setPr] = useState<number | null>(null);
  const r1 = x.pairs.filter((p) => p.at < '2021').map((p) => p.r), rN = x.pairs.filter((p) => p.at >= '2022').map((p) => p.r);
  const src = t('fig.source', { from: x.first.at.slice(0, 4), to: x.last.at.slice(0, 4) });
  const p = (key: string, values: Record<string, unknown> = {}) => <p className="bp-p">{t(key, values)}</p>;

  return (
    <article className="bp" lang={lang}>
      <Head post={post} />

      <figure className="bp-hero" aria-labelledby="stairs-q">
        <div className="bp-hero-words">
          <p className="bp-q" id="stairs-q">{t('wage.hero.q')}</p>
          <p className="bp-unit">{t('wage.hero.unit')}</p>
        </div>
        <Stairs post={post} steps={x.hourly} />
        <div className="bp-hero-foot">
          <p className="bp-so"><b>{t('fig.so')}</b> {t('wage.hero.so', { first: dec(x.first.value, 2), from: x.first.at.slice(0, 4), last: dec(x.last.value, 2),
                                                                          to: x.last.at.slice(0, 4), steps: N(x.hourly.length), decrees: N(x.count) })}</p>
          <p className="bp-src">{src}</p>
          <details className="bp-table">
            <summary>{t('fig.table')}</summary>
            <div className="bp-table-scroll">
              <Table head={['', '', '', '']} rows={post.steps.map((s) => [
                s.from ? longDate(s.from, lang) : longDate(decrees[s.decree || s.issue || '']?.published ?? '', lang),
                s.hourly ? dec(s.hourly, 2) : '–', s.daily ? dec(s.daily, 2) : '–', s.decree || `BO ${s.issue}`])} />
            </div>
          </details>
        </div>
      </figure>

      <section className="bp-sec" aria-labelledby="wage-s1">
        <h2 id="wage-s1">{t('wage.s1.h')}</h2>
        {p('wage.s1.p1')}
        <Figure id="zones" q={t('wage.s1.q')} unit={t('wage.s1.unit')} source={src}
                so={t('wage.s1.so', { diff: dec((x.zones[0] - x.zones[3]) * 100, 1) })}
                pick={pz === null ? t('fig.hint') : t('wage.s1.pick', { n: pz + 1, v: dec(x.zones[pz] * 100, 1) })}
                table={<Table head={['', '']} rows={x.zones.map((z, i) => [t('wage.s1.zone', { n: i + 1 }), dec(z * 100, 1)])} />}>
          <Bars values={x.zones.map((z) => z * 100)} rtl={rtl} hi={[0]} picked={pz} onPick={setPz} height={150}
                labels={Object.fromEntries(x.zones.map((z, i) => [i, dec(z * 100, 1)]))}
                ticks={Object.fromEntries(x.zones.map((_, i) => [i, t('wage.s1.zone', { n: i + 1 })]))} aria={t('wage.s1.q')} />
        </Figure>
        {p('wage.s1.p2', { gap: x.gap, after: N(x.after), gap2: Math.floor(x.gap2.y), gapFrom: x.gap2.from.slice(0, 4), gapTo: x.gap2.to.slice(0, 4) })}
        {p('wage.s1.p3', { last: dec(x.last.value, 2), hours: N(post.hours_a_year), month: money((x.last.value * post.hours_a_year) / 12, lang) })}
      </section>

      <section className="bp-sec" aria-labelledby="wage-s2">
        <h2 id="wage-s2">{t('wage.s2.h')}</h2>
        {p('wage.s2.p1', { d1: dec(daily.find((s) => s.from && s.from >= '1975')!.daily!, 2), dN: dec(daily[daily.length - 1].daily!, 2),
                           r1: dec(r1.reduce((a, b) => a + b, 0) / r1.length, 1), rN: dec(rN.reduce((a, b) => a + b, 0) / rN.length, 1) })}
        <Figure id="ratio" q={t('wage.s2.q')} unit={t('wage.s2.unit')} source={src}
                so={t('wage.s2.so', { rN: dec(rN.reduce((a, b) => a + b, 0) / rN.length, 1) })}
                pick={pr === null ? t('fig.hint') : t('wage.s2.pick', { from: longDate(x.pairs[pr].at, lang), daily: dec(x.pairs[pr].daily, 2),
                                                                         hourly: dec(x.pairs[pr].hourly, 2), r: dec(x.pairs[pr].r, 2) })}
                table={<Table head={['', '', '', '']} rows={x.pairs.map((q) => [q.at.slice(0, 4), dec(q.daily, 2), dec(q.hourly, 2), dec(q.r, 2)])} />}>
          <Bars values={x.pairs.map((q) => q.r)} rtl={rtl} picked={pr} onPick={setPr} height={160}
                hi={x.pairs.map((q, i) => (q.at >= '2022' ? i : -1)).filter((i) => i >= 0)}
                labels={{ 0: dec(x.pairs[0].r, 2), [x.pairs.length - 1]: dec(x.pairs[x.pairs.length - 1].r, 2) }}
                ticks={{ 0: x.pairs[0].at.slice(0, 4), [x.pairs.length - 1]: x.pairs[x.pairs.length - 1].at.slice(0, 4) }} aria={t('wage.s2.q')} />
        </Figure>
      </section>

      <section className="bp-method" aria-labelledby="wage-method">
        <h2 id="wage-method">{t('wage.method.h')}</h2>
        <ul>
          {(['read', 'dates', 'gaps', 'check'] as const).map((k) => <li key={k}>{t(`wage.method.${k}`)}</li>)}
          <li>{t('wage.method.on', { on: longDate(post.counted_on, lang) })}</li>
        </ul>
      </section>
    </article>
  );
}
