import { useMemo, useState, type KeyboardEvent, type PointerEvent } from 'react';
import { useTranslation } from 'react-i18next';
import type { WhoPost } from '../blog.api';
import { columnAt, decadeTicks, n, spaced, stepFor, useWidth } from '../viz';

/**
 * The post's one picture: each year a column of its texts as shares of who wrote them, the bands stacked from the King
 * at the bottom to other bodies at the top, so the ministers' violet band is seen to fill the Bulletin. Each band is
 * named inside it at both ends where it is thick enough; a tap gives the year's counts.
 */
export default function Bands({ post }: { post: WhoPost }) {
  const { t, i18n } = useTranslation('blog');
  const lang = i18n.language;
  const rtl = lang !== 'fr';
  const [ref, width] = useWidth<HTMLDivElement>(900);
  const [pick, setPick] = useState<number | null>(null);
  const f = post.figures;
  const [first, last] = f.span;
  const keys = post.authors.map((a) => a.key);
  const names = Object.fromEntries(post.authors.map((a) => [a.key, lang === 'fr' ? a.fr : a.ar]));
  const count = f.authors[keys[0]].length;
  const totals = useMemo(() => Array.from({ length: count }, (_, i) => keys.reduce((s, k) => s + f.authors[k][i], 0)), [f, keys, count]);
  const height = width < 640 ? 300 : 400, top = 8, foot = 26;
  const plot = height - top - foot;
  const step = width / count;
  const x = (i: number) => (rtl ? width - (i + 1) * step : i * step);
  // The bands' edges, a year at a time: the share of the year's texts below each band's top.
  const edges = useMemo(() => {
    const out: number[][] = [];
    let below = Array(count).fill(0);
    for (const k of keys) {
      const next = below.map((b, i) => b + (totals[i] ? f.authors[k][i] / totals[i] : 0));
      out.push(next);
      below = next;
    }
    return out;
  }, [keys, f, totals, count]);
  const y = (share: number) => top + plot * (1 - share);
  // A band's outline: its top edge in reading order, each year a flat step, then its foot back the other way.
  const area = (lo: number[], hi: number[]) => {
    const pts = (s: number[]) => Array.from({ length: count }, (_, i) => {
      const a = x(i), b = x(i) + step, h = y(s[i]).toFixed(1);
      return rtl ? [`${b.toFixed(1)},${h}`, `${a.toFixed(1)},${h}`] : [`${a.toFixed(1)},${h}`, `${b.toFixed(1)},${h}`];
    }).flat();
    return `M${pts(hi).join(' L')} L${pts(lo).reverse().join(' L')} Z`;
  };
  const zero = Array(count).fill(0);

  // A band's name inside it, at the first and the last year, where the band is 22 px thick there.
  const labels = keys.flatMap((k, b) => [0, count - 1].map((i) => {
    const lo = b ? edges[b - 1][i] : 0, hi = edges[b][i];
    if ((hi - lo) * plot < 22) return null;
    const atStart = i === 0;
    // The first year sits at the reading start (right in Arabic); its label reads inward from that edge.
    const edge = atStart === rtl ? width - 8 : 8;
    const anchor = atStart ? 'start' : 'end';
    return { key: `${k}-${i}`, x: edge, y: y((lo + hi) / 2) + 5, text: names[k], anchor, dark: k === 'ministers' };
  })).filter(Boolean) as { key: string; x: number; y: number; text: string; anchor: 'start' | 'end'; dark: boolean }[];

  const sentence = pick === null ? t('who.hero.hint') : t('who.hero.pick', {
    year: first + pick,
    list: keys.map((k) => t('who.hero.item', { who: names[k], n: n(f.authors[k][pick], lang) })).join(lang === 'fr' ? ', ' : '، '),
  });
  const move = (e: PointerEvent<SVGSVGElement>) => {
    const box = e.currentTarget.getBoundingClientRect();
    setPick(columnAt(e.clientX - box.left, box.width, count, rtl));
  };
  const key = (e: KeyboardEvent<SVGSVGElement>) => {
    const d = stepFor(e, rtl);
    if (!d) return;
    e.preventDefault();
    setPick((p) => Math.max(0, Math.min(count - 1, (p ?? (d > 0 ? -1 : count)) + d)));
  };
  const ticks = decadeTicks(first, last);
  return (
    <div className="bp-bands">
      <div ref={ref} className="bp-plot">
        <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} role="img" tabIndex={0} onKeyDown={key}
             onPointerMove={(e) => e.pointerType === 'mouse' && move(e)} onPointerDown={move}
             aria-label={t('who.hero.aria')}>
          {keys.map((k, b) => <path key={k} d={area(b ? edges[b - 1] : zero, edges[b])} className={`band band-${k}`} />)}
          {pick !== null ? <rect x={x(pick)} y={top} width={step} height={plot} className="band-pick" /> : null}
          {labels.map((l) => (
            <text key={l.key} x={l.x} y={l.y} direction={rtl ? 'rtl' : 'ltr'} textAnchor={l.anchor} className={`band-label${l.dark ? ' on-dark' : ''}`}>{l.text}</text>
          ))}
          {spaced(ticks, (i) => x(i) + step / 2).map(([i, year]) => (
            <text key={i} x={Math.min(Math.max(x(+i) + step / 2, 18), width - 18)} y={height - 6} textAnchor="middle" className="is-soft">{year}</text>
          ))}
        </svg>
      </div>
      <p className="bp-pick" aria-live="polite">{sentence}</p>
    </div>
  );
}
