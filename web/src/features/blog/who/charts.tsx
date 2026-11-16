import { useState, type CSSProperties } from 'react';
import { useTranslation } from 'react-i18next';
import type { WhoPost } from '../blog.api';
import { Bars, Figure, Table } from '../kit';
import { decadeTicks, n } from '../viz';

/** The fourth post's quieter charts: decree-laws a year, orders by ministry, orders by subject and laws by kind a
 *  decade at a time. */

function useSource(post: WhoPost) {
  return useTranslation('blog').t('fig.source', { from: post.figures.span[0], to: post.figures.span[1] });
}

const decadeName = (d: number, first: number, last: number) => `${Math.max(d, first)}–${Math.min(d + 9, last)}`;

export function DecreeLaws({ post, dl }: { post: WhoPost; dl: number }) {
  const { t, i18n } = useTranslation('blog');
  const lang = i18n.language;
  const src = useSource(post);
  const f = post.figures;
  const [picked, setPicked] = useState<number | null>(null);
  const top = f.decree_laws.indexOf(Math.max(...f.decree_laws));
  return (
    <Figure id="decree-laws" q={t('who.s1.q')} so={t('who.s1.so', { dl: n(dl, lang) })} source={src}
            pick={picked === null ? t('fig.hint') : t('who.s1.pick', { year: f.span[0] + picked, n: n(f.decree_laws[picked], lang) })}
            table={<Table head={['', '']} rows={f.decree_laws.map((v, i) => [f.span[0] + i, n(v, lang)]).filter((r) => r[1] !== '0')} />}>
      <Bars values={f.decree_laws} rtl={lang !== 'fr'} height={140} picked={picked} onPick={setPicked} hi={[]}
            labels={{ [top]: n(f.decree_laws[top], lang) }} ticks={decadeTicks(f.span[0], f.span[1])} aria={t('who.s1.q')} />
    </Figure>
  );
}

/** Orders by ministry, the longest first, each a strip as long as its orders. */
export function Ministries({ post }: { post: WhoPost }) {
  const { t, i18n } = useTranslation('blog');
  const lang = i18n.language;
  const src = useSource(post);
  const names = Object.fromEntries(post.ministries.map((m) => [m.key, lang === 'fr' ? m.fr : m.ar]));
  const rows = Object.entries(post.figures.ministries).map(([k, v]) => ({ k, v, name: names[k] ?? t('who.s2.ministryOther') }));
  const max = Math.max(...rows.map((r) => r.v));
  const edu = post.figures.ministries.education ?? 0;
  return (
    <Figure id="ministries" q={t('who.s2.q1')} unit={t('who.s2.unit1')} so={t('who.s2.so1', { edu: n(edu, lang) })} source={src}
            table={<Table head={['', '']} rows={rows.map((r) => [r.name, n(r.v, lang)])} />}>
      <ol className="bp-rank">
        {rows.map((r) => (
          <li key={r.k} className={r.k === 'education' ? 'is-hi' : r.k === 'other' ? 'is-other' : ''}>
            <span className="bp-rank-name">{r.name}</span>
            <span className="bp-rank-bar"><i style={{ '--w': r.v / max } as CSSProperties} /><b>{n(r.v, lang)}</b></span>
          </li>
        ))}
      </ol>
    </Figure>
  );
}

/** A decade a row, its texts as a bar cut by kind, each kind's count in it where it fits. */
function Decades({ post, series, order, names, hi }: {
  post: WhoPost; series: Record<string, number[]>; order: string[]; names: Record<string, string>; hi: string;
}) {
  const { t, i18n } = useTranslation('blog');
  const lang = i18n.language;
  const f = post.figures;
  const totals = f.decades.map((_, i) => order.reduce((s, k) => s + (series[k]?.[i] ?? 0), 0));
  const max = Math.max(...totals);
  const [picked, setPicked] = useState<string>(t('fig.hint'));
  return (
    <>
      <div className="bp-dec">
        {f.decades.map((d, i) => (
          <div key={d} className="bp-dec-row">
            <span className="bp-dec-label">{decadeName(d, f.span[0], f.span[1])}</span>
            <span className="bp-dec-bar" style={{ '--w': totals[i] / max } as CSSProperties}>
              {order.map((k) => {
                const v = series[k]?.[i] ?? 0;
                return v ? (
                  <button key={k} type="button" className={`seg seg-${k === hi ? 'hi' : k === 'other' ? 'other' : order.indexOf(k)}`} style={{ flexGrow: v }}
                          aria-label={`${names[k]}: ${n(v, lang)}`}
                          onClick={() => setPicked(`${decadeName(d, f.span[0], f.span[1])}: ${names[k]} ${n(v, lang)}`)}>
                    {v / max > 0.08 ? n(v, lang) : ''}
                  </button>
                ) : null;
              })}
            </span>
          </div>
        ))}
        <div className="bp-kept-key" aria-hidden="true">
          {order.map((k) => <span key={k}><i className={`seg seg-${k === hi ? 'hi' : k === 'other' ? 'other' : order.indexOf(k)}`} />{names[k]}</span>)}
        </div>
      </div>
      <p className="bp-pick" aria-live="polite">{picked}</p>
    </>
  );
}

export function Subjects({ post, eq10 }: { post: WhoPost; eq10: number }) {
  const { t, i18n } = useTranslation('blog');
  const lang = i18n.language;
  const src = useSource(post);
  const names: Record<string, string> = { ...Object.fromEntries(post.subjects.map((s) => [s.key, lang === 'fr' ? s.fr : s.ar])), other: t('who.s2.other') };
  const order = [...post.subjects.map((s) => s.key), 'other'];
  const f = post.figures;
  return (
    <Figure id="subjects" q={t('who.s2.q2')} unit={t('who.s2.unit2')} so={t('who.s2.so2', { eq10: n(eq10, lang) })} source={src}
            table={<Table head={['', ...order.map((k) => names[k])]} rows={f.decades.map((d, i) => [decadeName(d, f.span[0], f.span[1]), ...order.map((k) => n(f.subjects[k][i], lang))])} />}>
      <Decades post={post} series={f.subjects} order={order} names={names} hi="equivalence" />
    </Figure>
  );
}

export function Laws({ post, agrShare }: { post: WhoPost; agrShare: number }) {
  const { t, i18n } = useTranslation('blog');
  const lang = i18n.language;
  const src = useSource(post);
  const names: Record<string, string> = { ...Object.fromEntries(post.laws.map((s) => [s.key, lang === 'fr' ? s.fr : s.ar])), other: t('who.s3.other') };
  const order = ['other', ...post.laws.map((s) => s.key)];
  const f = post.figures;
  return (
    <Figure id="laws" q={t('who.s3.q')} unit={t('who.s3.unit')} so={t('who.s3.so', { agrShare })} source={src}
            table={<Table head={['', ...order.map((k) => names[k])]} rows={f.decades.map((d, i) => [decadeName(d, f.span[0], f.span[1]), ...order.map((k) => n(f.laws[k][i], lang))])} />}>
      <Decades post={post} series={f.laws} order={order} names={names} hi="agreement" />
    </Figure>
  );
}
