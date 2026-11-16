import { useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { longDate } from '@/features/corpus/format';
import type { SixPost } from '../blog.api';
import { Head } from '../Head';
import { n } from '../viz';
import { Continuity, Terms, Themes, Timeline } from './charts';
import Squares from './Squares';
import '@/shared/design/french.css';
import '../post.css';
import './six.css';

const days = (a: string, b: string) => Math.round((Date.parse(b) - Date.parse(a)) / 864e5);

/**
 * «ستة دساتير في صفحة واحدة» (the blog's second post): the six constitutions side by side, a square an article coloured
 * by what became of it since the one before; then their lengths, what stayed word for word (four articles in 2011, each
 * quoted), the titles as themes, words counted, and the days from the referendum to the Bulletin. Every figure in the
 * prose comes from the counted figures.
 */
export default function Six({ post }: { post: SixPost }) {
  const { t, i18n } = useTranslation('blog');
  const lang = i18n.language;
  const six = post.figures.constitutions;
  const first = six[0], last = six[six.length - 1], prev = six[six.length - 2];
  const N = (v: number) => n(v, lang);
  const x = useMemo(() => {
    const by = (year: number) => six.find((c) => c.year === year)!;
    const states = (c: (typeof six)[number], st: number) => c.squares.filter((q) => q[2] === st).length;
    const theme = (c: (typeof six)[number], key: string) => c.titles.filter((ti) => ti.theme === key).reduce((a, ti) => a + ti.articles, 0);
    const mid = six.slice(1, -1).map((c) => c.articles);
    return {
      by, states, theme, minMid: Math.min(...mid), maxMid: Math.max(...mid),
      kept: last.squares.filter((q) => q[2] === 1).map((q) => q[0]),
    };
  }, [six, last]);
  const term = (c: (typeof six)[number], k: string) => N(c.terms[k] ?? 0);
  const p = (key: string, values: Record<string, unknown> = {}) => <p className="bp-p">{t(key, values)}</p>;
  const bodies = Object.fromEntries(last.quotes);

  return (
    <article className="bp" lang={lang}>
      <Head post={post} />

      <figure className="bp-hero" aria-labelledby="sq-q">
        <div className="bp-hero-words">
          <p className="bp-q" id="sq-q">{t('six.hero.q')}</p>
          <p className="bp-unit">{t('six.hero.how', { first: first.year, last: last.year })}</p>
        </div>
        <Squares post={post} />
        <div className="bp-hero-foot">
          <p className="bp-so"><b>{t('fig.so')}</b> {t('six.hero.so', { last: last.year, prev: prev.year, same: N(x.states(last, 1)), fresh: N(x.states(last, 4)) })}</p>
          <p className="bp-src">{t('fig.source', { from: first.year, to: last.year })}</p>
        </div>
      </figure>

      <section className="bp-sec" aria-labelledby="six-s1">
        <h2 id="six-s1">{t('six.s1.h')}</h2>
        {p('six.s1.p1', { first: first.year, arts1: N(first.articles), minMid: N(x.minMid), maxMid: N(x.maxMid), last: last.year,
                          artsN: N(last.articles), wordsN: N(last.words), words1: N(first.words), preN: N(last.preamble), pre1: N(first.preamble) })}
      </section>

      <section className="bp-sec" aria-labelledby="six-s2">
        <h2 id="six-s2">{t('six.s2.h')}</h2>
        {p('six.s2.p1', { same72: N(x.states(x.by(1972), 1)), arts72: N(x.by(1972).articles), same92: N(x.states(x.by(1992), 1)), same96: N(x.states(x.by(1996), 1)) })}
        {p('six.s2.p2', { last: last.year, prev: prev.year, same: N(x.kept.length) })}
        <ol className="bp-quotes">
          {x.kept.map((number) => (
            <li key={number}>
              <q lang="ar" dir="rtl">{bodies[number] ?? '…'}</q>
              <Link to={`${last.path}/art_${number}`}>{lang === 'fr' ? `Article ${number}` : `الفصل ${number}`}</Link>
            </li>
          ))}
        </ol>
        {p('six.s2.p3', { fresh: N(x.states(last, 4)), prev: prev.year, unsure: N(x.states(last, 3)) })}
        <Continuity post={post} />
      </section>

      <section className="bp-sec" aria-labelledby="six-s3">
        <h2 id="six-s3">{t('six.s3.h')}</h2>
        {p('six.s3.p1')}
        {p('six.s3.p2', { last: last.year, titlesN: N(last.titles.length), rights: N(x.theme(last, 'rights')), jud: N(x.theme(last, 'judiciary')),
                          judPrev: N(x.theme(prev, 'judiciary')), gov: N(x.theme(last, 'governance')) })}
        <Themes post={post} />
      </section>

      <section className="bp-sec" aria-labelledby="six-s4">
        <h2 id="six-s4">{t('six.s4.h')}</h2>
        {p('six.s4.p1', { first: first.year, last: last.year, king1: term(first, 'king'), kingN: term(last, 'king'), law1: term(first, 'law'),
                          lawN: term(last, 'law'), citf: term(last, 'citizens_f'), gov: term(last, 'governance'), youth: term(last, 'youth'),
                          env: term(last, 'environment'), amz: term(last, 'amazigh'), par: term(last, 'parity') })}
        {p('six.s4.p2', { last: last.year })}
        <Terms post={post} />
      </section>

      <section className="bp-sec" aria-labelledby="six-s5">
        <h2 id="six-s5">{t('six.s5.h')}</h2>
        {p('six.s5.p1', {
          days: new Intl.ListFormat(lang === 'fr' ? 'fr' : 'ar', { type: 'conjunction' })
            .format(six.map((c) => `${t('six.s5.days', { n: N(days(c.referendum, c.published)) })} (${c.year})`)),
          bis: new Intl.ListFormat(lang === 'fr' ? 'fr' : 'ar', { type: 'conjunction' })
            .format(six.filter((c) => c.issue.includes('مكرر')).map((c) => String(c.year))),
        })}
        <Timeline post={post} />
      </section>

      <section className="bp-method" aria-labelledby="six-method">
        <h2 id="six-method">{t('six.method.h')}</h2>
        <ul>
          {(['source', 'words', 'lineage', 'titles', 'terms', 'dates'] as const).map((k) => <li key={k}>{t(`six.method.${k}`)}</li>)}
          <li>{t('six.method.on', { on: longDate(post.counted_on, lang) })}</li>
        </ul>
      </section>
    </article>
  );
}
