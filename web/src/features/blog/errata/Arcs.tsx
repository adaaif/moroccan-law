import { useMemo, useState, type KeyboardEvent, type PointerEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { longDate } from '@/features/corpus/format';
import type { ErrataPost } from '../blog.api';
import { decadeTicks, n, spaced, stepFor, useWidth } from '../viz';

/** A day as a year with its fraction, to place it in time. */
const when = (iso: string) => { const d = new Date(`${iso}T00:00:00Z`); return d.getUTCFullYear() + d.getUTCMonth() / 12 + (d.getUTCDate() - 1) / 365; };
const days = (a: string, b: string) => Math.round((Date.parse(b) - Date.parse(a)) / 86_400_000);
/** A text of law in the source's violet, names in a list in the corrected brown, the rest in soft ink. */
const tone = (kind: string) => (kind === 'names' ? 'is-names' : ['law', 'decree', 'order'].includes(kind) ? 'is-law' : '');

/**
 * The post's one picture: every correction an arc, from the issue that printed the mistake to the issue that put it
 * right, so the longer the wait the wider and higher the arc; under the line, the corrections each year. A tap on an
 * arc names both issues and the wait, a tap under the line reads the year; the arrows walk the corrections in time.
 */
export default function Arcs({ post }: { post: ErrataPost }) {
  const { t, i18n } = useTranslation('blog');
  const lang = i18n.language;
  const rtl = lang !== 'fr';
  const [ref, width] = useWidth<HTMLDivElement>(900);
  const [pick, setPick] = useState<{ arc?: number; year?: number } | null>(null);
  const f = post.figures;
  const [first, last] = f.span;
  const kinds = t('errata.kinds', { returnObjects: true }) as Record<string, string>;
  const issue = (k: string) => k.replace('-bis', rtl ? ' مكرر' : ' bis');
  const phone = width < 640;
  const B = phone ? 44 : 60, foot = 24;
  const t0 = first, t1 = last + 1;
  const x = (tt: number) => (rtl ? width - ((tt - t0) / (t1 - t0)) * width : ((tt - t0) / (t1 - t0)) * width);
  // One scale for every arc: its height a fixed share of its width (a half on a desk, the whole on a phone, where the
  // years are narrower), and the room above the line as high as the widest arc and its label need.
  const { arcs, A } = useMemo(() => {
    const raw = f.arcs.map(([from, to, fromIssue, toIssue, k]) => {
      const a = x(when(from)), b = x(when(to));
      return { lo: Math.min(a, b), hi: Math.max(a, b), from, to, fromIssue, toIssue, kind: f.kinds[k], days: days(from, to) };
    });
    const widest = Math.max(...raw.map((r) => r.hi - r.lo));
    const room = Math.min(phone ? 150 : 240, widest * (phone ? 1 : 0.5) + 28);
    const k = Math.min(phone ? 1 : 0.5, (room - 28) / widest);
    return { A: room, arcs: raw.map((r) => ({ ...r, cx: (r.lo + r.hi) / 2, rx: Math.max(0.6, (r.hi - r.lo) / 2), ry: Math.max(0.6, (r.hi - r.lo) * k) })) };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [f, width, rtl, phone]);
  const base = A + 2;
  const height = base + 4 + B + foot;
  const longest = arcs.reduce((m, a, i) => (a.days > arcs[m].days ? i : m), 0);
  const ymax = Math.max(...f.years);
  const yw = width / f.years.length;
  const ticks = decadeTicks(first, last);

  const nearest = (px: number, py: number) => {
    let best = -1, dist = 14;
    arcs.forEach((a, i) => {
      if (px < a.lo - 6 || px > a.hi + 6) return;
      const th = Math.atan2(Math.max(0, base - py) / a.ry, (px - a.cx) / a.rx);
      const d = Math.hypot(px - (a.cx + a.rx * Math.cos(th)), py - (base - a.ry * Math.sin(th)));
      if (d < dist) { dist = d; best = i; }
    });
    return best;
  };
  const move = (e: PointerEvent<SVGSVGElement>) => {
    const box = e.currentTarget.getBoundingClientRect();
    const px = e.clientX - box.left, py = e.clientY - box.top;
    if (py > base) {
      const i = Math.floor((rtl ? width - px : px) / yw);
      setPick({ year: Math.max(0, Math.min(f.years.length - 1, i)) });
      return;
    }
    const i = nearest(px, py);
    if (i >= 0) setPick({ arc: i });
  };
  // The arrows walk the corrections in the order they were printed.
  const order = useMemo(() => arcs.map((_, i) => i).sort((a, b) => arcs[a].to.localeCompare(arcs[b].to)), [arcs]);
  const key = (e: KeyboardEvent<SVGSVGElement>) => {
    const d = stepFor(e, rtl);
    if (!d) return;
    e.preventDefault();
    const at = pick?.arc === undefined ? (d > 0 ? -1 : order.length) : order.indexOf(pick.arc);
    setPick({ arc: order[Math.max(0, Math.min(order.length - 1, at + d))] });
  };
  const path = (a: (typeof arcs)[number]) => `M${a.lo},${base}A${a.rx},${a.ry} 0 0 1 ${a.hi},${base}`;
  const chosen = pick?.arc !== undefined ? arcs[pick.arc] : null;
  const L = arcs[longest];

  return (
    <div className="er-arcs">
      <div ref={ref} className="bp-plot">
        <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} role="img" aria-label={t('errata.hero.aria')} tabIndex={0}
             onPointerMove={(e) => e.pointerType === 'mouse' && move(e)} onPointerDown={move} onKeyDown={key}>
          <g className="er-arc-all">
            {arcs.map((a, i) => <path key={i} d={path(a)} className={tone(a.kind)} />)}
          </g>
          <text x={L.cx} y={base - L.ry - 8} textAnchor="middle" className="er-note">{t('errata.hero.longest', { years: n(Math.floor(L.days / 365.25), lang) })}</text>
          {chosen ? (
            <g className="er-arc-picked">
              <path d={path(chosen)} />
              <circle cx={x(when(chosen.from))} cy={base} r={4} /><circle cx={x(when(chosen.to))} cy={base} r={4} />
            </g>
          ) : null}
          <line className="bp-axis" x1={0} x2={width} y1={base + 0.5} y2={base + 0.5} />
          {f.years.map((v, i) => (
            <rect key={i} x={(rtl ? width - (i + 1) * yw : i * yw) + 0.5} y={base + 4} width={Math.max(1, yw - 1)} height={(v / ymax) * B}
                  className={pick?.year === i ? 'is-picked' : ''} />
          ))}
          {spaced(ticks, (i) => x(first + i + 0.5)).map(([i, year]) => (
            <text key={i} x={Math.min(Math.max(x(first + +i + 0.5), 18), width - 18)} y={height - 6} textAnchor="middle" className="is-soft">{year}</text>
          ))}
        </svg>
      </div>
      <p className="bp-pick" aria-live="polite">
        {chosen ? <>{t('errata.hero.pick', { printed: issue(chosen.toIssue), to: longDate(chosen.to, lang), corrected: issue(chosen.fromIssue),
                                             from: longDate(chosen.from, lang), days: n(chosen.days, lang), kind: kinds[chosen.kind] })}{' '}
          <Link to={`/bo/general_ar/${chosen.toIssue}`}>{t('errata.hero.open')}</Link></>
          : pick?.year !== undefined ? t('errata.hero.year', { year: first + pick.year, n: n(f.years[pick.year], lang) })
          : t('errata.hero.hint')}
      </p>
    </div>
  );
}
