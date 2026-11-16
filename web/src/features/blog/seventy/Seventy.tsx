import { useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { longDate } from '@/features/corpus/format';
import type { SeventyPost } from '../blog.api';
import { Head } from '../Head';
import { Table } from '../kit';
import { dec, n } from '../viz';
import { KindsChart, PricesChart, ProofChart, TextsChart, Thickest, WeekChart } from './charts';
import Piles from './Piles';
import { decades, yearRows } from './rows';
import '@/shared/design/french.css';
import '../post.css';
import './seventy.css';

/**
 * «الجريدة الرسمية من العدد 1 في صورة واحدة» (the blog's first post, chosen on 31 Oct 2026; from 1956 as
 * «سبعون سنة» until BH8 of the posts-from-No.-1 review, 6 Nov 2026): the Arabic Bulletin from No. 1 (1 February 1913) as one
 * picture, then No. 1 itself, and what the picture shows, each with its chart: the texts a year (the French edition's
 * own texts dashed apart), the days it came out, the thickest issues, the thin years checked against the Bulletin's own
 * page numbers, who writes, the price on the masthead; and how it was counted. Every figure in the prose comes from the
 * counted figures or from the meta's facts read on the pages.
 */
export default function Seventy({ post }: { post: SeventyPost }) {
  const { t, i18n } = useTranslation('blog');
  const lang = i18n.language;
  const f = post.figures;
  const [first, last] = f.span;
  const rows = useMemo(() => yearRows(f), [f]);
  const x = useMemo(() => {
    const by = (year: number) => rows.find((r) => r.year === year)!;
    const most = (key: 'pages' | 'texts' | 'bis') => rows.reduce((a, r) => (r[key] > a[key] ? r : a));
    // The thinnest year since independence; before it, the thinnest whole year (1913 counts from February).
    const least = rows.filter((r) => r.year >= 1956).reduce((a, r) => (r.pages < a.pages ? r : a));
    const leastOld = rows.filter((r) => r.year > 1913 && r.year < 1956).reduce((a, r) => (r.pages < a.pages ? r : a));
    const since = rows.filter((r) => r.year >= 2011);
    const groups = decades(rows).map((d) => {
      const texts = d.rows.reduce((a, r) => a + r.texts, 0);
      const share = (k: 'dahir' | 'order' | 'law') => (100 * d.rows.reduce((a, r) => a + r[k], 0)) / texts;
      return { from: d.from, to: d.to, dahir: share('dahir'), order: share('order'), law: share('law') };
    });
    const pct = (v: number) => (v < 1 ? dec(v, 1) : String(Math.round(v)));
    const textless = Object.values(f.issues).flat().filter((s) => !s[4]).length;
    const weekly = (year: number) => (f.weekdays[String(year)] ?? []).reduce((a, b) => a + b, 0);
    // The words from 1920: a third of 1913–1919's texts hold only their title on the site.
    const worded = rows.filter((r) => r.year >= 1920);
    const words = worded.reduce((a, r) => a + r.words, 0);
    const early = rows.filter((r) => r.year < 1920);
    const sum = (o: Record<string, number> | undefined, test: (y: number) => boolean) =>
      Object.entries(o ?? {}).reduce((a, [y, v]) => a + (test(+y) ? v : 0), 0);
    const fr = Object.entries(f.french ?? {}).reduce((a, [, v]) => a + v[1], 0);
    const frYears = Object.entries(f.french ?? {}).filter(([, v]) => v[1] > 0).map(([y]) => +y);
    return {
      first: rows[0], y56: by(1956), y73: by(1973), least, leastOld, mostPages: most('pages'), mostTexts: most('texts'), mostBis: most('bis'),
      words, readDays: Math.round(words / 200 / 60 / 8),
      earlyTexts: early.reduce((a, r) => a + r.texts, 0), earlyBare: sum(f.bare, (y) => y < 1920),
      fr, frFrom: Math.min(...frYears), frTo: Math.max(...frYears), copies: sum(f.copies, () => true),
      maxBisBefore: Math.max(...rows.filter((r) => r.year <= 2010).map((r) => r.bis)), bis2011: by(2011).bis,
      reportShare: Math.round((100 * since.reduce((a, r) => a + r.report_pages, 0)) / since.reduce((a, r) => a + r.pages, 0)),
      agree: rows.filter((r) => r.printed).length, textless, groups, pct, orderTop: groups.reduce((a, g) => (g.order > a.order ? g : a)),
      before: weekly(1995), after: weekly(1996),
    };
  }, [f, rows]);
  const N = (v: number) => n(v, lang);
  const words = (r: { words: number; pages: number; texts: number }) => ({ page: Math.round(r.words / r.pages), text: Math.round(r.words / r.texts) });
  const w73 = words(x.y73), wl = words(x.least);
  const w = post.weekdays;
  const No1 = post.first;
  const thick = f.thickest[0];
  const p = (key: string, values: Record<string, unknown> = {}) => <p className="bp-p">{t(key, values)}</p>;

  return (
    <article className="bp" lang={lang}>
      <Head post={post} />

      <figure className="bp-hero" aria-labelledby="piles-q">
        <div className="bp-hero-words">
          <p className="bp-q" id="piles-q">{t('seventy.piles.q')}</p>
          <p className="bp-unit">{t('seventy.piles.how', { from: first, to: last })}</p>
        </div>
        <Piles post={post} />
        <div className="bp-hero-foot">
          <p className="bp-so"><b>{t('fig.so')}</b> {t('seventy.piles.so', {
            year: x.mostPages.year, pages: N(x.mostPages.pages), times: Math.floor(x.mostPages.pages / x.y56.pages), first: 1956,
            one: N(thick.pages) })}</p>
          <p className="bp-src">{t('fig.source', { from: first, to: last })}</p>
          <details className="bp-table">
            <summary>{t('fig.table')}</summary>
            <div className="bp-table-scroll">
              <Table head={(['year', 'issues', 'bis', 'pages', 'texts'] as const).map((c) => t(`seventy.piles.cols.${c}`))}
                     rows={rows.map((r) => [r.year, N(r.issues), N(r.bis), N(r.pages), N(r.texts)])} />
            </div>
          </details>
        </div>
      </figure>

      <section className="bp-sec" aria-labelledby="s0">
        <h2 id="s0">{t('seventy.s0.h')}</h2>
        {p('seventy.s0.p1', { date: longDate(No1.date, lang), hijri: No1.hijri, of: No1.of[lang === 'fr' ? 'fr' : 'ar'], pages: N(No1.pages) })}
        <ol className="bp-contents">
          {No1.contents.map((c) => <li key={c.ar}>{c[lang === 'fr' ? 'fr' : 'ar']}</li>)}
        </ol>
        {p('seventy.s0.p2', { second: longDate(No1.second.date, lang), frFirst: longDate(post.french.first.date, lang), before: N(post.french.before) })}
        <p className="bp-get"><Link to={`/bo/general_ar/${No1.issue}`}>{t('seventy.s0.open')}</Link></p>
      </section>

      <section className="bp-sec" aria-labelledby="s1">
        <h2 id="s1">{t('seventy.s1.h')}</h2>
        {p('seventy.s1.p1', { first, issues: N(x.first.issues), pages: N(x.first.pages), texts: N(x.first.texts),
                              issues56: N(x.y56.issues), pages56: N(x.y56.pages), texts56: N(x.y56.texts), age: t('seventy.s1.age'),
                              pagesYear: x.mostPages.year, pagesMax: N(x.mostPages.pages), textsYear: x.mostTexts.year, textsMax: N(x.mostTexts.texts) })}
        {p('seventy.s1.p2', { last, millions: dec(x.words / 1e6, 1), days: N(x.readDays), bare: N(x.earlyBare), texts: N(x.earlyTexts) })}
        {x.fr ? p('seventy.s1.p3', { fr: N(x.fr), from: x.frFrom, to: x.frTo }) : null}
        <TextsChart post={post} rows={rows} />
      </section>

      <section className="bp-sec" aria-labelledby="s2">
        <h2 id="s2">{t('seventy.s2.h')}</h2>
        {p('seventy.s2.p1', { mon: longDate(w[1].from, lang), tue: longDate(w[2].from, lang), fri: longDate(w[3].from, lang),
                              wed: longDate(w[4].from, lang), twice: longDate(w[5].from, lang), before: N(x.before), after: N(x.after) })}
        {p('seventy.s2.p2')}
        <WeekChart post={post} />
      </section>

      <section className="bp-sec" aria-labelledby="s3">
        <h2 id="s3">{t('seventy.s3.h')}</h2>
        {p('seventy.s3.p1', { maxBefore: N(x.maxBisBefore), y2011: N(x.bis2011), max: N(x.mostBis.bis), maxYear: x.mostBis.year })}
        {p('seventy.s3.p2', { date: longDate(thick.date, lang), pages: N(thick.pages), first: 1956, firstPages: N(x.y56.pages) })}
        {p('seventy.s3.p3', { to: last, share: x.reportShare })}
        <Thickest post={post} />
      </section>

      <section className="bp-sec" aria-labelledby="s4">
        <h2 id="s4">{t('seventy.s4.h')}</h2>
        {p('seventy.s4.p1', { year: x.least.year, pages: N(x.least.pages), pages73: N(x.y73.pages), texts: N(x.least.texts), texts73: N(x.y73.texts) })}
        {p('seventy.s4.p2', { year: x.least.year, printed: N(x.least.printed), gap: N(x.least.printed - x.least.pages), agree: x.agree })}
        {p('seventy.s4.p3', { wp73: w73.page, wp: wl.page, wt73: N(w73.text), wt: N(wl.text), year: x.least.year })}
        {p('seventy.s4.p4', { year: x.leastOld.year, pages: N(x.leastOld.pages), texts: N(x.leastOld.texts) })}
        <ProofChart post={post} rows={rows} />
      </section>

      <section className="bp-sec" aria-labelledby="s5">
        <h2 id="s5">{t('seventy.s5.h')}</h2>
        {p('seventy.s5.p1', { dahirFirst: x.pct(x.groups[0].dahir), dahirLast: x.pct(x.groups[x.groups.length - 1].dahir),
                              orderFirst: x.pct(x.groups[0].order), orderMax: x.pct(x.orderTop.order), orderFrom: x.orderTop.from, orderTo: x.orderTop.to,
                              lawMax: x.pct(Math.max(...x.groups.map((g) => g.law))) })}
        <KindsChart post={post} rows={rows} />
      </section>

      <section className="bp-sec" aria-labelledby="s6">
        <h2 id="s6">{t('seventy.s6.h')}</h2>
        {p('seventy.s6.p1')}
        {p('seventy.s6.p2', { lastRead: longDate(post.price_last_read.date, lang), sub: N(post.subscription.price), subOn: longDate(post.subscription.date, lang) })}
        <PricesChart post={post} />
      </section>

      <section className="bp-method" aria-labelledby="method">
        <h2 id="method">{t('seventy.method.h')}</h2>
        <ul>
          <li>{t('seventy.method.source', { from: first, to: last, issues: N(f.totals.issues), copies: N(x.copies) })}</li>
          <li>{t('seventy.method.pages', { agree: x.agree, years: rows.length })}</li>
          <li>{t('seventy.method.texts', { textless: N(x.textless), reports: N(f.totals.report_issues) })}</li>
          <li>{t('seventy.method.words')}</li>
          {x.fr ? <li>{t('seventy.method.french', { fr: N(x.fr), from: x.frFrom, to: x.frTo })}</li> : null}
          <li>{t('seventy.method.reports')}</li>
          <li>{t('seventy.method.days')}</li>
          <li>{t('seventy.method.on', { on: longDate(f.counted.on, lang) })}</li>
        </ul>
        <p className="bp-get">
          <a href={`/api/blog/${post.slug}/years.csv`} download>{t('seventy.method.csv')}</a>
          <span>{t('seventy.method.reuse')}</span>
        </p>
      </section>
    </article>
  );
}
