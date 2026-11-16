import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { longDate } from '@/features/corpus/format';
import type { HolidaysPost } from '../blog.api';
import { useWidth } from '../viz';

type Row = { key: string; name: string; from: string; to: string | null; hijri: boolean };

/** A day as a year with its fraction, to place it in time. */
const when = (iso: string) => { const d = new Date(`${iso}T00:00:00Z`); return d.getUTCFullYear() + d.getUTCMonth() / 12 + (d.getUTCDate() - 1) / 365; };

/**
 * The post's one picture: the private employers' paid holidays, a line each from the decree that put it on the list to
 * 2026 (or to the decree that took it off), the national days in the source's violet and the Hijri feasts in ink; a
 * thin rule for each decree that changed the list, named at its foot. A tap tells a line's or a decree's story.
 */
export default function Lines({ post }: { post: HolidaysPost }) {
  const { t, i18n } = useTranslation('blog');
  const lang = i18n.language;
  const rtl = lang !== 'fr';
  const [ref, width] = useWidth<HTMLDivElement>(900);
  const [pick, setPick] = useState<{ row?: number; text?: string } | null>(null);
  const texts = post.figures.texts;
  const lists = post.private.map((l) => ({ ...l, at: texts[l.text]?.published ?? '' }));
  const rows = useMemo<Row[]>(() => {
    const out: Row[] = [];
    for (const h of post.holidays) {
      const on = lists.map((l) => l.days.includes(h.key));
      const start = on.indexOf(true);
      if (start < 0) continue;
      const end = on.lastIndexOf(true);
      out.push({ key: h.key, name: lang === 'fr' ? h.fr : h.ar, from: lists[start].at, to: end < lists.length - 1 ? lists[end + 1].at : null,
                 hijri: Boolean(h.hijri) });
    }
    return out.sort((a, b) => a.from.localeCompare(b.from) || Number(a.hijri) - Number(b.hijri));
  }, [post.holidays, lists, lang]);

  const phone = width < 640;
  // The names take the room the longest needs, measured in the chart's type, at most half the width.
  const label = useMemo(() => {
    const ctx = typeof document === 'undefined' ? null : document.createElement('canvas').getContext('2d');
    if (ctx) ctx.font = '14px "Readex Pro", sans-serif';
    return Math.min(width * 0.5, 16 + Math.max(...rows.map((r) => (ctx ? ctx.measureText(r.name).width : r.name.length * 7.5))));
  }, [rows, width]);
  const rowH = phone ? 24 : 28, top = 10, foot = 10;
  const t0 = 1976.5, t1 = 2026.6;
  const plot = width - label - 12;
  const x = (tt: number) => (rtl ? width - label - ((tt - t0) / (t1 - t0)) * plot : label + ((tt - t0) / (t1 - t0)) * plot);
  const height = top + rows.length * rowH + foot;
  const say = () => {
    if (!pick) return t('holidays.hero.hint');
    if (pick.row !== undefined) {
      const r = rows[pick.row];
      return t(r.to ? 'holidays.hero.pickGone' : 'holidays.hero.pickDay', { day: r.name, from: r.from.slice(0, 4), to: r.to?.slice(0, 4) });
    }
    const tx = texts[pick.text!];
    return <>{t('holidays.hero.pickText', { date: longDate(tx.published, lang), title: tx.title })} <Link to={tx.path}>{t('holidays.hero.open')}</Link></>;
  };
  return (
    <div className="bp-lines">
      <div ref={ref} className="bp-plot">
        <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} role="img" aria-label={t('holidays.hero.aria')}>
          {lists.map((l) => (
            <g key={l.text} className="hl-text" onPointerDown={() => setPick({ text: l.text })}>
              <line x1={x(when(l.at))} x2={x(when(l.at))} y1={top - 4} y2={height - foot + 6} className={pick?.text === l.text ? 'is-picked' : ''} />
              <rect x={x(when(l.at)) - 8} y={top - 4} width={16} height={height - foot + 10 - top} className="hl-hit" />
            </g>
          ))}
          {rows.map((r, i) => {
            const y = top + i * rowH + rowH / 2;
            const a = x(when(r.from)), b = x(r.to ? when(r.to) : t1);
            return (
              <g key={r.key} className={`hl-row${r.hijri ? ' is-hijri' : ''}${pick?.row === i ? ' is-picked' : ''}`} onPointerDown={() => setPick({ row: i })}>
                <rect x={0} y={y - rowH / 2} width={width} height={rowH} className="hl-hit" />
                <text x={rtl ? width : 0} y={y + 5} textAnchor="start" direction={rtl ? 'rtl' : 'ltr'} className="hl-name">{r.name}</text>
                <line x1={a} x2={b} y1={y} y2={y} className="hl-bar" />
                <circle cx={a} cy={y} r={4.5} className="hl-dot" />
                {r.to ? <circle cx={b} cy={y} r={4.5} className="hl-end" /> : null}
              </g>
            );
          })}
        </svg>
      </div>
      {/* The decrees in time order, each with the days its list counts: chips, since some came weeks apart. */}
      <div className="hl-texts">
        {lists.map((l) => (
          <button key={l.text} type="button" aria-pressed={pick?.text === l.text} onClick={() => setPick({ text: l.text })}>
            <b>{l.at.slice(0, 4)}</b> {t('holidays.hero.count', { n: l.days.length })}
          </button>
        ))}
      </div>
      <p className="bp-pick" aria-live="polite">{say()}</p>
    </div>
  );
}
