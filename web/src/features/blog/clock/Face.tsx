/**
 * A clock face drawn as a watchmaker draws one: sixty ticks, twelve longer, three hands, nothing else. The hour the law
 * adds is the face's one colour: the sector from the hour Greenwich shows to the hour Morocco shows, in the post's gold.
 * Angles are degrees from twelve, clockwise; the face is never mirrored (a clock reads the same on an Arabic page).
 */
import type { Hands } from './time';

function sector(r: number, from: number, to: number): string {
  if (Math.abs(to - from) < 0.01) return '';
  const p = (a: number) => [r * Math.sin((a * Math.PI) / 180), -r * Math.cos((a * Math.PI) / 180)];
  const [x1, y1] = p(from), [x2, y2] = p(to);
  const large = Math.abs(to - from) > 180 ? 1 : 0;
  return `M0 0L${x1.toFixed(2)} ${y1.toFixed(2)}A${r} ${r} 0 ${large} 1 ${x2.toFixed(2)} ${y2.toFixed(2)}Z`;
}

export function Face({ size, at, gold, label, secondHand = true, className = '' }: {
  size: number;
  at: Hands;
  /** The added hour as a sector, in degrees from twelve: [from, to]. */
  gold?: [number, number] | null;
  label?: string;
  secondHand?: boolean;
  className?: string;
}) {
  const r = 100;
  const ticks = Array.from({ length: 60 }, (_, i) => i);
  return (
    <svg className={`ck-face ${className}`} width={size} height={size} viewBox="-110 -110 220 220" role="img" aria-label={label} direction="ltr">
      <circle r={r + 6} className="ck-face-rim" />
      <circle r={r} className="ck-face-dial" />
      {gold && gold[1] > gold[0] ? <path d={sector(r - 2, gold[0], gold[1])} className="ck-face-gold" /> : null}
      {ticks.map((i) => {
        const big = i % 5 === 0;
        return <line key={i} y1={-r + 4} y2={-r + (big ? 15 : 8)} transform={`rotate(${i * 6})`} className={big ? 'ck-tick-h' : 'ck-tick-m'} />;
      })}
      <line y1={10} y2={-52} style={{ transform: `rotate(${at.hour}deg)` }} className="ck-hand-h" />
      <line y1={14} y2={-80} style={{ transform: `rotate(${at.minute}deg)` }} className="ck-hand-m" />
      {secondHand && at.second !== undefined ? (
        <g style={{ transform: `rotate(${at.second}deg)` }} className="ck-hand-s"><line y1={18} y2={-88} /><circle r={3.2} /></g>
      ) : null}
      <circle r={4.5} className="ck-hand-cap" />
    </svg>
  );
}
