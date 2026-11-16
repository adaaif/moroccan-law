import { useState, type KeyboardEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { longDate } from '@/features/corpus/format';
import type { WagePost } from '../blog.api';
import { dec, stepFor, useWidth } from '../viz';

export type Step = { at: string; value: number; decree: string; published: boolean };

/** A step's day as a year with its fraction, to place it on the time axis. */
const when = (iso: string) => { const d = new Date(`${iso}T00:00:00Z`); return d.getUTCFullYear() + d.getUTCMonth() / 12 + (d.getUTCDate() - 1) / 365; };

/**
 * The post's one picture: the hourly minimum wage as a staircase in time, from the first amount to today, each tread
 * a decree's amount, its riser the day it applies; a dot on each, the decrees' violet; the first, a few on the way and
 * today's named. A tap names the decree and opens it.
 */
export default function Stairs({ post, steps }: { post: WagePost; steps: Step[] }) {
  const { t, i18n } = useTranslation('blog');
  const lang = i18n.language;
  const rtl = lang !== 'fr';
  const [ref, width] = useWidth<HTMLDivElement>(900);
  const [pick, setPick] = useState<number | null>(null);
  const height = width < 640 ? 300 : 380, top = 30, foot = 26, pad = 14;
  const t0 = Math.floor(when(steps[0].at)), t1 = 2027;
  const max = Math.ceil(Math.max(...steps.map((s) => s.value)) / 5) * 5;
  const x = (tt: number) => (rtl ? width - pad - ((tt - t0) / (t1 - t0)) * (width - 2 * pad) : pad + ((tt - t0) / (t1 - t0)) * (width - 2 * pad));
  const y = (v: number) => top + (height - top - foot) * (1 - v / max);
  let d = '';
  steps.forEach((s, i) => {
    const xs = x(when(s.at)), ys = y(s.value);
    // Along the old amount to the day the new one applies, then up to it.
    d += i ? ` H${xs.toFixed(1)} V${ys.toFixed(1)}` : `M${xs.toFixed(1)},${ys.toFixed(1)}`;
  });
  d += ` H${x(t1 - 0.2).toFixed(1)}`;
  const named = new Set([0, steps.findIndex((s) => s.at >= '1990'), steps.findIndex((s) => s.at >= '2011'), steps.length - 1]);
  const decrees = post.figures.decrees;
  const chosen = pick === null ? null : steps[pick];
  const sentence = chosen ? (
    <>
      {t(chosen.published ? 'wage.hero.pickPublished' : 'wage.hero.pick', {
        value: dec(chosen.value, 2), from: longDate(chosen.at, lang), decree: decrees[chosen.decree]?.title ?? chosen.decree })}{' '}
      {decrees[chosen.decree] ? <Link to={decrees[chosen.decree].path}>{t('wage.hero.open')}</Link> : null}
    </>
  ) : t('wage.hero.hint');
  const key = (e: KeyboardEvent<SVGSVGElement>) => {
    const k = stepFor(e, rtl);
    if (!k) return;
    e.preventDefault();
    setPick((p) => Math.max(0, Math.min(steps.length - 1, (p ?? (k > 0 ? -1 : steps.length)) + k)));
  };
  const years = [1960, 1970, 1980, 1990, 2000, 2010, 2020].filter((yr) => yr >= t0);
  return (
    <div className="bp-stairs">
      <div ref={ref} className="bp-plot">
        <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} role="img" tabIndex={0} onKeyDown={key}
             aria-label={t('wage.hero.aria')}>
          {[5, 10, 15].filter((v) => v < max).map((v) => (
            <g key={v}>
              <line className="stairs-grid" x1={pad} x2={width - pad} y1={y(v)} y2={y(v)} />
              <text x={rtl ? width - pad : pad} y={y(v) - 5} textAnchor="start" direction={rtl ? 'rtl' : 'ltr'} className="is-soft">{v}</text>
            </g>
          ))}
          <line className="bp-axis" x1={pad} x2={width - pad} y1={height - foot + 0.5} y2={height - foot + 0.5} />
          <path d={d} className="stairs-line" />
          {steps.map((s, i) => (
            <g key={`${s.decree}-${s.at}`}>
              <circle cx={x(when(s.at))} cy={y(s.value)} r={pick === i ? 7 : 4.5} className={pick === i ? 'stairs-dot is-picked' : 'stairs-dot'}
                      onPointerDown={() => setPick(i)} onPointerEnter={(e) => e.pointerType === 'mouse' && setPick(i)} />
              {named.has(i) ? (
                <text x={Math.min(Math.max(x(when(s.at)), 24), width - 24)} y={y(s.value) - 12} textAnchor="middle" className="is-strong">{dec(s.value, 2)}</text>
              ) : null}
            </g>
          ))}
          {years.map((yr) => <text key={yr} x={x(yr)} y={height - 6} textAnchor="middle" className="is-soft">{yr}</text>)}
        </svg>
      </div>
      <p className="bp-pick" aria-live="polite">{sentence}</p>
    </div>
  );
}
