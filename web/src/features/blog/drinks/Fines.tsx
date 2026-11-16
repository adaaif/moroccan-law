import type { Group } from './fines';

/**
 * The order's fines, a row for each range: the articles that share it and the range in words, over one track of dirhams
 * from 0 to 2.500, left to right on every page, the same for every row so the bands compare; article 28 in violet.
 */
export function Fines({ rows, picked, label, range, ticks }: {
  rows: Group[];
  picked: number;
  label: (g: Group) => string;
  range: (g: Group) => string;
  ticks: string[];
}) {
  const max = 2500;
  return (
    <div className="dr-fines">
      <ol className="dr-fine-rows">
        {rows.map((g) => (
          <li key={`${g.lo}-${g.hi}`} className={`dr-fine${g.arts.includes(picked) ? ' is-on' : ''}`}>
            <p className="dr-fine-head"><span className="dr-fine-label">{label(g)}</span><b className="dr-fine-range">{range(g)}</b></p>
            <div className="dr-track" dir="ltr" aria-hidden="true">
              <i style={{ left: `${(g.lo / max) * 100}%`, width: `${Math.max(0.8, ((g.hi - g.lo) / max) * 100)}%` }} />
            </div>
          </li>
        ))}
      </ol>
      <div className="dr-ticks" dir="ltr" aria-hidden="true">{ticks.map((s) => <span key={s}>{s}</span>)}</div>
    </div>
  );
}
