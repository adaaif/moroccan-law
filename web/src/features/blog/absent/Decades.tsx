import { useTranslation } from 'react-i18next';
import { n, useWidth } from '../viz';
import { peak } from './screens';

/**
 * A machine's life in the law, decade by decade, left to right on every page: one bar a decade from the 1910s to the
 * 2020s, its height the texts of law first published that decade that write the word, against the machine's own peak
 * (each row its own scale: the telegram's peak is 315 texts, the telex's 9). The peak is named over its bar, the decades
 * at both ends under the axis. Drawn at its real width, so no word shrinks under 14 px.
 */
export function Decades({ decades, counts, aria }: { decades: number[]; counts: number[]; aria: string }) {
  const { i18n } = useTranslation('blog');
  const lang = i18n.language;
  const [ref, W] = useWidth<HTMLDivElement>(300);
  const top = peak(decades, counts);
  const H = 78, base = 54, gap = 3;
  const bw = Math.max(2, (W - gap * (decades.length - 1)) / decades.length);
  const max = Math.max(1, top.n);
  return (
    <div ref={ref} className="wa-dec" dir="ltr">
      <svg width={W} height={H} role="img" aria-label={aria}>
        <line x1={0} x2={W} y1={base + 0.5} y2={base + 0.5} className="wa-dec-rail" />
        {counts.map((c, i) => {
          const h = c ? Math.max(2, (c / max) * (base - 20)) : 0;
          const x = i * (bw + gap);
          const isPeak = decades[i] === top.decade;
          return (
            <g key={decades[i]}>
              <rect x={x} y={c ? base - h : base - 1} width={bw} height={c ? h : 1} className={c ? (isPeak ? 'is-peak' : '') : 'is-none'} />
              {isPeak ? <text x={Math.min(Math.max(x + bw / 2, 14), W - 14)} y={base - h - 6} textAnchor="middle" className="wa-dec-n">{n(c, lang)}</text> : null}
            </g>
          );
        })}
        <text x={0} y={H - 4} className="wa-dec-axis">{decades[0]}</text>
        <text x={W} y={H - 4} textAnchor="end" className="wa-dec-axis">{decades[decades.length - 1]}</text>
      </svg>
    </div>
  );
}
