import { useWidth } from '../viz';
import { stack } from './dial';

/**
 * The ministers' orders that set a limit on a road section, one violet dot an order at its year and the speed it fixed,
 * left to right on every page; orders of one year and one speed sit side by side. The usual speeds are lines across.
 */
export function Orders({ orders, from, to, aria }: { orders: { year: number; kmh: number }[]; from: number; to: number; aria: string }) {
  const [ref, width] = useWidth<HTMLDivElement>(640);
  const phone = width < 560;
  const m = { l: 36, r: 10, t: 10, b: 30 };
  const H = phone ? 220 : 260;
  const x = (yr: number) => m.l + ((yr - from) / (to + 1 - from)) * (width - m.l - m.r);
  const y = (v: number) => H - m.b - (v / 130) * (H - m.t - m.b);
  const r = phone ? 3.2 : 4;
  const lines = [20, 40, 60, 80, 100, 120];
  const decades = Array.from({ length: Math.floor((to - from) / 10) + 2 }, (_, i) => Math.ceil(from / 10) * 10 + i * 10).filter((d) => d <= to);
  return (
    <div ref={ref} className="sp-orders" dir="ltr">
      <svg width={width} height={H} role="img" aria-label={aria}>
        {lines.map((v) => (
          <g key={v}>
            <line x1={m.l} x2={width - m.r} y1={y(v)} y2={y(v)} className="sp-grid" />
            <text x={m.l - 6} y={y(v) + 5} textAnchor="end" className="sp-axis">{v}</text>
          </g>
        ))}
        {decades.map((d) => <text key={d} x={x(d)} y={H - 8} textAnchor="middle" className="sp-axis">{d}</text>)}
        {stack(orders).map((o, i) => (
          <circle key={i} cx={x(o.year) + (o.k % 4) * (r * 1.6) - r} cy={y(o.kmh) - Math.floor(o.k / 4) * (r * 1.6)} r={r} className="sp-dot" />
        ))}
      </svg>
    </div>
  );
}
