import { useCallback, useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { reducedMotion } from '@/shared/services/motion';
import { Face } from './Face';
import { hands } from './time';

/**
 * The post's one motion that plays by itself: 20 September 2026, 01:59:58 by the hour ahead; two ticks; at 02:00 the
 * minute hand runs back a full turn, the hour hand from two to one, and the gold hour folds away. Then the clock goes
 * on from 01:00:00. With reduced motion the face shows the hour after, and the words say what happened.
 */
const TICK = 1000, HOLD = 2300, TURN = 1700;
const ease = (p: number) => (p < 0.5 ? 16 * p ** 5 : 1 - (-2 * p + 2) ** 5 / 2);
const pad = (n: number) => String(n).padStart(2, '0');

type Frame = { h: number; m: number; s: number; hour: number; minute: number; gold: number; ahead: boolean };

function frame(t: number): Frame {
  if (t < 2 * TICK) {
    const s = 58 + Math.floor(t / TICK);
    return { h: 1, m: 59, s, ...angles(1, 59, s), gold: 60, ahead: true };
  }
  if (t < HOLD) return { h: 2, m: 0, s: 0, ...angles(2, 0, 0), gold: 60, ahead: true };
  if (t < HOLD + TURN) {
    const p = ease((t - HOLD) / TURN);
    return { h: p < 0.5 ? 2 : 1, m: 0, s: 0, hour: 60 - 30 * p, minute: -360 * p, gold: 60 - 30 * p, ahead: p < 0.5 };
  }
  const s = Math.floor((t - HOLD - TURN) / TICK);
  return { h: 1, m: Math.floor(s / 60), s: s % 60, ...angles(1, Math.floor(s / 60), s % 60), gold: 30, ahead: false };
}

function angles(h: number, m: number, s: number) {
  const a = hands(h, m, s);
  return { hour: a.hour, minute: a.minute };
}

export function Hero({ when, quote, stamp }: { when: string; quote: string; stamp: React.ReactNode }) {
  const { t } = useTranslation('blog');
  const [now, setNow] = useState<number>(() => (reducedMotion() ? HOLD + TURN : 0));
  const box = useRef<HTMLDivElement>(null);
  const start = useRef<number | null>(null);
  const raf = useRef(0);
  const [size, setSize] = useState(260);

  const play = useCallback(() => {
    cancelAnimationFrame(raf.current);
    start.current = null;
    const step = (ts: number) => {
      if (start.current === null) start.current = ts;
      const t = ts - start.current;
      setNow(t);
      if (t < HOLD + TURN + 60 * TICK) raf.current = requestAnimationFrame(step);
    };
    raf.current = requestAnimationFrame(step);
  }, []);

  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const fit = () => setSize(Math.round(Math.min(300, Math.max(200, el.clientWidth * 0.62))));
    fit();
    const ro = new ResizeObserver(fit);
    ro.observe(el);
    if (reducedMotion()) return () => ro.disconnect();
    // Plays once the face is seen (the head above it may push it below the fold on a small phone).
    const io = new IntersectionObserver(([e]) => { if (e.isIntersecting) { play(); io.disconnect(); } }, { threshold: 0.6 });
    io.observe(el);
    return () => { ro.disconnect(); io.disconnect(); cancelAnimationFrame(raf.current); };
  }, [play]);

  const f = frame(now);
  const after = now >= HOLD + TURN / 2;
  return (
    <figure className="ck-hero" aria-labelledby="ck-hero-q">
      <div className="ck-hero-clock" ref={box}>
        <Face size={size} at={{ hour: f.hour, minute: f.minute, second: f.s * 6 }} gold={[30, f.gold]}
              label={t('clock.hero.aria')} />
        <p className="ck-zone" data-ahead={f.ahead || undefined} aria-hidden="true">
          <span className="ck-zone-dot" />{f.ahead ? t('clock.hero.ahead') : t('clock.hero.gmt')}
        </p>
      </div>
      <div className="ck-hero-words">
        <p className="ck-readout" dir="ltr" aria-hidden="true">
          <span key={f.h} className={after ? 'ck-roll' : ''}>{pad(f.h)}</span>:{pad(f.m)}<span className="ck-readout-s">:{pad(f.s)}</span>
        </p>
        <p className="ck-when" id="ck-hero-q">{when}</p>
        <blockquote className="ck-quote">{quote}</blockquote>
        <p className="ck-stamp-row">{stamp}</p>
        {!reducedMotion() ? (
          <button type="button" className="ck-replay" onClick={play}>
            <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M3 12a9 9 0 1 0 3-6.7" /><path d="M3 4v5h5" />
            </svg>
            {t('clock.hero.replay')}
          </button>
        ) : null}
      </div>
    </figure>
  );
}
