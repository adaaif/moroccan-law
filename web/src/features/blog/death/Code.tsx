import { type KeyboardEvent, useEffect, useRef, useState } from 'react';
import { reducedMotion } from '@/shared/services/motion';
import { type Cell, runs, step } from './code';

/**
 * The penal code, article by article: every article of our copy a small square, in the code's order, left to right
 * on every page, in runs by the part of the code it stands in (each run named in the page's language). The articles that
 * punish with death are filled in ink, those that rule on the penalty drawn in ink outline, the rest pale. Once in view
 * the filled squares ink in one after the other in the code's order (the post's one motion that plays by itself; none
 * with reduced motion). Only the marked squares are buttons: a tap, or the arrow keys, names one below.
 */
export function Code({ cells, kinds, picked, onPick, names, label, rtl }: {
  cells: Cell[];
  kinds: Record<string, 'death' | 'rule'>;
  picked: string;
  onPick: (n: string) => void;
  names: Record<string, string>;
  label: (n: string) => string;
  rtl: boolean;
}) {
  const order = cells.filter((c) => kinds[c.n]).map((c) => c.n);
  const box = useRef<HTMLDivElement>(null);
  const [lit, setLit] = useState(() => (reducedMotion() ? order.length : 0));
  useEffect(() => {
    if (lit >= order.length || !box.current) return;
    let timer = 0;
    const io = new IntersectionObserver(([e]) => {
      if (!e.isIntersecting) return;
      io.disconnect();
      let k = 0;
      timer = window.setInterval(() => {
        k += 1;
        setLit(k);
        if (k >= order.length) window.clearInterval(timer);
      }, 55);
    }, { threshold: 0.05 });
    io.observe(box.current);
    return () => { io.disconnect(); window.clearInterval(timer); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const litSet = new Set(order.slice(0, lit));
  const keys = (e: KeyboardEvent, n: string) => {
    const by = e.key === 'ArrowRight' || e.key === 'ArrowDown' ? 1 : e.key === 'ArrowLeft' || e.key === 'ArrowUp' ? -1 : 0;
    if (!by) return;
    e.preventDefault();
    const next = step(order, n, by);
    onPick(next);
    box.current?.querySelector<HTMLButtonElement>(`[data-n="${next}"]`)?.focus();
  };
  return (
    <div ref={box} className="dp-code">
      {runs(cells).map((run) => (
        <div key={run.cells[0].n} className="dp-run">
          <p className="dp-run-name" dir={rtl ? 'rtl' : 'ltr'}>{names[run.g]}</p>
          <div className="dp-cells" dir="ltr">
            {run.cells.map((c) => {
              const kind = kinds[c.n];
              if (!kind) return <span key={c.n} className="dp-cell" />;
              const on = picked === c.n;
              return (
                <button key={c.n} type="button" data-n={c.n} tabIndex={on ? 0 : -1}
                        className={`dp-cell is-${kind}${kind === 'rule' || litSet.has(c.n) ? ' is-lit' : ''}${on ? ' is-on' : ''}`}
                        aria-label={label(c.n)} aria-pressed={on} onClick={() => onPick(c.n)} onKeyDown={(e) => keys(e, c.n)} />
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}
