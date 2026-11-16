import { useEffect, useRef, useState } from 'react';
import { reducedMotion } from '@/shared/services/motion';
import { useWidth } from '../viz';
import { pieces, type Term } from './calendar';

/**
 * Three years as a wall calendar: a row a year (2020 to 2023), its months left to right on every page; the declaration in
 * ink, then every decree's term as a band, in turn violet and lighter violet, the two that changed a term hatched. Once in
 * view the terms fill in one after another (the post's one motion that plays by itself; none with reduced motion). A tap
 * names a decree.
 */
export function Calendar({ terms, months, picked, onPick, label }: {
  terms: (Term & { kind: 'declared' | 'extended' | 'changed' })[];
  months: string[];
  picked: string;
  onPick: (k: string) => void;
  label: (k: string) => string;
}) {
  const box = useRef<HTMLDivElement>(null);
  const [ref, width] = useWidth<HTMLDivElement>(640);
  const [shown, setShown] = useState(() => (reducedMotion() ? terms.length : 0));
  useEffect(() => {
    if (shown >= terms.length || !box.current) return;
    let timer = 0;
    const io = new IntersectionObserver(([e]) => {
      if (!e.isIntersecting) return;
      io.disconnect();
      let k = 0;
      timer = window.setInterval(() => { k += 1; setShown(k); if (k >= terms.length) window.clearInterval(timer); }, 50);
    }, { threshold: 0.2 });
    io.observe(box.current);
    return () => { io.disconnect(); window.clearInterval(timer); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const years = [2020, 2021, 2022, 2023];
  return (
    <div ref={(el) => { ref(el); box.current = el; }} className="em-cal" dir="ltr">
      {/* The months by name on a desk, by number on a phone, where a name would not fit its column. */}
      <div className="em-months">{months.map((m, i) => <span key={m}>{width < 560 ? i + 1 : m}</span>)}</div>
      {years.map((y) => (
        <div key={y} className="em-row">
          <span className="em-year">{y}</span>
          <div className="em-track">
            {months.map((m, i) => <i key={m} className="em-month-line" style={{ left: `${(i / 12) * 100}%` }} />)}
            {terms.map((t, k) => pieces(t).filter(([py]) => py === y).map(([, a, b]) => (
              <button key={`${t.key}-${y}`} type="button" aria-label={label(t.key)} aria-pressed={picked === t.key}
                      className={`em-term is-${t.kind}${k % 2 ? ' is-odd' : ''}${k < shown ? ' is-on' : ''}${picked === t.key ? ' is-picked' : ''}`}
                      style={{ left: `${a * 100}%`, width: `${Math.max(0.6, (b - a) * 100)}%` }} onClick={() => onPick(t.key)} />
            )))}
          </div>
        </div>
      ))}
    </div>
  );
}
