import { useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { longDate } from '@/features/corpus/format';
import type { WordsPost } from '../blog.api';
import { Head } from '../Head';
import { dec, n } from '../viz';
import { Pairs, Roads, Stops, Titles } from './charts';
import { opening } from './opening';
import Heat from './Heat';
import '@/shared/design/french.css';
import '../post.css';
import './words.css';

/**
 * «كلمات دخلت القانون، وكلمات خرجت منه» (the blog's third post): 24 words in the texts cut since 1956, as a grid of
 * years; then each word that entered with its stops (its first mention, the first text on the subject, the steps after:
 * 31 Oct 2026), the words that left or were replaced (franc and dirham, «المعوقين» and «في وضعية إعاقة») and
 * the era words that ministries' names carried (96 % of «الاستثمار» in 1995), each with its stops. Every figure in the
 * prose comes from the counted figures, every date from a stop read on its page.
 */
export default function Words({ post }: { post: WordsPost }) {
  const { t, i18n } = useTranslation('blog');
  const lang = i18n.language;
  const f = post.figures;
  const [first, last] = f.span;
  const N = (v: number) => n(v, lang);
  const x = useMemo(() => {
    const c = Object.fromEntries(f.words.map((w) => [w.key, w]));
    const at = (year: number) => year - first;
    const permille = (k: string, i: number) => (f.texts[i] ? (1000 * c[k].years[i]) / f.texts[i] : 0);
    // The year from which the new words lead every year, not the first year they lead once (2014's 1 against 0 came
    // before 2015's 2 against 4).
    let cross = 0;
    for (let i = f.texts.length - 1; i >= 0 && c.disabled_new.years[i] > c.disabled_old.years[i]; i--) cross = first + i;
    const share = (k: string, from: number, to: number) => {
      const a = at(from), b = Math.min(at(to), f.texts.length - 1) + 1;
      const texts = f.texts.slice(a, b).reduce((x, y) => x + y, 0);
      return texts ? Math.round((100 * c[k].years.slice(a, b).reduce((x, y) => x + y, 0)) / texts) : 0;
    };
    const peak = (k: string) => c[k].years.indexOf(Math.max(...c[k].years));
    const sum = (k: string) => c[k].years.reduce((a, b) => a + b, 0);
    return { c, at, permille, cross, peak, sum, share };
  }, [f, first]);
  // A word's day: its first mention (or its first text on the subject), as its stops say; `kind` picks another stop.
  const day = (k: string, kind?: 'first' | 'subject') => {
    const w = x.c[k];
    const at = kind ? w?.stops?.find((s) => s.kind === kind)?.date : w && opening(w, first)?.date;
    return at ? longDate(at, lang) : '';
  };
  const year = (k: string, kind: 'first' | 'subject') => x.c[k]?.stops?.find((s) => s.kind === kind)?.date.slice(0, 4) ?? '';
  const p = (key: string, values: Record<string, unknown> = {}) => <p className="bp-p">{t(key, values)}</p>;
  const inv = x.peak('investment'), priv = x.peak('privatization');
  const last0 = f.texts.length - 1;

  return (
    <article className="bp" lang={lang}>
      <Head post={post} />

      <figure className="bp-hero" aria-labelledby="heat-q">
        <div className="bp-hero-words">
          <p className="bp-q" id="heat-q">{t('words.hero.q')}</p>
          <p className="bp-unit">{t('words.hero.how', { from: first, to: last })}</p>
        </div>
        <Heat post={post} />
        <div className="bp-hero-foot">
          <p className="bp-so"><b>{t('fig.so')}</b> {t('words.hero.so', { franc: Math.round(x.permille('franc', 0) / 10), from: first })}</p>
          <p className="bp-src">{t('fig.source', { from: first, to: last })}</p>
        </div>
      </figure>

      <section className="bp-sec" aria-labelledby="words-s1">
        <h2 id="words-s1">{t('words.s1.h')}</h2>
        {p('words.s1.p1', { internet: day('internet') })}
        {p('words.s1.p2', { amazigh: day('amazigh'), amazighSubject: day('amazigh', 'subject') })}
        {p('words.s1.p3', { governance: day('governance'), ai: day('ai'), covid: day('covid') })}
        <Roads post={post} />
      </section>

      <section className="bp-sec" aria-labelledby="words-s2">
        <h2 id="words-s2">{t('words.s2.h')}</h2>
        {p('words.s2.p1', { from: first, franc: N(x.c.franc.years[0]), texts: N(f.texts[0]), dirham: day('dirham', 'subject'),
                            dirham60: N(x.c.dirham.years[x.at(1960)]), sixties: x.share('dirham', 1960, 1969),
                            now: x.share('dirham', 2020, last) })}
        {p('words.s2.p2', { oldFirst: year('disabled_old', 'first'), oldLaw: year('disabled_old', 'subject'),
                            newFirst: year('disabled_new', 'first'), newLaw: year('disabled_new', 'subject'), cross: x.cross })}
        {p('words.s2.p3', { caid: dec(x.permille('caid', 0), 0), pacha: dec(x.permille('pacha', 0), 0),
                            caidN: dec(x.permille('caid', last0), 1), pachaN: dec(x.permille('pacha', last0), 1) })}
        <Pairs post={post} cross={x.cross} />
        <Stops post={post} keys={['dirham', 'franc', 'disabled_old', 'disabled_new', 'caid']} />
      </section>

      <section className="bp-sec" aria-labelledby="words-s3">
        <h2 id="words-s3">{t('words.s3.h')}</h2>
        {p('words.s3.p1', { invYear: first + inv, inv: N(x.c.investment.years[inv]), invTexts: N(f.texts[inv]),
                            invTitle: N(x.c.investment_title.years[inv]) })}
        {year('investment', 'subject') === String(first + inv) ? p('words.s3.charter', { invYear: first + inv }) : null}
        {p('words.s3.p2', { priv: N(x.c.privatization.years[priv]), privYear: first + priv, privTitle: N(x.c.privatization_title.years[priv]),
                            envTitlesShare: Math.round((100 * x.sum('environment_title')) / x.sum('environment')) })}
        <Titles post={post} />
        <Stops post={post} keys={['investment', 'privatization', 'environment', 'emergency']} />
      </section>

      <section className="bp-method" aria-labelledby="words-method">
        <h2 id="words-method">{t('words.method.h')}</h2>
        <ul>
          <li>{t('words.method.texts', { from: first, to: last, texts: N(f.texts.reduce((a, b) => a + b, 0)) })}</li>
          <li>{t('words.method.words')}</li>
          <li>{t('words.method.out')}</li>
          <li>{t('words.method.misread')}</li>
          <li>{t('words.method.read')}</li>
          <li>{t('words.method.copy', { on: longDate(post.counted_on, lang) })}</li>
        </ul>
      </section>
    </article>
  );
}
