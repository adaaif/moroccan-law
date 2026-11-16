import { useMemo, useState, type CSSProperties } from 'react';
import { useTranslation } from 'react-i18next';
import { longDate } from '@/features/corpus/format';
import type { SixPost } from '../blog.api';
import { Figure, Table } from '../kit';
import { n } from '../viz';

/** The second post's quieter charts: what stayed of each constitution in the next, the words of each title, words
 *  counted, the days from the referendum to the Bulletin. */

const days = (a: string, b: string) => Math.round((Date.parse(b) - Date.parse(a)) / 864e5);

function useSource(post: SixPost) {
  const { t } = useTranslation('blog');
  const six = post.figures.constitutions;
  return t('fig.source', { from: six[0].year, to: six[six.length - 1].year });
}

/** Each constitution after the first as one bar of its articles: kept word for word, rewritten, unsure, new. */
export function Continuity({ post }: { post: SixPost }) {
  const { t, i18n } = useTranslation('blog');
  const lang = i18n.language;
  const src = useSource(post);
  const six = post.figures.constitutions;
  const legend = t('six.s2.legend', { returnObjects: true }) as string[];
  const [picked, setPicked] = useState<string>(t('fig.hint'));
  const rows = six.slice(1).map((con, i) => {
    const counts = [1, 2, 3, 4].map((st) => con.squares.filter((q) => q[2] === st).length);
    return { con, prev: six[i].year, counts };
  });
  const max = Math.max(...six.map((c) => c.articles));
  const last = six[six.length - 1];
  return (
    <Figure id="kept" q={t('six.s2.q')} source={src} pick={picked}
            so={t('six.s2.so', { last: last.year, same: n(rows[rows.length - 1].counts[0], lang) })}
            table={<Table head={['', ...legend]} rows={rows.map((r) => [t('six.s2.row', { year: r.con.year, prev: r.prev }), ...r.counts.map((c) => n(c, lang))])} />}>
      <div className="bp-kept">
        {rows.map((r) => (
          <div key={r.con.year} className="bp-kept-row">
            <span className="bp-kept-label">{t('six.s2.row', { year: r.con.year, prev: r.prev })}</span>
            <span className="bp-kept-bar" style={{ '--w': r.con.articles / max } as CSSProperties}>
              {r.counts.map((c, k) => (c ? (
                <button key={k} type="button" className={`s${k + 1}`} style={{ flexGrow: c }}
                        aria-label={`${legend[k]}: ${n(c, lang)}`}
                        onClick={() => setPicked(t('six.s2.pick', { year: r.con.year, n: n(c, lang), state: legend[k] }))}>
                  {c / r.con.articles > 0.07 ? n(c, lang) : ''}
                </button>
              ) : null))}
            </span>
          </div>
        ))}
        <div className="bp-kept-key" aria-hidden="true">
          {legend.map((l, k) => <span key={l}><i className={`s${k + 1}`} />{l}</span>)}
        </div>
      </div>
    </Figure>
  );
}

/** A grid: a row a theme or a word, a column a constitution, each cell a mark as large as its number. */
function Grid({ rows, years, mark, label, onPick }: {
  rows: { key: string; name: string; values: (number | null)[]; hi?: boolean[] }[];
  years: number[];
  mark: 'bar' | 'dot';
  label: (v: number) => string;
  onPick: (row: number, col: number) => void;
}) {
  const max = Math.max(...rows.flatMap((r) => r.values.map((v) => v ?? 0)));
  return (
    <div className="bp-grid" role="table">
      <div className="bp-grid-row bp-grid-head" role="row">
        <span role="columnheader" />
        {years.map((y) => <span key={y} role="columnheader">{y}</span>)}
      </div>
      {rows.map((r, i) => (
        <div key={r.key} className="bp-grid-row" role="row">
          <span className="bp-grid-name" role="rowheader">{r.name}</span>
          {r.values.map((v, j) => (
            <button key={j} type="button" role="cell" className={`bp-cell ${mark}${r.hi?.[j] ? ' is-hi' : ''}${v ? '' : ' is-zero'}`}
                    disabled={v === null} onClick={() => onPick(i, j)}
                    style={{ '--v': v ? (mark === 'dot' ? Math.sqrt(v / max) : v / max) : 0 } as CSSProperties}>
              {v === null ? <span className="bp-cell-none">–</span> : <><i aria-hidden="true" /><b>{label(v)}</b></>}
            </button>
          ))}
        </div>
      ))}
    </div>
  );
}

/** The words of each theme's title in each constitution; violet where a theme first appears. */
export function Themes({ post }: { post: SixPost }) {
  const { t, i18n } = useTranslation('blog');
  const lang = i18n.language;
  const src = useSource(post);
  const six = post.figures.constitutions;
  const [picked, setPicked] = useState<string>(t('fig.hint'));
  const rows = useMemo(() => post.themes.map((th) => {
    const values = six.map((c) => {
      const titles = c.titles.filter((x) => x.theme === th.key);
      return titles.length ? titles.reduce((a, x) => a + x.words, 0) : null;
    });
    const firstAt = values.findIndex((v) => v !== null);
    return { key: th.key, name: lang === 'fr' ? th.fr : th.ar, values, hi: values.map((_, j) => j === firstAt && j > 0) };
  }).filter((r) => r.values.some((v) => v !== null)), [post.themes, six, lang]);
  const parl = rows.find((r) => r.key === 'parliament')!;
  const years = six.map((c) => c.year);
  return (
    <Figure id="titles" q={t('six.s3.q')} unit={t('six.s3.unit')} source={src} pick={picked}
            so={t('six.s3.so', { first: years[0], last: years[years.length - 1], parl1: n(parl.values[0] ?? 0, lang), parlN: n(parl.values[years.length - 1] ?? 0, lang) })}
            table={<Table head={['', ...years.map(String)]} rows={rows.map((r) => [r.name, ...r.values.map((v) => (v === null ? '–' : n(v, lang)))])} />}>
      <Grid rows={rows} years={years} mark="bar" label={(v) => n(v, lang)}
            onPick={(i, j) => setPicked(t('six.s3.pick', { name: rows[i].name, year: years[j], n: n(rows[i].values[j] ?? 0, lang) }))} />
    </Figure>
  );
}

/** Thirteen words, counted in each constitution. */
export function Terms({ post }: { post: SixPost }) {
  const { t, i18n } = useTranslation('blog');
  const lang = i18n.language;
  const src = useSource(post);
  const six = post.figures.constitutions;
  const years = six.map((c) => c.year);
  const [picked, setPicked] = useState<string>(t('fig.hint'));
  const rows = post.terms.map((term) => ({
    key: term.key, name: lang === 'fr' ? term.fr : term.ar, values: six.map((c) => c.terms[term.key] ?? 0),
    hi: six.map((c, j) => j === six.length - 1 && six.slice(0, -1).every((p) => !p.terms[term.key]) && Boolean(c.terms[term.key])),
  }));
  return (
    <Figure id="terms" q={t('six.s4.q')} unit={t('six.s4.unit')} source={src} pick={picked}
            so={t('six.s4.so', { last: years[years.length - 1] })}
            table={<Table head={['', ...years.map(String)]} rows={rows.map((r) => [r.name, ...r.values.map((v) => n(v, lang))])} />}>
      <Grid rows={rows} years={years} mark="dot" label={(v) => n(v, lang)}
            onPick={(i, j) => setPicked(t('six.s4.pick', { term: rows[i].name, year: years[j], n: n(rows[i].values[j] ?? 0, lang) }))} />
    </Figure>
  );
}

/** From the referendum to the dahir, and from the dahir to the Bulletin, a row a constitution. */
export function Timeline({ post }: { post: SixPost }) {
  const { t, i18n } = useTranslation('blog');
  const lang = i18n.language;
  const src = useSource(post);
  const six = post.figures.constitutions;
  const rows = six.map((c) => ({ c, sign: days(c.referendum, c.signed), print: days(c.signed, c.published) }));
  const max = Math.max(...rows.map((r) => r.sign + r.print));
  const [picked, setPicked] = useState<string>(t('fig.hint'));
  const say = (c: (typeof six)[number]) => t('six.s5.pick', {
    year: c.year, referendum: longDate(c.referendum, lang), signed: longDate(c.signed, lang), published: longDate(c.published, lang),
    issue: lang === 'fr' ? c.issue.replace('مكرر', 'bis') : c.issue });
  return (
    <Figure id="days" q={t('six.s5.q')} unit={t('six.s5.unit')} source={src} pick={picked}
            so={t('six.s5.so', { max: n(max, lang) })}
            table={<Table head={['', t('six.s5.unit')]} rows={rows.map((r) => [r.c.year, `${n(r.sign, lang)} + ${n(r.print, lang)}`])} />}>
      <div className="bp-days">
        {rows.map((r) => (
          <button key={r.c.year} type="button" className="bp-days-row" onClick={() => setPicked(say(r.c))}>
            <span className="bp-days-year">{r.c.year}</span>
            <span className="bp-days-track" style={{ '--w': (r.sign + r.print) / max } as CSSProperties}>
              <i className="sign" style={{ flexGrow: r.sign }} />
              <i className="print" style={{ flexGrow: Math.max(r.print, 0.6) }} />
            </span>
            <b>{t('six.s5.days', { n: n(r.sign + r.print, lang) })}</b>
          </button>
        ))}
      </div>
    </Figure>
  );
}
