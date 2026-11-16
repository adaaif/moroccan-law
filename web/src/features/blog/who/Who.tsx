import { useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { longDate } from '@/features/corpus/format';
import type { WhoPost } from '../blog.api';
import { Head } from '../Head';
import { n } from '../viz';
import Bands from './Bands';
import { DecreeLaws, Laws, Ministries, Subjects } from './charts';
import '@/shared/design/french.css';
import '../post.css';
import './who.css';

/**
 * «من يكتب القواعد التي نعيش بها؟» (the blog's fourth post): seventy years of the Bulletin's texts by who wrote them, as
 * bands of each year's shares; then the dahir's retreat and the decree-laws, the ministers' orders by ministry and by
 * subject (half of them diploma equivalences and delegations of signature), and Parliament's laws by kind. Every figure
 * in the prose comes from the counted figures.
 */
export default function Who({ post }: { post: WhoPost }) {
  const { t, i18n } = useTranslation('blog');
  const lang = i18n.language;
  const f = post.figures;
  const [first, last] = f.span;
  const N = (v: number) => n(v, lang);
  const x = useMemo(() => {
    const sum = (a: number[]) => a.reduce((s, v) => s + v, 0);
    const total = sum(Object.values(f.authors).map(sum));
    const yearTotal = (i: number) => sum(Object.values(f.authors).map((a) => a[i]));
    const lastI = f.authors.king.length - 1;
    const d = (decade: number) => f.decades.indexOf(decade);
    const decadeShare = (k: string, i: number) => {
      const from = Math.max(0, f.decades[i] - first), to = Math.min(lastI, f.decades[i] + 9 - first);
      let a = 0, all = 0;
      for (let y = from; y <= to; y++) { a += f.authors[k][y]; all += yearTotal(y); }
      return (100 * a) / all;
    };
    const lawShares = f.decades.map((_, i) => decadeShare('parliament', i));
    const laws1025 = (k: string) => f.laws[k][d(2010)] + f.laws[k][d(2020)];
    const lawsAll = Object.keys(f.laws).reduce((s, k) => s + laws1025(k), 0);
    const orders = sum(f.authors.ministers);
    const eq = sum(f.subjects.equivalence), del = sum(f.subjects.delegation);
    const dlAt = (a: number, b: number) => sum(f.decree_laws.slice(a - first, b - first + 1));
    return {
      total, orders, eq, del, lastI,
      dahir: Math.round(decadeShare('king', 0)),
      firstLaw: first + f.authors.parliament.findIndex((v) => v > 0),
      lawMax: Math.round(Math.max(...lawShares)),
      perYear: Math.round(sum(f.authors.parliament.slice(2010 - first, 2020 - first)) / 10),
      dl: dlAt(1965, 1971), dlAll: sum(f.decree_laws),
      lastMinisters: Math.round((100 * f.authors.ministers[lastI]) / yearTotal(lastI)),
      lastParliament: Math.round((100 * f.authors.parliament[lastI]) / yearTotal(lastI)),
      laws1025, lawsAll,
      eq70: f.subjects.equivalence[d(1970)], eq10: f.subjects.equivalence[d(2010)],
    };
  }, [f, first]);
  const m = f.ministries;
  const p = (key: string, values: Record<string, unknown> = {}) => <p className="bp-p">{t(key, values)}</p>;

  return (
    <article className="bp" lang={lang}>
      <Head post={post} />

      <figure className="bp-hero" aria-labelledby="bands-q">
        <div className="bp-hero-words">
          <p className="bp-q" id="bands-q">{t('who.hero.q')}</p>
          <p className="bp-unit">{t('who.hero.how', { from: first, to: last })}</p>
        </div>
        <Bands post={post} />
        <div className="bp-hero-foot">
          <p className="bp-so"><b>{t('fig.so')}</b> {t('who.hero.so', { last, ministers: x.lastMinisters, parliament: x.lastParliament })}</p>
          <p className="bp-src">{t('fig.source', { from: first, to: last })}</p>
        </div>
      </figure>

      <section className="bp-sec" aria-labelledby="who-s1">
        <h2 id="who-s1">{t('who.s1.h')}</h2>
        {p('who.s1.p1', { dahir: x.dahir, firstLaw: x.firstLaw, lawMax: x.lawMax, perYear: x.perYear })}
        {p('who.s1.p2', { dl: N(x.dl), dlAll: N(x.dlAll) })}
        <DecreeLaws post={post} dl={x.dl} />
      </section>

      <section className="bp-sec" aria-labelledby="who-s2">
        <h2 id="who-s2">{t('who.s2.h')}</h2>
        {p('who.s2.p1', { orders: N(x.orders), share: Math.round((100 * x.orders) / x.total), edu: N(m.education), agri: N(m.agriculture),
                          fin: N(m.finance), int: N(m.interior) })}
        <Ministries post={post} />
        {p('who.s2.p2', { eq: N(x.eq), del: N(x.del), both: Math.round((100 * (x.eq + x.del)) / x.orders), eq70: N(x.eq70), eq10: N(x.eq10) })}
        <Subjects post={post} eq10={x.eq10} />
      </section>

      <section className="bp-sec" aria-labelledby="who-s3">
        <h2 id="who-s3">{t('who.s3.h')}</h2>
        {p('who.s3.p1', { last, laws: N(x.lawsAll), agr: N(x.laws1025('agreement')), dl: N(x.laws1025('decree_law')), fin: N(x.laws1025('finance')),
                          other: N(x.laws1025('other')) })}
        <Laws post={post} agrShare={Math.round((100 * x.laws1025('agreement')) / x.lawsAll)} />
      </section>

      <section className="bp-method" aria-labelledby="who-method">
        <h2 id="who-method">{t('who.method.h')}</h2>
        <ul>
          <li>{t('who.method.texts', { from: first, to: last, texts: N(x.total) })}</li>
          <li>{t('who.method.who')}</li>
          <li>{t('who.method.ministries')}</li>
          <li>{t('who.method.subjects')}</li>
          <li>{t('who.method.on', { on: longDate(post.counted_on, lang) })}</li>
        </ul>
      </section>
    </article>
  );
}
