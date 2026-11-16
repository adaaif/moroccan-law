import { type KeyboardEvent, type PointerEvent } from 'react';
import { useWidth } from '../viz';
import { MAX_DAYS, MIN_DAYS, place } from './time';

/**
 * Every deadline the law in force writes, on one scale of time, left to right on every page: an hour at the left, decades
 * at the right, the scale logarithmic so both show. One stick a deadline, its height the times the law writes it; the
 * picked one in ink, the others in violet (what the texts printed); the tallest named. A tap, or the arrow keys, picks one.
 */
export type Deadline = { key: string; days: number; count: number; label: string };

export function Scale({ deadlines, picked, onPick, ticks, aria, rtl }: {
  deadlines: Deadline[];
  picked: string;
  onPick: (k: string) => void;
  ticks: { days: number; label: string }[];
  aria: string;
  rtl: boolean;
}) {
  const [ref, width] = useWidth<HTMLDivElement>(640);
  const phone = width < 560;
  const m = { l: 16, r: 16 };
  const H = phone ? 230 : 260, base = H - 46;
  const x = (days: number) => m.l + place(days) * (width - m.l - m.r);
  const top = Math.max(...deadlines.map((d) => d.count));
  const order = [...deadlines].sort((a, b) => a.days - b.days);
  const keys = (e: KeyboardEvent) => {
    const by = e.key === 'ArrowRight' ? 1 : e.key === 'ArrowLeft' ? -1 : 0;
    if (!by) return;
    e.preventDefault();
    const i = order.findIndex((d) => d.key === picked);
    onPick(order[Math.min(order.length - 1, Math.max(0, i + by))].key);
  };
  // A finger finds the stick nearest it (HM30 of the hard-moment review): 75 sticks share a phone's width, some a
  // pixel apart, so no stick can be a finger wide; the whole chart is the target, and a tap or a slide picks the stick
  // nearest across, then the one whose top the finger is under.
  const near = (e: PointerEvent<SVGSVGElement>) => {
    const r = e.currentTarget.getBoundingClientRect(), px = e.clientX - r.left, py = e.clientY - r.top;
    const score = (d: Deadline) => Math.abs(x(d.days) - px) + Math.max(0, base - Math.max(3, (d.count / top) * (base - 64)) - py) * 0.3;
    const best = deadlines.reduce((a, b) => (score(b) < score(a) ? b : a));
    if (best.key !== picked) onPick(best.key);
  };
  // The tallest first, so the small ones stay on top.
  const drawn = [...deadlines].sort((a, b) => b.count - a.count);
  const labelled = new Set([...deadlines].sort((a, b) => b.count - a.count).slice(0, phone ? 3 : 6).map((d) => d.key));
  // The names stand in two rows over the sticks, every other one a row lower, in time order, each led to its stick.
  const lift = new Map(order.filter((d) => labelled.has(d.key) || d.key === picked).map((d, i) => [d.key, i % 2 ? 22 : 0]));
  return (
    <div ref={ref} className="dl-scale" dir="ltr">
      <svg width={width} height={H} role="listbox" tabIndex={0} aria-label={aria} aria-activedescendant={`dl-${picked}`} onKeyDown={keys}
           onPointerDown={(e) => { e.currentTarget.setPointerCapture?.(e.pointerId); near(e); }} onPointerMove={(e) => { if (e.buttons) near(e); }}>
        <line x1={x(MIN_DAYS)} x2={x(MAX_DAYS)} y1={base} y2={base} className="dl-rail" />
        {ticks.filter((tk) => !phone || tk.days !== 7).map((tk) => (
          <g key={tk.label}>
            <line x1={x(tk.days)} x2={x(tk.days)} y1={base} y2={base + 6} className="dl-tick" />
            <text x={x(tk.days)} y={base + 26} textAnchor="middle" className="dl-axis">{tk.label}</text>
          </g>
        ))}
        {drawn.map((d) => {
          const h = Math.max(3, (d.count / top) * (base - 64));
          const on = d.key === picked;
          return (
            <g key={d.key} id={`dl-${d.key}`} role="option" aria-selected={on} aria-label={`${d.label}: ${d.count}`} className={`dl-bub${on ? ' is-on' : ''}`}>
              <line x1={x(d.days)} x2={x(d.days)} y1={base} y2={base - h} />
              <circle cx={x(d.days)} cy={base - h} r={on ? 6 : 4.5} />
              {labelled.has(d.key) || on ? (
                <>
                  <line x1={x(d.days)} x2={x(d.days)} y1={24 + (lift.get(d.key) ?? 0)} y2={base - h - 8} className="dl-lead" />
                  <text x={x(d.days)} y={18 + (lift.get(d.key) ?? 0)} textAnchor="middle" direction={rtl ? 'rtl' : 'ltr'} className="dl-bub-label">{d.label}</text>
                </>
              ) : null}
            </g>
          );
        })}
      </svg>
    </div>
  );
}
