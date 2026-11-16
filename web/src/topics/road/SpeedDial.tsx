import { useRef } from 'react';
import { tick } from '../kit/motion';
import { bandEdges } from './rules/speed';
import { SCENE_COLOURS, speedSign } from './scenes/signs';

const CX = 150, CY = 165, R = 118;

/** A speedometer for the speed tool (A2 of the road tools review): its arc painted by the bands of arts 184, 185 and
 *  175, the radar's margin grey, the limit as its sign on the rim, a needle the finger drags (a tick at every 10 on
 *  Android). The slider under it does the same from a keyboard. A dial is a dial: it never mirrors with the page. */
export function SpeedDial({ limit, speed, radar, onChange, label, unit }: {
  limit: number; speed: number; radar: boolean; onChange: (v: number) => void; label: string; unit: string;
}) {
  const svg = useRef<SVGSVGElement>(null);
  const last = useRef(Math.floor(speed / 10));
  const max = limit + 80;
  const ang = (v: number) => Math.PI * (1 - Math.min(Math.max(v, 0), max) / max);
  const pt = (v: number, r = R) => [CX + r * Math.cos(ang(v)), CY - r * Math.sin(ang(v))];
  const arc = (a: number, b: number, r = R) => {
    const [x1, y1] = pt(a, r), [x2, y2] = pt(Math.min(b, max), r);
    return `M${x1.toFixed(1)} ${y1.toFixed(1)} A${r} ${r} 0 0 1 ${x2.toFixed(1)} ${y2.toFixed(1)}`;
  };
  const e = bandEdges(limit, radar);
  const zones: [number, number, string][] = [
    [0, e.limit, 'var(--color-in-force)'], [e.limit, e.margin, 'var(--color-field)'], [e.margin, e.c2, 'var(--color-rule)'],
    [e.c2, e.c1, '#E0A24A'], [e.c1, e.delit, '#D9692B'], [e.delit, max, 'var(--color-repealed)'],
  ];
  const set = (v: number) => {
    const n = Math.max(0, Math.min(max, Math.round(v)));
    if (Math.floor(n / 10) !== last.current) { last.current = Math.floor(n / 10); tick(); }
    onChange(n);
  };
  const fromPointer = (ev: React.PointerEvent) => {
    const r = svg.current!.getBoundingClientRect();
    const x = ((ev.clientX - r.left) / r.width) * 300 - CX, y = CY - ((ev.clientY - r.top) / r.height) * 200;
    set((1 - Math.atan2(Math.max(y, 0), x) / Math.PI) * max);
  };
  const ticks = Array.from({ length: Math.floor(max / 20) + 1 }, (_, i) => i * 20);
  const [lx, ly] = pt(limit, R + 17);
  return (
    <div className="flex flex-col items-center gap-2" style={SCENE_COLOURS}>
      <svg ref={svg} viewBox="0 0 300 200" role="img" aria-label={label} style={{ direction: 'ltr' }} className="w-full max-w-sm cursor-grab touch-none select-none"
           onPointerDown={(ev) => { svg.current?.setPointerCapture(ev.pointerId); fromPointer(ev); }}
           onPointerMove={(ev) => { if (svg.current?.hasPointerCapture(ev.pointerId)) fromPointer(ev); }}>
        {zones.map(([a, b, c], i) => (b > a ? <path key={i} d={arc(a, b)} stroke={c} strokeWidth={18} fill="none" /> : null))}
        {ticks.map((v) => {
          const [x1, y1] = pt(v, R - 13), [x2, y2] = pt(v, R - 22), [tx, ty] = pt(v, R - 38);
          return (
            <g key={v}>
              <line x1={x1} y1={y1} x2={x2} y2={y2} stroke="var(--color-ink-soft)" strokeWidth={2} />
              <text x={tx} y={ty + 5} textAnchor="middle" fontSize={14} fill="var(--color-ink-soft)" fontFamily="var(--font-ui)">{v}</text>
            </g>
          );
        })}
        <g transform={`translate(${(lx - 16).toFixed(1)},${(ly - 16).toFixed(1)}) scale(0.32)`} dangerouslySetInnerHTML={{ __html: speedSign(limit) }} />
        <g style={{ transform: `translate(${CX}px, ${CY}px) rotate(${(-ang(speed) * 180) / Math.PI}deg)` }}
           className="motion-safe:transition-transform motion-safe:duration-150">
          <line x1={0} y1={0} x2={R - 30} y2={0} stroke="var(--color-ink)" strokeWidth={4} strokeLinecap="round" />
          <circle r={9} fill="var(--color-ink)" />
        </g>
        <text x={CX} y={CY + 30} textAnchor="middle" fontSize={22} fontWeight={700} fill="var(--color-ink)" fontFamily="var(--font-ui)">{speed} {unit}</text>
      </svg>
      <input type="range" min={20} max={max} step={1} value={speed} aria-label={label} onChange={(ev) => set(Number(ev.target.value))}
             className="w-full max-w-sm accent-[var(--t)]" dir="ltr" />
    </div>
  );
}
