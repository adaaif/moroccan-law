import { useMemo, useState, type CSSProperties } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { longDate } from '@/features/corpus/format';
import type { WaitsPost } from '../blog.api';
import { Head } from '../Head';
import { Bars, Figure, Table } from '../kit';
import { n } from '../viz';
import Strip from './Strip';
import '@/shared/design/french.css';
import '../post.css';
import './waits.css';

const median = (v: number[]) => { const s = [...v].sort((a, b) => a - b); const m = s.length >> 1; return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2; };
const KINDS = ['dahir_agreement', 'order', 'decision', 'law_agreement', 'decree', 'law', 'dahir'] as const;

/**
 * «من التوقيع إلى الجريدة: كم ينتظر القانون؟» (the blog's eighth post): every law as a dot by its year and its wait; then
 * the median law and its decades, the kinds of text from the slowest (dahirs that publish an agreement) to the fastest,
 * and the laws that waited more than a year (seventeen of them published in 1993). Every figure is computed from the
 * counted figures.
 */
export default function Waits({ post }: { post: WaitsPost }) {
  const { t, i18n } = useTranslation('blog');
  const lang = i18n.language;
  const rtl = lang !== 'fr';
  const f = post.figures;
  const [first, last] = f.span;
  const N = (v: number) => n(v, lang);
  const x = useMemo(() => {
    const days = f.laws.map((l) => l[1]);
    const byDecade = f.decades.map((d) => median(f.laws.filter((l) => +l[0].slice(0, 4) >= d && +l[0].slice(0, 4) < d + 10).map((l) => l[1])));
    const lateIn93 = f.late.filter((l) => l.published.startsWith('1993'));
    return {
      median: median(days), month: Math.round((100 * days.filter((d) => d <= 30).length) / days.length), byDecade,
      d60: byDecade[f.decades.indexOf(1960)], d90: byDecade[f.decades.indexOf(1990)], d20: byDecade[f.decades.indexOf(2020)],
      lateIn93, oldest93: lateIn93.reduce((a, l) => (l.days > a.days ? l : a)), issues93: new Set(lateIn93.map((l) => l.issue)).size,
      from93: Math.min(...lateIn93.map((l) => +l.signed.slice(0, 4))), to93: Math.max(...lateIn93.map((l) => +l.signed.slice(0, 4))),
    };
  }, [f]);
  const kinds = t('waits.kinds', { returnObjects: true }) as Record<string, string>;
  const [p1, setP1] = useState<number | null>(null);
  const src = t('fig.source', { from: first, to: last });
  const decadeName = (d: number) => `${Math.max(d, first)}–${Math.min(d + 9, last)}`;
  const max = Math.max(...KINDS.map((k) => f.overall[k] ?? 0));
  const p = (key: string, values: Record<string, unknown> = {}) => <p className="bp-p">{t(key, values)}</p>;
  const shown = f.decades.map((d, i) => ({ d, v: x.byDecade[i] })).filter((r) => !Number.isNaN(r.v));

  return (
    <article className="bp" lang={lang}>
      <Head post={post} />

      <figure className="bp-hero" aria-labelledby="strip-q">
        <div className="bp-hero-words">
          <p className="bp-q" id="strip-q">{t('waits.hero.q')}</p>
          <p className="bp-unit">{t('waits.hero.how', { from: first, to: last })}</p>
        </div>
        <Strip post={post} />
        <div className="bp-hero-foot">
          <p className="bp-so"><b>{t('fig.so')}</b> {t('waits.hero.so', { share: x.month })}</p>
          <p className="bp-src">{src}</p>
        </div>
      </figure>

      <section className="bp-sec" aria-labelledby="waits-s1">
        <h2 id="waits-s1">{t('waits.s1.h', { median: N(x.median) })}</h2>
        {p('waits.s1.p1', { laws: N(f.laws.length), median: N(x.median), month: x.month, d60: N(x.d60), d90: N(x.d90), d20: N(x.d20), same: N(f.same_day) })}
        <Figure id="decades" q={t('waits.s1.q')} unit={t('waits.s1.unit')} source={src} so={t('waits.s1.so', { d20: N(x.d20) })}
                pick={p1 === null ? t('fig.hint') : t('waits.s1.pick', { decade: decadeName(shown[p1].d), days: N(shown[p1].v) })}
                table={<Table head={['', t('waits.s1.unit')]} rows={shown.map((r) => [decadeName(r.d), N(r.v)])} />}>
          <Bars values={shown.map((r) => r.v)} rtl={rtl} hi={[shown.length - 1]} picked={p1} onPick={setP1} height={160}
                labels={Object.fromEntries(shown.map((r, i) => [i, N(r.v)]))} ticks={{ 0: decadeName(shown[0].d), [shown.length - 1]: decadeName(shown[shown.length - 1].d) }}
                aria={t('waits.s1.q')} />
        </Figure>
      </section>

      <section className="bp-sec" aria-labelledby="waits-s2">
        <h2 id="waits-s2">{t('waits.s2.h')}</h2>
        {p('waits.s2.p1', { order: N(f.overall.order), decision: N(f.overall.decision), decree: N(f.overall.decree), dahirAgr: N(f.overall.dahir_agreement),
                            dahir: N(f.overall.dahir), late: N(f.late.length), lateAgr: N(f.late.filter((l) => l.agreement).length) })}
        <Figure id="kinds" q={t('waits.s2.q')} unit={t('waits.s2.unit')} source={src} so={t('waits.s2.so', { dahirAgr: N(f.overall.dahir_agreement) })}
                table={<Table head={['', t('waits.s2.unit'), '']} rows={KINDS.map((k) => [kinds[k], N(f.overall[k]), N(f.counts[k])])} />}>
          <ol className="wt-rank">
            {KINDS.map((k) => (
              <li key={k} className={k.endsWith('agreement') ? 'is-hi' : ''}>
                <span className="wt-name">{kinds[k]}<small>{t('waits.s2.n', { n: N(f.counts[k]) })}</small></span>
                <span className="wt-bar"><i style={{ '--w': f.overall[k] / max } as CSSProperties} /><b>{N(f.overall[k])}</b></span>
              </li>
            ))}
          </ol>
        </Figure>
      </section>

      <section className="bp-sec" aria-labelledby="waits-s3">
        <h2 id="waits-s3">{t('waits.s3.h')}</h2>
        {p('waits.s3.p1', { n93: N(x.lateIn93.length), fromY: x.from93, toY: x.to93, issues: N(x.issues93), oldest: x.oldest93.number.replace('-', '.'),
                            signed: longDate(x.oldest93.signed, lang), published: longDate(x.oldest93.published, lang), days: N(x.oldest93.days) })}
        <Figure id="late" q={t('waits.s3.q')} unit={t('waits.s3.unit')} source={src} so={t('waits.s3.so', { n93: N(x.lateIn93.length) })}>
          <ol className="wt-late">
            {f.late.map((l) => (
              <li key={l.number} className={l.agreement ? 'is-agreement' : ''}>
                <span className="wt-dates">{longDate(l.signed, lang)} {rtl ? '←' : '→'} {longDate(l.published, lang)}</span>
                <b className="wt-days">{t('waits.s3.days', { n: N(l.days) })}</b>
                <Link to={l.path} className="wt-title" lang="ar" dir="rtl">{l.title}</Link>
                {l.agreement ? <span className="wt-tag">{t('waits.s3.agreement')}</span> : null}
              </li>
            ))}
          </ol>
        </Figure>
      </section>

      <section className="bp-method" aria-labelledby="waits-method">
        <h2 id="waits-method">{t('waits.method.h')}</h2>
        <ul>
          <li>{t('waits.method.dates')}</li>
          <li>{t('waits.method.out', { after: N(f.left_out.after), none: N(f.left_out.no_date) })}</li>
          <li>{t('waits.method.kinds')}</li>
          <li>{t('waits.method.median')}</li>
          <li>{t('waits.method.check')}</li>
          <li>{t('waits.method.on', { on: longDate(post.counted_on, lang) })}</li>
        </ul>
      </section>
    </article>
  );
}
