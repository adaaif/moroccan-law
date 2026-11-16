import { useMemo, useState, type CSSProperties } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { longDate } from '@/features/corpus/format';
import type { ErrataPost } from '../blog.api';
import { Head } from '../Head';
import { Bars, Figure, Table } from '../kit';
import { dec, n } from '../viz';
import Arcs from './Arcs';
import '@/shared/design/french.css';
import '../post.css';
import './errata.css';

/** Which words a correction changes: position by position when both lines have as many words, else what the longest
 *  common run of words leaves out. */
function changed(a: string[], b: string[]): [Set<number>, Set<number>] {
  if (a.length === b.length) {
    const d = new Set(a.map((w, i) => (w === b[i] ? -1 : i)).filter((i) => i >= 0));
    return [d, d];
  }
  const L = Array.from({ length: a.length + 1 }, () => Array<number>(b.length + 1).fill(0));
  for (let i = a.length - 1; i >= 0; i--) for (let j = b.length - 1; j >= 0; j--) L[i][j] = a[i] === b[j] ? L[i + 1][j + 1] + 1 : Math.max(L[i + 1][j], L[i][j + 1]);
  const keepA = new Set<number>(), keepB = new Set<number>();
  for (let i = 0, j = 0; i < a.length && j < b.length;) {
    if (a[i] === b[j]) { keepA.add(i++); keepB.add(j++); } else if (L[i + 1][j] >= L[i][j + 1]) i++; else j++;
  }
  return [new Set(a.map((_, i) => i).filter((i) => !keepA.has(i))), new Set(b.map((_, i) => i).filter((i) => !keepB.has(i)))];
}

/** A correction as the Bulletin prints it: «عوض» the line printed, its wrong words struck; «يقرأ» the line to read, its
 *  right words marked. */
function Fix({ wrong, right }: { wrong: string; right: string }) {
  const { t } = useTranslation('blog');
  const a = wrong.split(' '), b = right.split(' ');
  const [out, inn] = changed(a, b);
  const line = (words: string[], marked: Set<number>, Tag: 'del' | 'ins') => words.map((w, i) => (
    <span key={i}>{i ? ' ' : ''}{marked.has(i) ? <Tag>{w}</Tag> : w}</span>
  ));
  return (
    <dl className="er-fix">
      <dt>{t('errata.s3.wrong')}</dt><dd lang="ar" dir="rtl">{line(a, out, 'del')}</dd>
      <dt>{t('errata.s3.right')}</dt><dd lang="ar" dir="rtl">{line(b, inn, 'ins')}</dd>
    </dl>
  );
}

/**
 * «حين تصحح الجريدة الرسمية نفسها» (the blog's ninth post): every correction notice since 1956 as an arc from the issue
 * it corrects; then how often (per 1,000 texts, a decade at a time), what (names in lists, then texts), four corrections
 * as printed, and how late, to the twenty-five years of the longest. Every figure is computed from the counted figures;
 * the examples' words are the meta's, read on their pages.
 */
export default function Errata({ post }: { post: ErrataPost }) {
  const { t, i18n } = useTranslation('blog');
  const lang = i18n.language;
  const rtl = lang !== 'fr';
  const f = post.figures;
  const [first, last] = f.span;
  const N = (v: number) => n(v, lang);
  const issue = (k: string) => k.replace('-bis', rtl ? ' مكرر' : ' bis');
  const p = f.per_decade;
  const at = (d: number) => f.decades.indexOf(d);
  const x = useMemo(() => {
    const d80 = at(1980), d90 = at(1990), d20 = at(2020), since = f.decades.map((d, i) => (d >= 2000 ? i : -1)).filter((i) => i >= 0);
    const rate = f.decades.map((_, i) => (1000 * p.notices[i]) / p.texts[i]);
    const sum = (k: keyof typeof p) => since.reduce((s, i) => s + p[k][i], 0);
    const most = f.most_corrected[0];
    const ofMost = f.arcs.filter((a) => a[2] === most.issue).map((a) => a[1]).sort();
    return {
      d80, d90, d20, rate, after: sum('notices'), namesAfter: sum('names'), orderAfter: sum('order'), decreeAfter: sum('decree'),
      within: f.band_counts.slice(0, 4).reduce((s, v) => s + v, 0), most, mostLast: ofMost[ofMost.length - 1],
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [f]);
  const [p1, setP1] = useState<number | null>(null);
  const [p2, setP2] = useState<number | null>(null);
  const [p4, setP4] = useState<number | null>(null);
  const kinds = t('errata.kinds', { returnObjects: true }) as Record<string, string>;
  const bands = t('errata.s4.bands', { returnObjects: true }) as string[];
  const src = t('fig.source', { from: first, to: last });
  const decadeName = (d: number) => `${Math.max(d, first)}–${Math.min(d + 9, last)}`;
  const k = (v: number) => dec(v, 1);
  const para = (key: string, values: Record<string, unknown> = {}) => <p className="bp-p">{t(key, values)}</p>;
  const medians = f.decade_median_days.map((v) => v ?? 0);
  const bandMax = Math.max(...f.band_counts);
  const arcOf = (corrected: string, printed: string) => f.arcs.find((a) => a[2] === corrected && a[3] === printed);
  const years = (days: number) => N(Math.floor(days / 365.25));

  return (
    <article className="bp" lang={lang}>
      <Head post={post} />

      <figure className="bp-hero" aria-labelledby="er-q">
        <div className="bp-hero-words">
          <p className="bp-q" id="er-q">{t('errata.hero.q')}</p>
          <p className="bp-unit">{t('errata.hero.how', { from: first, to: last })}</p>
        </div>
        <Arcs post={post} />
        <div className="bp-hero-foot">
          <p className="bp-so"><b>{t('fig.so')}</b> {t('errata.hero.so', { median: N(f.median_days), over10: N(f.band_counts[5]) })}</p>
          <p className="bp-src">{src}</p>
        </div>
      </figure>

      <section className="bp-sec" aria-labelledby="er-s1">
        <h2 id="er-s1">{t('errata.s1.h')}</h2>
        {para('errata.s1.p1', { notices: N(f.notices), n80: N(p.notices[x.d80]), i80: N(p.issues[x.d80]), per80: N(Math.round((100 * p.notices[x.d80]) / p.issues[x.d80])),
                                k80: k(x.rate[x.d80]), k20: k(x.rate[x.d20]), t10: N(p.texts[at(2010)]), t80: N(p.texts[x.d80]) })}
        <Figure id="er-rate" q={t('errata.s1.q')} unit={t('errata.s1.unit')} source={src} so={t('errata.s1.so', { k80: k(x.rate[x.d80]), k20: k(x.rate[x.d20]) })}
                pick={p1 === null ? t('fig.hint') : t('errata.s1.pick', { decade: decadeName(f.decades[p1]), v: k(x.rate[p1]), n: N(p.notices[p1]) })}
                table={<Table head={t('errata.s1.head', { returnObjects: true }) as string[]}
                              rows={f.decades.map((d, i) => [decadeName(d), N(p.notices[i]), N(p.texts[i]), k(x.rate[i]), N(p.issues[i]), k((100 * p.notices[i]) / p.issues[i])])} />}>
          <Bars values={x.rate} rtl={rtl} hi={[x.d80]} picked={p1} onPick={setP1} height={170}
                labels={Object.fromEntries(x.rate.map((v, i) => [i, k(v)]))}
                ticks={{ 0: decadeName(f.decades[0]), [f.decades.length - 1]: decadeName(f.decades[f.decades.length - 1]) }} aria={t('errata.s1.q')} />
        </Figure>
      </section>

      <section className="bp-sec" aria-labelledby="er-s2">
        <h2 id="er-s2">{t('errata.s2.h')}</h2>
        {para('errata.s2.p1', { names80: N(p.names[x.d80]), n80: N(p.notices[x.d80]), names90: N(p.names[x.d90]), n90: N(p.notices[x.d90]),
                                namesAfter: N(x.namesAfter), after: N(x.after), orderAfter: N(x.orderAfter), decreeAfter: N(x.decreeAfter) })}
        <div className="er-names">
          <Figure id="er-kinds" q={t('errata.s2.q')} unit={t('errata.s2.unit')} source={src} so={t('errata.s2.so', { namesAfter: N(x.namesAfter) })}
                  pick={p2 === null ? t('fig.hint') : t('errata.s2.pick', { decade: decadeName(f.decades[p2]), n: N(p.notices[p2]), names: N(p.names[p2]) })}
                  table={<Table head={t('errata.s2.head', { returnObjects: true }) as string[]}
                                rows={f.decades.map((d, i) => [decadeName(d), ...(['notices', 'names', 'law', 'decree', 'order', 'other', 'index'] as const).map((c) => N(p[c][i]))])} />}>
            <Bars values={p.notices} parts={p.names} rtl={rtl} picked={p2} onPick={setP2} height={170}
                  labels={Object.fromEntries(p.notices.map((v, i) => [i, N(v)]))}
                  ticks={{ 0: decadeName(f.decades[0]), [f.decades.length - 1]: decadeName(f.decades[f.decades.length - 1]) }} aria={t('errata.s2.q')} />
          </Figure>
        </div>
      </section>

      <section className="bp-sec" aria-labelledby="er-s3">
        <h2 id="er-s3">{t('errata.s3.h')}</h2>
        {para('errata.s3.p1')}
        <ol className="er-examples">
          {post.examples.map((e) => {
            const arc = arcOf(e.corrected_issue, e.printed_issue);
            return (
              <li key={e.printed_issue}>
                <p className="er-when">{t('errata.s3.when', { corrected: issue(e.corrected_issue), printed: issue(e.printed_issue),
                                                               from: arc ? longDate(arc[0], lang) : '', to: arc ? longDate(arc[1], lang) : '',
                                                               days: arc ? N(Math.round((Date.parse(arc[1]) - Date.parse(arc[0])) / 86_400_000)) : '' })}</p>
                <p className="er-what">{rtl ? e.what.ar : e.what.fr}</p>
                <Fix wrong={e.wrong} right={e.right} />
                {rtl ? null : <p className="er-gloss">{e.gloss}</p>}
                <Link to={`/bo/general_ar/${e.printed_issue}`} className="er-open">{t('errata.s3.open')}</Link>
              </li>
            );
          })}
        </ol>
      </section>

      <section className="bp-sec" aria-labelledby="er-s4">
        <h2 id="er-s4">{t('errata.s4.h', { median: N(f.median_days) })}</h2>
        {para('errata.s4.p1', { timed: N(f.timed), week: N(f.band_counts[0]), month: N(f.band_counts[0] + f.band_counts[1]),
                                year: N(f.band_counts[4] + f.band_counts[5]), decade: N(f.band_counts[5]), d80: N(medians[x.d80]), d20: N(medians[x.d20]) })}
        <Figure id="er-bands" q={t('errata.s4.bandsQ')} unit={t('errata.s4.bandsUnit')} source={src}
                so={t('errata.s4.bandsSo', { share: N(Math.round((100 * x.within) / f.timed)) })}
                table={<Table head={['', t('errata.s4.bandsUnit')]} rows={bands.map((b, i) => [b, N(f.band_counts[i])])} />}>
          <ol className="er-rank">
            {bands.map((b, i) => (
              <li key={b} className={i < 4 ? 'is-hi' : ''}>
                <span className="er-name">{b}</span>
                <span className="er-bar"><i style={{ '--w': f.band_counts[i] / bandMax } as CSSProperties} /><b>{N(f.band_counts[i])}</b></span>
              </li>
            ))}
          </ol>
        </Figure>
        <Figure id="er-medians" q={t('errata.s4.q')} unit={t('errata.s4.unit')} source={src} so={t('errata.s4.so', { d80: N(medians[x.d80]), d20: N(medians[x.d20]) })}
                pick={p4 === null ? t('fig.hint') : t('errata.s4.pick', { decade: decadeName(f.decades[p4]), days: N(medians[p4]) })}
                table={<Table head={['', t('errata.s4.unit')]} rows={f.decades.map((d, i) => [decadeName(d), N(medians[i])])} />}>
          <Bars values={medians} rtl={rtl} hi={[x.d80]} picked={p4} onPick={setP4} height={160}
                labels={Object.fromEntries(medians.map((v, i) => [i, N(v)]))}
                ticks={{ 0: decadeName(f.decades[0]), [f.decades.length - 1]: decadeName(f.decades[f.decades.length - 1]) }} aria={t('errata.s4.q')} />
        </Figure>
        {para('errata.s4.p2', { issue: issue(x.most.issue), date: longDate(x.most.date, lang), times: N(x.most.times), last: longDate(x.mostLast, lang) })}
        <Figure id="er-late" q={t('errata.s4.lateQ')} unit={t('errata.s4.lateUnit')} source={src} so={t('errata.s4.lateSo', { years: years(f.longest[0].days) })}>
          <ol className="er-late">
            {f.longest.map((l) => (
              <li key={`${l.corrected_issue}-${l.printed_issue}`} className={['law', 'decree', 'order'].includes(l.kind) ? 'is-law' : l.kind === 'names' ? 'is-names' : ''}>
                <span className="er-dates">
                  {t('errata.s4.pair', { corrected: issue(l.corrected_issue), from: longDate(l.corrected, lang), printed: issue(l.printed_issue), to: longDate(l.printed, lang) })}
                </span>
                <b className="er-days">{t(Math.floor(l.days / 365.25) <= 10 ? 'errata.s4.yearsFew' : 'errata.s4.years', { years: years(l.days), n: N(l.days) })}</b>
                <span className="er-kind">{kinds[l.kind]}</span>
                <Link to={`/bo/general_ar/${l.printed_issue}`} className="er-open">{t('errata.s3.open')}</Link>
              </li>
            ))}
          </ol>
        </Figure>
      </section>

      <section className="bp-method" aria-labelledby="er-method">
        <h2 id="er-method">{t('errata.method.h')}</h2>
        <ul>
          <li>{t('errata.method.read')}</li>
          <li>{t('errata.method.once')}</li>
          <li>{t('errata.method.out', { none: N(f.left_out.no_issue ?? 0), after: N(f.left_out.after ?? 0), misread: N(f.left_out.misread ?? 0) })}</li>
          <li>{t('errata.method.kinds')}</li>
          <li>{t('errata.method.rate')}</li>
          <li>{t('errata.method.check')}</li>
          <li>{t('errata.method.on', { on: longDate(post.counted_on, lang) })}</li>
        </ul>
      </section>
    </article>
  );
}
