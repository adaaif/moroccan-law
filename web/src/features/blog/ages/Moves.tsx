import { type ReactNode, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { reducedMotion } from '@/shared/services/motion';

/**
 * The ages that moved, a row each: the rule, then every age a text wrote for it in the order of their years, in the
 * page's direction, the old ones struck through and the one in force in violet; each age opens its printed page. Once in
 * view the rows write themselves, the ages one after the other and the strokes over the old ones (the post's one motion
 * that plays by itself; none with reduced motion).
 */
export type MoveStep = { age: number; year: number; viewer: string | null; source: ReactNode };
export type Move = { key: string; label: string; change: string; steps: MoveStep[] };

export function Moves({ rows, yearsWord, arrow }: { rows: Move[]; yearsWord: (n: number) => string; arrow: string }) {
  const box = useRef<HTMLOListElement>(null);
  // Each row writes itself when it comes into view (a list this long is never in view whole on a phone).
  const [seen, setSeen] = useState<Set<string>>(() => new Set(reducedMotion() ? rows.map((r) => r.key) : []));
  useEffect(() => {
    if (!box.current || seen.size === rows.length) return;
    const io = new IntersectionObserver((entries) => {
      const keys = entries.filter((e) => e.isIntersecting).map((e) => (e.target as HTMLElement).dataset.key!);
      if (keys.length) setSeen((s) => new Set([...s, ...keys]));
    }, { threshold: 0.6 });
    box.current.querySelectorAll<HTMLElement>('.ag-move').forEach((el) => io.observe(el));
    return () => io.disconnect();
  }, [rows, seen.size]);
  return (
    <ol ref={box} className="ag-moves">
      {rows.map((r) => (
        <li key={r.key} data-key={r.key} className={`ag-move${seen.has(r.key) ? ' is-on' : ''}`}>
          <p className="ag-move-head"><b>{r.label}</b><span className="ag-move-change">{r.change}</span></p>
          <ol className="ag-move-steps">
            {r.steps.map((s, k) => {
              const now = k === r.steps.length - 1;
              const inner = (
                <>
                  <span className="ag-step-age">{s.age}</span>
                  <span className="ag-step-unit">{yearsWord(s.age)}</span>
                  <span className="ag-step-year">{s.year}</span>
                </>
              );
              return (
                <li key={s.year} className={`ag-step${now ? ' is-now' : ' is-was'}`} style={{ ['--k' as string]: k }}>
                  {s.viewer ? <Link to={s.viewer} className="ag-step-box">{inner}</Link> : <span className="ag-step-box">{inner}</span>}
                </li>
              );
            })}
          </ol>
          <p className="ag-move-src">{r.steps.map((s, k) => <span key={s.year}>{k ? ` ${arrow} ` : ''}{s.source}</span>)}</p>
        </li>
      ))}
    </ol>
  );
}
