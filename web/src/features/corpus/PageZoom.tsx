import { useCallback, useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDismiss } from '@/shared/components/dismiss';
import type { Region } from './corpus.api';

type View = { s: number; x: number; y: number };
const MAX = 5;
const SWIPE = 70;           // px a finger travels sideways to turn the page, at the page's own size
const TAP_GAP = 300;        // ms between the two taps of a double tap

/** A printed page full screen (N10 of the read-and-trusted review): drawn 358 px wide on a phone, its body text stood
 *  about 5 px tall. Pinch and double-tap zoom, a finger pans, a swipe at the page's own size turns to the next one;
 *  opened on an article whose place is known, the page is framed on it, again when its place comes after the image.
 *  Escape and the phone's back close it. Opened at once from an article (`from`, HM39 of the hard-moment review):
 *  its head says the way back, «رجوع إلى الفصل 1», which the phone's back takes too, and offers the page's reading. */
export default function PageZoom({ src, alt, region, previous, next, onClose, from = null }: {
  src: string;
  alt: string;
  region: Region | null;
  previous: (() => void) | null;
  next: (() => void) | null;
  onClose: () => void;
  from?: { label: string; back: () => void; text: () => void } | null;
}) {
  const { t, i18n } = useTranslation();
  const box = useRef<HTMLDivElement>(null);
  const [view, setView] = useState<View>({ s: 1, x: 0, y: 0 });
  const [height, setHeight] = useState(0);
  const touches = useRef(new Map<number, { x: number; y: number }>());
  const gesture = useRef<{ from: View; d: number; mid: { x: number; y: number }; start: { x: number; y: number } } | null>(null);
  const lastTap = useRef(0);
  // Opened from an article, it is the page's first sight: no entry of its own, the phone's back goes to the article.
  useDismiss(onClose, !from);

  // Its own size, a scale and a place kept inside the screen.
  const fit = useCallback((v: View): View => {
    const el = box.current;
    if (!el) return v;
    const s = Math.min(MAX, Math.max(1, v.s));
    const w = el.clientWidth, h = el.clientHeight, ph = height * s;
    const x = Math.min(0, Math.max(w - w * s, v.x));
    const y = ph <= h ? (h - ph) / 2 : Math.min(0, Math.max(h - ph, v.y));
    return { s, x, y };
  }, [height]);

  // Framed on the article: its width fills the screen, its top a little under the screen's.
  const frame = useCallback((imageHeight: number) => {
    const el = box.current;
    if (!el) return;
    if (!region) { setView({ s: 1, x: 0, y: Math.max(0, (el.clientHeight - imageHeight) / 2) }); return; }
    const w = el.clientWidth;
    const s = Math.min(MAX, Math.max(1, 0.94 / Math.max(0.2, region.right - region.left)));
    // Under the buttons, the page kept on the screen: an article at a page's foot sits lower rather than over the dark.
    setView({ s, x: Math.min(0, Math.max(w - w * s, -region.left * w * s + w * 0.03)),
              y: Math.max(el.clientHeight - imageHeight * s, -region.top * imageHeight * s + 76) });
  }, [region]);

  // The article's place may come after the image: framed on it then.
  useEffect(() => { if (height) frame(height); }, [region]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const body = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => { document.body.style.overflow = body; };
  }, []);

  const zoomAt = (s: number, at: { x: number; y: number }) =>
    setView((v) => fit({ s, x: at.x - ((at.x - v.x) / v.s) * s, y: at.y - ((at.y - v.y) / v.s) * s }));
  const point = (e: React.PointerEvent) => {
    const r = box.current!.getBoundingClientRect();
    return { x: e.clientX - r.left, y: e.clientY - r.top };
  };

  const down = (e: React.PointerEvent) => {
    e.currentTarget.setPointerCapture(e.pointerId);
    touches.current.set(e.pointerId, point(e));
    const all = [...touches.current.values()];
    const mid = all.length === 2 ? { x: (all[0].x + all[1].x) / 2, y: (all[0].y + all[1].y) / 2 } : all[0];
    const d = all.length === 2 ? Math.hypot(all[0].x - all[1].x, all[0].y - all[1].y) : 0;
    gesture.current = { from: view, d, mid, start: point(e) };
  };
  const move = (e: React.PointerEvent) => {
    if (!touches.current.has(e.pointerId) || !gesture.current) return;
    touches.current.set(e.pointerId, point(e));
    const all = [...touches.current.values()];
    const g = gesture.current;
    if (all.length === 2 && g.d) {
      const d = Math.hypot(all[0].x - all[1].x, all[0].y - all[1].y);
      const mid = { x: (all[0].x + all[1].x) / 2, y: (all[0].y + all[1].y) / 2 };
      const s = g.from.s * (d / g.d);
      setView(fit({ s, x: mid.x - ((g.mid.x - g.from.x) / g.from.s) * s, y: mid.y - ((g.mid.y - g.from.y) / g.from.s) * s }));
    } else if (all.length === 1 && g.from.s > 1.01) {
      const p = all[0];
      setView(fit({ s: g.from.s, x: g.from.x + p.x - g.mid.x, y: g.from.y + p.y - g.mid.y }));
    }
  };
  const up = (e: React.PointerEvent) => {
    const g = gesture.current;
    const end = point(e);
    touches.current.delete(e.pointerId);
    if (!g || touches.current.size) return;
    gesture.current = null;
    const dx = end.x - g.start.x, dy = end.y - g.start.y;
    if (Math.hypot(dx, dy) < 10) {
      // A double tap: in at the finger, or back to the page's own size.
      const now = Date.now();
      if (now - lastTap.current < TAP_GAP) { zoomAt(view.s > 1.2 ? 1 : 2.5, end); lastTap.current = 0; } else lastTap.current = now;
      return;
    }
    if (g.from.s <= 1.01 && Math.abs(dx) > SWIPE && Math.abs(dy) < SWIPE) {
      // Pages turn the way the book's words run: in Arabic the next page is the one to the left.
      const forward = i18n.dir() === 'rtl' ? dx > 0 : dx < 0;
      (forward ? next : previous)?.();
    }
  };

  // Its look in style attributes, not utilities: it loads apart, and the shared stylesheet has a budget (N14).
  const button = 'grid size-11 place-items-center rounded-full';
  const pill = 'inline-flex h-11 min-w-0 items-center gap-1.5 rounded-full px-4 text-meta font-medium';
  const on = (enabled = true) => ({ background: 'rgba(0,0,0,.55)', color: '#fff', opacity: enabled ? 1 : 0.4 });
  return (
    <div role="dialog" aria-modal="true" aria-label={alt} className="fixed inset-0 flex flex-col" style={{ zIndex: 50, background: '#1b1a1f' }}>
      <div className="absolute inset-x-0 top-0 flex items-center justify-between gap-2 p-3"
           style={{ zIndex: 1, paddingTop: 'max(0.75rem, env(safe-area-inset-top))', background: from ? 'rgba(27,26,31,.94)' : undefined }}>
        {from ? (
          <button type="button" onClick={from.back} className={pill} style={on()}>
            <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" className="rtl:rotate-180"><path d="M15 6l-6 6 6 6" /></svg>
            <span className="truncate">{t('pages:corpus.backTo')} <bdi>{from.label}</bdi></span>
          </button>
        ) : (
          <button type="button" onClick={onClose} aria-label={t('pages:corpus.close')} title={t('pages:corpus.close')} className={button} style={on()}>
            <svg aria-hidden="true" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M6 6l12 12M18 6 6 18" /></svg>
          </button>
        )}
        {/* From an article, a slim head: the way back and the page's reading; the fingers zoom (the foot says how). */}
        {from ? <button type="button" onClick={from.text} className={`${pill} shrink-0`} style={on()}>{t('pages:corpus.ocrText')}</button> : (
          <div className="flex shrink-0 gap-2">
            <button type="button" onClick={() => zoomAt(view.s / 1.5, { x: box.current!.clientWidth / 2, y: box.current!.clientHeight / 2 })}
                    disabled={view.s <= 1} aria-label={t('pages:corpus.zoomOut')} className={button} style={on(view.s > 1)}>−</button>
            <button type="button" onClick={() => zoomAt(view.s * 1.5, { x: box.current!.clientWidth / 2, y: box.current!.clientHeight / 2 })}
                    disabled={view.s >= MAX} aria-label={t('pages:corpus.zoomIn')} className={button} style={on(view.s < MAX)}>+</button>
          </div>
        )}
      </div>
      <div ref={box} className="relative min-h-0 flex-1 overflow-hidden" style={{ touchAction: 'none', userSelect: 'none' }}
           onPointerDown={down} onPointerMove={move} onPointerUp={up} onPointerCancel={up}
           onWheel={(e) => { const r = e.currentTarget.getBoundingClientRect();
                             zoomAt(view.s * (e.deltaY < 0 ? 1.15 : 1 / 1.15), { x: e.clientX - r.left, y: e.clientY - r.top }); }}>
        <img src={src} alt={alt} draggable={false}
             onLoad={(e) => { const h = e.currentTarget.getBoundingClientRect().height / view.s; setHeight(h); frame(h); }}
             className="absolute top-0 block w-full bg-white"
             style={{ left: 0, maxWidth: 'none', transformOrigin: '0 0', transform: `translate(${view.x}px, ${view.y}px) scale(${view.s})` }} />
        {region ? (
          <span aria-hidden="true" className="pointer-events-none absolute border-2 border-stamp"
                style={{ borderRadius: 3, transformOrigin: '0 0', left: 0, top: 0, width: `${(region.right - region.left) * 100}%`, height: height ? (region.bottom - region.top) * height : 0,
                         transform: `translate(${view.x + region.left * (box.current?.clientWidth ?? 0) * view.s}px, ${view.y + region.top * height * view.s}px) scale(${view.s})` }} />
        ) : null}
      </div>
      <div className="flex items-center justify-between gap-3 p-3 text-meta"
           style={{ color: 'rgba(255,255,255,.8)', paddingBottom: 'max(0.75rem, env(safe-area-inset-bottom))' }}>
        <button type="button" onClick={() => previous?.()} disabled={!previous} className={button} style={on(Boolean(previous))} aria-label={t('corpus.previous')}>
          <svg aria-hidden="true" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" className="rtl:rotate-180"><path d="M15 6l-6 6 6 6" /></svg>
        </button>
        <span>{t('pages:corpus.zoomHint')}</span>
        <button type="button" onClick={() => next?.()} disabled={!next} className={button} style={on(Boolean(next))} aria-label={t('corpus.next')}>
          <svg aria-hidden="true" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" className="rtl:rotate-180"><path d="M9 6l6 6-6 6" /></svg>
        </button>
      </div>
    </div>
  );
}
