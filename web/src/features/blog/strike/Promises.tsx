import { useWidth } from '../viz';
import { yearOf } from './wait';

/**
 * The organic laws the 2011 Constitution called for, a dot each on a line of years from 2011, left to right on every page:
 * the first legislature (to the election of 7 October 2016, the end article 86 set) as a band; the laws printed inside it
 * grey, stacked where they share a day; the four printed after it in violet and named; the strike bill's wait, from its
 * filing on the band's last day to the law, dashed. A tap names a law.
 */
export type Promise = { number: string; name: string; date: string };

export function Promises({ laws, band, filed, picked, onPick, labels, aria, rtl }: {
  laws: Promise[];
  band: [string, string];
  filed: string;
  picked: string;
  onPick: (n: string) => void;
  labels: { band: string };
  aria: string;
  rtl: boolean;
}) {
  const [ref, width] = useWidth<HTMLDivElement>(640);
  const phone = width < 560;
  const m = { l: 14, r: 14 };
  const X0 = 2011, X1 = 2027;
  const x = (yr: number) => m.l + ((yr - X0) / (X1 - X0)) * (width - m.l - m.r);
  const base = phone ? 176 : 190, height = base + 62, r = phone ? 6 : 7;
  // Laws printed within two months of each other share a column; each stacks upward.
  const placed: { law: Promise; cx: number; cy: number }[] = [];
  for (const law of [...laws].sort((a, b) => a.date.localeCompare(b.date))) {
    const cx = x(yearOf(law.date));
    const under = placed.filter((p) => Math.abs(p.cx - cx) < r * 2.1);
    placed.push({ law, cx: under.length ? under[0].cx : cx, cy: base - 14 - under.length * (r * 2 + 3) });
  }
  const late = (d: string) => d > band[1];
  // A late law's name under its dot, a line lower when the late law before it stands too close (26.16, 04.16).
  const lates = placed.filter((p) => late(p.law.date));
  const lift = (law: Promise): boolean => { const i = lates.findIndex((p) => p.law === law); return i > 0 && lates[i].cx - lates[i - 1].cx < 46 && !lift(lates[i - 1].law); };
  const law97 = placed.find((p) => p.law.number === '97.15');
  return (
    <div ref={ref} className="st-promises" dir="ltr">
      <svg width={width} height={height} role="img" aria-label={aria}>
        <rect x={x(yearOf(band[0]))} y={20} width={x(yearOf(band[1])) - x(yearOf(band[0]))} height={base - 20} className="st-legis" />
        {/* The band's name at its page-start edge: in a right-to-left text the anchor «start» is its right side. */}
        <text x={rtl ? x(yearOf(band[1])) - 8 : x(yearOf(band[0])) + 8} y={40} className="st-legis-words" direction={rtl ? 'rtl' : 'ltr'} textAnchor="start">{labels.band}</text>
        <line x1={x(X0)} x2={x(X1)} y1={base} y2={base} className="st-rail" />
        {[2012, 2014, 2016, 2018, 2020, 2022, 2024, 2026].map((d) => (
          <g key={d}>
            <line x1={x(d)} x2={x(d)} y1={base - 3} y2={base + 3} className="st-tick" />
            <text x={x(d)} y={base + 58} textAnchor="middle" className="st-axis">{phone && d % 4 ? '' : d}</text>
          </g>
        ))}
        {/* The strike bill's wait: an arc from its filing, on the band's last day, to the law. */}
        {law97 ? <path d={`M${x(yearOf(filed))} ${base - 14}Q${(x(yearOf(filed)) + law97.cx) / 2} ${base - 150} ${law97.cx} ${law97.cy - r}`} className="st-filed" /> : null}
        {law97 ? <circle cx={x(yearOf(filed))} cy={base - 14} r={4} className="st-filed-dot" /> : null}
        {placed.map(({ law, cx, cy }) => (
          <g key={law.number} className={`st-dot${late(law.date) ? ' is-late' : ''}${picked === law.number ? ' is-on' : ''}`} onPointerDown={() => onPick(law.number)}>
            <circle cx={cx} cy={cy} r={picked === law.number ? r + 2 : r} />
            <circle cx={cx} cy={cy} r={r + 8} className="st-hit" />
            {late(law.date) ? (
              <text x={cx} y={cy + r + 22 + (lift(law) ? 18 : 0)} textAnchor={cx > width - 40 ? 'end' : 'middle'} dx={cx > width - 40 ? 8 : 0} className="st-dot-name">{law.number}</text>
            ) : null}
          </g>
        ))}
      </svg>
    </div>
  );
}
