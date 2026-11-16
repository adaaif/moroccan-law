import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { longDate } from '@/features/corpus/format';
import type { WaitsPost } from '../blog.api';
import { decadeTicks, n, spaced, useWidth } from '../viz';

const when = (iso: string) => { const d = new Date(`${iso}T00:00:00Z`); return d.getUTCFullYear() + d.getUTCMonth() / 12 + (d.getUTCDate() - 1) / 365; };
/** A dot's place inside its band, the same for the same law every time (no randomness in a chart). */
const jitter = (i: number) => ((i * 0.6180339887) % 1);

/**
 * The post's one picture: every law a dot, at the year of its issue and on the row of how long it waited after its
 * promulgation dahir, from «the same week» at the bottom to «more than a year» at the top; the laws that approve an
 * international agreement in the source's violet. A tap names the law and opens it.
 */
export default function Strip({ post }: { post: WaitsPost }) {
  const { t, i18n } = useTranslation('blog');
  const lang = i18n.language;
  const rtl = lang !== 'fr';
  const [ref, width] = useWidth<HTMLDivElement>(900);
  const [pick, setPick] = useState<number | null>(null);
  const f = post.figures;
  const [first, last] = f.span;
  const bands = t('waits.bands', { returnObjects: true }) as string[];
  const phone = width < 640;
  const label = phone ? 92 : 140;
  const rowH = phone ? 46 : 62, foot = 26;
  const height = bands.length * rowH + foot;
  const t0 = first, t1 = last + 1;
  const plot = width - label - 8;
  const x = (tt: number) => (rtl ? width - label - ((tt - t0) / (t1 - t0)) * plot : label + ((tt - t0) / (t1 - t0)) * plot);
  const band = (days: number) => { const i = f.bands.findIndex((b) => days <= b); return i < 0 ? f.bands.length : i; };
  // Rows from the longest wait at the top to the same week at the bottom.
  const rowY = (b: number) => (bands.length - 1 - b) * rowH;
  const dots = useMemo(() => f.laws.map((l, i) => {
    const b = band(l[1]);
    return { i, x: x(when(l[0])), y: rowY(b) + 6 + jitter(i) * (rowH - 12), agreement: l[2] === 1 };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }), [f.laws, width, rtl]);
  const chosen = pick === null ? null : f.laws[pick];
  const ticks = decadeTicks(first, last);
  return (
    <div className="bp-strip">
      <div ref={ref} className="bp-plot">
        <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} role="img" aria-label={t('waits.hero.aria')}>
          {bands.map((b, i) => (
            <g key={b}>
              <rect x={rtl ? 0 : label} y={rowY(i)} width={plot + 8} height={rowH} className={i % 2 ? 'strip-row odd' : 'strip-row'} />
              <text x={rtl ? width : 0} y={rowY(i) + rowH / 2 + 5} textAnchor="start" direction={rtl ? 'rtl' : 'ltr'} className="strip-band">{b}</text>
            </g>
          ))}
          {dots.map((d) => (
            <circle key={d.i} cx={d.x} cy={d.y} r={pick === d.i ? 6 : phone ? 2 : 2.6} className={`strip-dot${d.agreement ? ' is-agreement' : ''}${pick === d.i ? ' is-picked' : ''}`}
                    onPointerDown={() => setPick(d.i)} onPointerEnter={(e) => e.pointerType === 'mouse' && setPick(d.i)} />
          ))}
          {spaced(ticks, (i) => x(first + i + 0.5)).map(([i, year]) => (
            <text key={i} x={Math.min(Math.max(x(first + +i + 0.5), rtl ? 18 : label + 18), rtl ? width - label - 18 : width - 18)} y={height - 6} textAnchor="middle" className="is-soft">{year}</text>
          ))}
        </svg>
      </div>
      <p className="bp-pick" aria-live="polite">
        {chosen ? <>{t('waits.hero.pick', { number: chosen[3].replace('-', '.'), date: longDate(chosen[0], lang), days: n(chosen[1], lang) })}{' '}
          <Link to={chosen[5]}>{t('waits.hero.open')}</Link></> : t('waits.hero.hint')}
      </p>
    </div>
  );
}
