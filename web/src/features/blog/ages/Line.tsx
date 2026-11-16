import { type KeyboardEvent, type PointerEvent } from 'react';
import { useWidth } from '../viz';
import { lifeAge, lifeX } from './life';

/**
 * A life from 0 to 66 as one line, left to right on every page: youth takes most of it (lifeX), the years where the law
 * writes almost nothing fold into a short dashed stretch. Each age a law writes is a violet notch; the reader's years are
 * the ink line from 0 to their mark. The line is the age control: a finger or the mouse sets the age anywhere on it,
 * the arrows move a year, Page Up and Page Down jump to the next or the last age a law writes.
 */
export function Line({ age, ages, onAge, label, valueText }: {
  age: number;
  /** The ages the laws write, each once. */
  ages: number[];
  onAge: (a: number) => void;
  label: string;
  valueText: string;
}) {
  const [ref, width] = useWidth<HTMLDivElement>(640);
  const m = 14, W = width - 2 * m, base = 46, height = 78;
  const x = (a: number) => m + lifeX(a) * W;
  const set = (e: PointerEvent<SVGSVGElement>) => {
    const box = e.currentTarget.getBoundingClientRect();
    onAge(lifeAge((e.clientX - box.left - m) / W));
  };
  const down = (e: PointerEvent<SVGSVGElement>) => { e.currentTarget.setPointerCapture(e.pointerId); set(e); };
  const move = (e: PointerEvent<SVGSVGElement>) => { if (e.buttons) set(e); };
  const key = (e: KeyboardEvent<SVGSVGElement>) => {
    const later = ages.filter((a) => a > age), earlier = ages.filter((a) => a < age);
    const to = e.key === 'ArrowRight' || e.key === 'ArrowUp' ? age + 1
      : e.key === 'ArrowLeft' || e.key === 'ArrowDown' ? age - 1
      : e.key === 'PageUp' ? (later[0] ?? age)
      : e.key === 'PageDown' ? (earlier[earlier.length - 1] ?? age)
      : e.key === 'Home' ? 0 : e.key === 'End' ? 66 : null;
    if (to === null) return;
    e.preventDefault();
    onAge(Math.max(0, Math.min(66, to)));
  };
  // The numerals under the notches: each kept when it stands clear of the last one kept.
  const shown: number[] = [];
  for (const a of ages) if (!shown.length || x(a) - x(shown[shown.length - 1]) >= 24) shown.push(a);
  const fold = [x(26), x(54)];
  return (
    <div ref={ref} className="ag-line" dir="ltr">
      <svg width={width} height={height} role="slider" tabIndex={0} aria-label={label} aria-valuemin={0} aria-valuemax={66}
           aria-valuenow={age} aria-valuetext={valueText} onPointerDown={down} onPointerMove={move} onKeyDown={key}>
        {/* The years: a tick each, the folded stretch dashed. */}
        <line x1={m} x2={fold[0]} y1={base} y2={base} className="ag-rail" />
        <line x1={fold[0]} x2={fold[1]} y1={base} y2={base} className="ag-rail is-fold" />
        <line x1={fold[1]} x2={width - m} y1={base} y2={base} className="ag-rail" />
        {Array.from({ length: 67 }, (_, a) => a).filter((a) => a <= 26 || a >= 54).map((a) => (
          <line key={a} x1={x(a)} x2={x(a)} y1={base - 3} y2={base + 3} className="ag-tick" />
        ))}
        {/* The reader's years. */}
        <line x1={m} x2={x(age)} y1={base} y2={base} className="ag-lived" />
        {ages.map((a) => (
          <line key={`n${a}`} x1={x(a)} x2={x(a)} y1={base - 12} y2={base + 12} className={`ag-notch${a <= age ? ' is-past' : ''}`} />
        ))}
        {shown.map((a) => (
          <text key={`t${a}`} x={x(a)} y={base + 30} textAnchor="middle" className={`ag-notch-num${a === age ? ' is-on' : ''}`}>{a}</text>
        ))}
        {/* The reader's mark, a pencil stroke over the line. */}
        <g className="ag-mark" transform={`translate(${x(age)} 0)`}>
          <line x1={0} x2={0} y1={base - 26} y2={base + 8} />
          <circle cx={0} cy={base} r={7} />
        </g>
      </svg>
    </div>
  );
}
