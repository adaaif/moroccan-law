import { useMemo, useState, type KeyboardEvent } from 'react';
import { useTranslation } from 'react-i18next';
import type { MonthsPost } from '../blog.api';
import { monthNames, n, stepFor, useWidth } from '../viz';

/**
 * The post's one picture: seventy years as a calendar, a row a year (1956 at the top), a cell a month (January at the
 * reading start), as dark as the month's pages against its year's monthly mean; a dot where a «bis» issue came out.
 * Under it, an average year: how often each month was above its year's mean. A tap names the month.
 */
export default function Calendar({ post }: { post: MonthsPost }) {
  const { t, i18n } = useTranslation('blog');
  const lang = i18n.language;
  const rtl = lang !== 'fr';
  const [ref, width] = useWidth<HTMLDivElement>(900);
  const [pick, setPick] = useState<{ y: number; m: number } | null>(null);
  const f = post.figures;
  const [first] = f.span;
  const rows = f.months;
  const phone = width < 640;
  const names = monthNames(lang, phone ? 'short' : 'long');
  const label = phone ? 40 : 54;
  const head = 26;
  const rowH = phone ? 5 : 7;
  const cw = Math.min(64, (width - label) / 12);
  const gridW = cw * 12;
  const x0 = rtl ? width - label - gridW : label;
  const x = (m: number) => (rtl ? x0 + gridW - (m + 1) * cw : x0 + m * cw);
  const ratio = useMemo(() => rows.map((year) => {
    const mean = year.reduce((s, c) => s + c[2], 0) / 12;
    return year.map((c) => (mean ? c[2] / mean : 0));
  }), [rows]);
  const above = useMemo(() => Array.from({ length: 12 }, (_, m) => ratio.filter((r) => r[m] > 1).length), [ratio]);
  const top = head;
  const gridH = rows.length * rowH;
  const avgTop = top + gridH + 14;
  const avgH = 46;
  const height = avgTop + avgH + 24;

  const sentence = pick ? t('months.hero.pick', {
    month: monthNames(lang)[pick.m], year: first + pick.y, issues: n(rows[pick.y][pick.m][0], lang), bis: n(rows[pick.y][pick.m][1], lang),
    pages: n(rows[pick.y][pick.m][2], lang), texts: n(rows[pick.y][pick.m][3], lang),
  }) : t('months.hero.hint');
  const key = (e: KeyboardEvent<SVGSVGElement>) => {
    const d = stepFor(e, rtl);
    const cur = pick ?? { y: 0, m: 0 };
    if (d) { e.preventDefault(); setPick({ y: cur.y, m: Math.max(0, Math.min(11, cur.m + d)) }); }
    else if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault();
      setPick({ y: Math.max(0, Math.min(rows.length - 1, cur.y + (e.key === 'ArrowDown' ? 1 : -1))), m: cur.m });
    }
  };
  const maxAbove = Math.max(...above);
  return (
    <div className="bp-cal">
      <div ref={ref} className="bp-plot">
        <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} role="img" tabIndex={0} onKeyDown={key}
             aria-label={t('months.hero.aria')}>
          {names.map((name, m) => (
            <text key={name} x={x(m) + cw / 2} y={16} textAnchor="middle" className={m === 11 ? 'is-strong' : 'is-soft'}>{phone ? m + 1 : name}</text>
          ))}
          {rows.map((year, yi) => (
            <g key={yi}>
              {(first + yi) % 10 === 0 || yi === 0 || yi === rows.length - 1 ? (
                <text x={rtl ? width : 0} y={top + yi * rowH + rowH / 2 + 5} textAnchor="start" direction={rtl ? 'rtl' : 'ltr'} className="is-soft">{first + yi}</text>
              ) : null}
              {year.map((_, m) => {
                const r = ratio[yi][m];
                return (
                  <rect key={m} x={x(m) + 1} y={top + yi * rowH} width={cw - 2} height={rowH - 1}
                        className={pick && pick.y === yi && pick.m === m ? 'cal-pick' : r > 1 ? 'cal-up' : 'cal-down'}
                        style={{ opacity: r > 1 ? Math.min(1, 0.25 + (r - 1) * 0.9) : Math.max(0.25, r) }}
                        onPointerDown={() => setPick({ y: yi, m })}
                        onPointerEnter={(e) => e.pointerType === 'mouse' && setPick({ y: yi, m })} />
                );
              })}
              {year.map((cell, m) => (cell[1] ? (
                <circle key={`b${m}`} cx={x(m) + cw - (phone ? 4 : 6)} cy={top + yi * rowH + (rowH - 1) / 2} r={phone ? 1.6 : 2.2} className="cal-bis" />
              ) : null))}
            </g>
          ))}
          {above.map((v, m) => (
            <g key={`a${m}`}>
              <rect x={x(m) + 4} y={avgTop + avgH - (v / maxAbove) * avgH} width={cw - 8} height={(v / maxAbove) * avgH}
                    className={m === 11 ? 'cal-avg is-hi' : 'cal-avg'} />
              <text x={x(m) + cw / 2} y={avgTop + avgH + 18} textAnchor="middle" className={m === 11 ? 'is-strong' : 'is-soft'}>{n(v, lang)}</text>
            </g>
          ))}
        </svg>
      </div>
      <p className="bp-unit">{t('months.hero.avg')}</p>
      <p className="bp-pick" aria-live="polite">{sentence}</p>
    </div>
  );
}
