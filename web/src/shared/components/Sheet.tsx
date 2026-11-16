import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { useTranslation } from 'react-i18next';
import { useDismiss } from './dismiss';

/** A sheet from the bottom (U5): it follows the finger down and closes past a third of its height, or grows to the
 *  whole screen when pulled up from half (`half`, for long lists: the outline, the tools); on a desk `centered` makes
 *  it a card in the middle. The scrim and a tap on it close it too. */
export function Sheet({ label, onClose, children, half = false, centered = false, wide = false, closeButton = false }: {
  label: string;
  onClose: () => void;
  children: React.ReactNode;
  half?: boolean;
  centered?: boolean;
  wide?: boolean;
  closeButton?: boolean;
}) {
  const { t } = useTranslation();
  const ref = useRef<HTMLDivElement>(null);
  const scrim = useRef<HTMLDivElement>(null);
  const [full, setFull] = useState(!half);
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;
  useDismiss(onClose);

  useEffect(() => {
    ref.current?.querySelector<HTMLElement>('input, textarea, a, button')?.focus({ preventScroll: true });
    const overflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => { document.body.style.overflow = overflow; };
  }, []);

  // The finger: from the handle at any time, from the content only when it is scrolled to its top and pulled down.
  useEffect(() => {
    const el = ref.current;
    if (!el || (centered && window.matchMedia('(min-width: 640px)').matches)) return;
    let y0 = 0, t0 = 0, dy = 0, drag = false, fromHandle = false;
    const move = (y: number) => {
      dy = y - y0;
      el.style.transform = `translateY(${Math.max(dy, -40)}px)`;
      if (scrim.current) scrim.current.style.opacity = String(Math.max(0.2, 1 - Math.max(dy, 0) / el.offsetHeight));
    };
    const end = () => {
      if (!drag) return;
      drag = false;
      el.style.transition = 'transform 180ms ease-out';
      const fast = dy / Math.max(1, Date.now() - t0) > 0.6;
      if (dy > el.offsetHeight / 3 || (fast && dy > 40)) {
        el.style.transform = 'translateY(100%)';
        window.setTimeout(onCloseRef.current, 150);
        return;
      }
      if (dy < -50) setFull(true);
      el.style.transform = '';
      if (scrim.current) scrim.current.style.opacity = '';
      window.setTimeout(() => { el.style.transition = ''; }, 200);
    };
    const start = (e: TouchEvent) => {
      fromHandle = Boolean((e.target as HTMLElement).closest('[data-handle]'));
      y0 = e.touches[0].clientY;
      t0 = Date.now();
      dy = 0;
      drag = false;
    };
    const touchMove = (e: TouchEvent) => {
      const y = e.touches[0].clientY;
      if (!drag) {
        const down = y - y0 > 6;
        if (!(fromHandle && Math.abs(y - y0) > 4) && !(down && el.scrollTop <= 0)) return;
        drag = true;
        y0 = y;
        el.style.transition = 'none';
      }
      e.preventDefault();
      move(y);
    };
    el.addEventListener('touchstart', start, { passive: true });
    el.addEventListener('touchmove', touchMove, { passive: false });
    el.addEventListener('touchend', end);
    el.addEventListener('touchcancel', end);
    return () => {
      el.removeEventListener('touchstart', start);
      el.removeEventListener('touchmove', touchMove);
      el.removeEventListener('touchend', end);
      el.removeEventListener('touchcancel', end);
    };
  }, [centered]);

  const place = centered ? 'sm:items-center sm:p-6' : '';
  const shape = centered
    ? `sm:rounded-card sm:pt-5 ${wide ? 'sm:max-w-3xl' : 'sm:max-w-lg'}`
    : '';
  return createPortal(
    <div className={`fixed inset-0 z-50 flex items-end justify-center ${place}`} data-noprint>
      <div ref={scrim} aria-hidden="true" onClick={onClose}
           className="absolute inset-0 bg-scrim/55 motion-safe:animate-[fade-in_160ms_ease-out]" />
      <div ref={ref} role="dialog" aria-modal="true" aria-label={label}
           className={`relative w-full overscroll-contain overflow-y-auto rounded-t-[22px] bg-sheet px-4 pb-[calc(1.25rem+env(safe-area-inset-bottom))] shadow-xl motion-safe:animate-[sheet-up_200ms_ease-out] sm:px-5 ${full ? 'max-h-[92vh]' : 'max-h-[58vh]'} ${shape}`}>
        <div data-handle aria-hidden="true" className={`sticky top-0 z-10 -mx-4 flex h-7 touch-none items-center justify-center bg-sheet sm:-mx-5 ${centered ? 'sm:hidden' : ''}`}>
          <span className="h-1 w-10 rounded-full bg-field" />
        </div>
        {children}
        {closeButton ? (
          <button type="button" onClick={onClose} className="mt-3 h-12 w-full rounded-control border border-rule text-body font-medium text-ink hover:bg-paper">
            {t('article.close')}
          </button>
        ) : null}
      </div>
    </div>,
    document.body,
  );
}
