import { useMemo, useState, type CSSProperties } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { longDate } from '@/features/corpus/format';
import type { AgreementsPost, Counted } from '../blog.api';
import { Head } from '../Head';
import { Bars, Figure, Table } from '../kit';
import { dec, n } from '../viz';
import Lenders from './Lenders';
import '@/shared/design/french.css';
import '../post.css';
import './agreements.css';

const REGIONS = ['africa', 'multilateral', 'europe', 'arab', 'asia', 'americas_oceania', 'organisations', 'lenders'] as const;

/** A ranked list of horizontal bars: a name, its bar, its number. */
function Rank({ items, name, hi = [] }: { items: Counted[]; name: (k: string) => string; hi?: string[] }) {
  const max = Math.max(...items.map((i) => i.n));
  // What no word named comes last, whatever its count.
  const shown = [...items.filter((i) => i.key !== 'other'), ...items.filter((i) => i.key === 'other')];
  const { i18n } = useTranslation('blog');
  return (
    <ol className="ag-rank">
      {shown.map((i) => (
        <li key={i.key} className={hi.includes(i.key) ? 'is-hi' : ''}>
          <span className="ag-rank-name">{name(i.key)}</span>
          <span className="ag-bar"><i style={{ '--w': i.n / max } as CSSProperties} /><b>{n(i.n, i18n.language)}</b></span>
        </li>
      ))}
    </ol>
  );
}

/**
 * «المغرب والعالم في الجريدة الرسمية» (the blog's tenth post): every loan and guarantee approved by decree since 1956
 * as a line on its lender's row; then the loans a decade at a time, the public bodies the State guarantees, the treaties
 * the Bulletin published to 2018 and their age when it did, the conventions edition that took them over in 2019, and
 * the laws that approve treaties by the partner's region. Every figure is computed from the counted figures.
 */
export default function Agreements({ post }: { post: AgreementsPost }) {
  const { t, i18n } = useTranslation('blog');
  const lang = i18n.language;
  const rtl = lang !== 'fr';
  const f = post.figures;
  const [first, last] = f.span;
  const N = (v: number) => n(v, lang);
  const at = (d: number) => f.decades.indexOf(d);
  const decadeName = (d: number, end = last) => `${Math.max(d, first)}–${Math.min(d + 9, end)}`;
  const years = (d: number, end = last) => Math.min(d + 9, end) - Math.max(d, first) + 1;
  const name = (k: string) => { const x = f.names[k]; return x ? (rtl ? x.ar : x.fr) : t(`agreements.borrowerOther`); };
  const short = (k: string) => { const x = f.names[k]; return x ? (rtl ? x.short_ar ?? x.ar : x.short_fr ?? x.fr) : k; };
  const x = useMemo(() => {
    const loans = f.money_per_decade.loan, guarantees = f.money_per_decade.guarantee;
    const total = f.decades.map((_, i) => loans[i] + guarantees[i]);
    const perYear = f.decades.map((d, i) => total[i] / years(d));
    const guaranteesPerYear = f.decades.map((d, i) => guarantees[i] / years(d));
    // The treaties the general edition published: to 2018, since the conventions edition took them over.
    const tDecades = f.decades.filter((d) => d <= 2010);
    const tPerYear = tDecades.map((d, i) => f.treaties_per_decade[i] / years(d, 2018));
    const lender = (k: string) => f.lenders.find((l) => l.key === k);
    const aged10 = f.ages.aged[at(2010)];
    return {
      loans, guarantees, total, perYear, guaranteesPerYear, tDecades, tPerYear, lender,
      guaranteed: guarantees.reduce((s, v) => s + v, 0), loaned: loans.reduce((s, v) => s + v, 0),
      treaties: f.treaties_per_decade.slice(0, tDecades.length).reduce((s, v) => s + v, 0), aged10,
      africa: f.law_regions.africa ?? f.decades.map(() => 0),
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [f]);
  const [p1, setP1] = useState<number | null>(null);
  const [p3, setP3] = useState<number | null>(null);
  const [p4, setP4] = useState<number | null>(null);
  const src = t('fig.source', { from: first, to: last });
  const para = (key: string, values: Record<string, unknown> = {}) => <p className="bp-p">{t(key, values)}</p>;
  const d90 = at(1990), d00 = at(2000), d10 = at(2010), d20 = at(2020);
  const region = (r: string, d: number) => (f.law_regions[r] ?? [])[d] ?? 0;
  const ends = (count: number, end = last) => ({ 0: decadeName(f.decades[0], end), [count - 1]: decadeName(f.decades[count - 1], end) });

  return (
    <article className="bp" lang={lang}>
      <Head post={post} />

      <figure className="bp-hero" aria-labelledby="ag-q">
        <div className="bp-hero-words">
          <p className="bp-q" id="ag-q">{t('agreements.hero.q')}</p>
          <p className="bp-unit">{t('agreements.hero.how', { from: first, to: last })}</p>
        </div>
        <Lenders post={post} />
        <div className="bp-hero-foot">
          <p className="bp-so"><b>{t('fig.so')}</b> {t('agreements.hero.so', { wb: N(x.lender('world_bank')?.since_2000 ?? 0), afdb: N(x.lender('afdb')?.since_2000 ?? 0),
                                                                              kfw: N(x.lender('kfw')?.since_2000 ?? 0), eib: N(x.lender('eib')?.since_2000 ?? 0) })}</p>
          <p className="bp-src">{src}</p>
        </div>
      </figure>

      <section className="bp-sec" aria-labelledby="ag-s1">
        <h2 id="ag-s1">{t('agreements.s1.h')}</h2>
        {para('agreements.s1.p1', { money: N(f.money.length), loans: N(x.loaned), guarantees: N(x.guaranteed), y90: dec(x.perYear[d90]), y20: dec(x.perYear[d20]),
                                    g10: N(x.guarantees[d10]), l10: N(x.loans[d10]) })}
        {para('agreements.s1.p2', { usa: N(x.lender('usa')?.n ?? 0), usaLast: x.lender('usa')?.last.slice(0, 4), banks: N(x.lender('banks')?.n ?? 0),
                                    banksOld: N(f.money.filter((m) => m[2] === 'banks' && m[0] < '2000').length) })}
        <div className="ag-split">
          <Figure id="ag-money" q={t('agreements.s1.q')} unit={t('agreements.s1.unit')} source={src} so={t('agreements.s1.so', { y90: dec(x.perYear[d90]), y20: dec(x.perYear[d20]) })}
                  pick={p1 === null ? t('fig.hint') : t('agreements.s1.pick', { decade: decadeName(f.decades[p1]), v: dec(x.perYear[p1]), loans: N(x.loans[p1]), guarantees: N(x.guarantees[p1]) })}
                  table={<Table head={t('agreements.s1.head', { returnObjects: true }) as string[]}
                                rows={f.decades.map((d, i) => [decadeName(d), N(x.loans[i]), N(x.guarantees[i]), dec(x.perYear[i])])} />}>
            <Bars values={x.perYear} parts={x.guaranteesPerYear} rtl={rtl} picked={p1} onPick={setP1} height={170}
                  labels={Object.fromEntries(x.perYear.flatMap((v, i) => (v ? [[i, dec(v)]] : [])))} ticks={ends(f.decades.length)} aria={t('agreements.s1.q')} />
          </Figure>
        </div>
      </section>

      <section className="bp-sec" aria-labelledby="ag-s2">
        <h2 id="ag-s2">{t('agreements.s2.h')}</h2>
        {para('agreements.s2.p1', { guarantees: N(x.guaranteed), onee: N(f.borrowers.find((b) => b.key === 'onee')?.n ?? 0),
                                    adm: N(f.borrowers.find((b) => b.key === 'adm')?.n ?? 0), masen: N(f.borrowers.find((b) => b.key === 'masen')?.n ?? 0) })}
        <Figure id="ag-borrowers" q={t('agreements.s2.q')} unit={t('agreements.s2.unit')} source={src}
                so={t('agreements.s2.so', { share: N(Math.round((100 * (f.borrowers.find((b) => b.key === 'onee')?.n ?? 0)) / x.guaranteed)) })}
                table={<Table head={['', t('agreements.s2.unit')]} rows={f.borrowers.map((b) => [name(b.key), N(b.n)])} />}>
          <Rank items={f.borrowers} name={name} hi={['onee']} />
        </Figure>
      </section>

      <section className="bp-sec" aria-labelledby="ag-s3">
        <h2 id="ag-s3">{t('agreements.s3.h')}</h2>
        {para('agreements.s3.p1', { treaties: N(x.treaties), y90: dec(x.tPerYear[d90]), y00: dec(x.tPerYear[d00]), y10: dec(x.tPerYear[d10]),
                                    m10: N(f.ages.median[d10] ?? 0), o10: N(f.ages.over_10[d10]), o20: N(f.ages.over_20[d10]), a10: N(x.aged10) })}
        <p className="bp-p">
          {t('agreements.s3.p2', { decree: post.edition.decree, issue: post.edition.issue, date: longDate(post.edition.date, lang), words: post.edition.words,
                                   last: f.last_publication ? longDate(f.last_publication, lang) : '' })}{' '}
          <Link to={post.edition.path}>{t('agreements.s3.open')}</Link>
        </p>
        <Figure id="ag-treaties" q={t('agreements.s3.q')} unit={t('agreements.s3.unit')} source={t('fig.source', { from: first, to: 2018 })}
                so={t('agreements.s3.so', { y90: dec(x.tPerYear[d90]), y10: dec(x.tPerYear[d10]) })}
                pick={p3 === null ? t('fig.hint') : t('agreements.s3.pick', { decade: decadeName(x.tDecades[p3], 2018), v: dec(x.tPerYear[p3]), n: N(f.treaties_per_decade[p3]),
                                                                               median: N(f.ages.median[p3] ?? 0) })}
                table={<Table head={t('agreements.s3.head', { returnObjects: true }) as string[]}
                              rows={x.tDecades.map((d, i) => [decadeName(d, 2018), N(f.treaties_per_decade[i]), dec(x.tPerYear[i]), f.ages.aged[i] ? N(f.ages.median[i] ?? 0) : '–',
                                                              N(f.ages.over_10[i])])} />}>
          <Bars values={x.tPerYear} rtl={rtl} hi={[d00, d10]} picked={p3} onPick={setP3} height={160}
                labels={Object.fromEntries(x.tPerYear.map((v, i) => [i, dec(v)]))} ticks={ends(x.tDecades.length, 2018)} aria={t('agreements.s3.q')} />
        </Figure>
        <Figure id="ag-oldest" q={t('agreements.s3.oldQ')} unit={t('agreements.s3.oldUnit')} source={t('fig.source', { from: first, to: 2018 })}
                so={t('agreements.s3.oldSo', { years: N(f.oldest[0].years), signed: f.oldest[0].signed, published: f.oldest[0].published.slice(0, 4) })}>
          <ol className="ag-old">
            {f.oldest.slice(0, 6).map((o) => (
              <li key={o.path}>
                <b className="ag-years">{t('agreements.s3.years', { n: N(o.years) })}</b>
                <span className="ag-when">{t('agreements.s3.when', { signed: o.signed, published: longDate(o.published, lang) })}</span>
                <Link to={o.path} className="ag-title" lang="ar" dir="rtl">{o.title}</Link>
              </li>
            ))}
          </ol>
        </Figure>
      </section>

      <section className="bp-sec" aria-labelledby="ag-s4">
        <h2 id="ag-s4">{t('agreements.s4.h')}</h2>
        {para('agreements.s4.p1', { l10: N(f.laws_per_decade[d10]), af10: N(region('africa', d10)), mu10: N(region('multilateral', d10)), eu10: N(region('europe', d10)),
                                    ar10: N(region('arab', d10)), l90: N(f.laws_per_decade[d90]), ar90: N(region('arab', d90)), af90: N(region('africa', d90)),
                                    l20: N(f.laws_per_decade[d20]), af20: N(region('africa', d20)) })}
        <div className="ag-africa">
          <Figure id="ag-laws" q={t('agreements.s4.q')} unit={t('agreements.s4.unit')} source={src}
                  so={t('agreements.s4.so', { af10: N(region('africa', d10)), l10: N(f.laws_per_decade[d10]) })}
                  pick={p4 === null ? t('fig.hint') : t('agreements.s4.pick', { decade: decadeName(f.decades[p4]), n: N(f.laws_per_decade[p4]), africa: N(x.africa[p4]) })}
                  table={<Table head={['', ...REGIONS.map((r) => t(`agreements.regions.${r}`))]}
                                rows={f.decades.map((d, i) => [decadeName(d), ...REGIONS.map((r) => N(region(r, i)))])} />}>
            <Bars values={f.laws_per_decade} parts={x.africa} rtl={rtl} picked={p4} onPick={setP4} height={170}
                  labels={Object.fromEntries(f.laws_per_decade.map((v, i) => [i, N(v)]))} ticks={ends(f.decades.length)} aria={t('agreements.s4.q')} />
          </Figure>
        </div>
        <Figure id="ag-topics" q={t('agreements.s4.topicsQ')} unit={t('agreements.s4.topicsUnit')} source={t('fig.source', { from: first, to: 2018 })}
                so={t('agreements.s4.topicsSo', { tax: N(f.topics.find((x) => x.key === 'tax')?.n ?? 0), investment: N(f.topics.find((x) => x.key === 'investment')?.n ?? 0) })}
                table={<Table head={['', t('agreements.s4.topicsUnit')]} rows={f.topics.map((x) => [t(`agreements.topics.${x.key}`), N(x.n)])} />}>
          <Rank items={f.topics} name={(k) => t(`agreements.topics.${k}`)} hi={['tax', 'investment']} />
        </Figure>
        {para('agreements.s4.p2', { partners: f.treaty_partners.filter((p) => !['multilateral', 'un', 'arab_orgs', 'eu', 'african_orgs'].includes(p.key)).slice(0, 5)
          .map((p) => `${short(p.key)} (${N(p.n)})`).join(rtl ? '، ' : ', ') })}
      </section>

      <section className="bp-method" aria-labelledby="ag-method">
        <h2 id="ag-method">{t('agreements.method.h')}</h2>
        <ul>
          <li>{t('agreements.method.read', { texts: N(f.texts) })}</li>
          <li>{t('agreements.method.what')}</li>
          <li>{t('agreements.method.partner')}</li>
          <li>{t('agreements.method.out', { domestic: N(f.sorted.domestic), other: N(f.sorted.other) })}</li>
          <li>{t('agreements.method.regions')}</li>
          <li>{t('agreements.method.age')}</li>
          <li>{t('agreements.method.edition', { decree: post.edition.decree })}</li>
          <li>{t('agreements.method.on', { on: longDate(post.counted_on, lang) })}</li>
        </ul>
      </section>
    </article>
  );
}
