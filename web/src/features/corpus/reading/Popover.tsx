import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { useDismiss } from '@/shared/components/dismiss';

/** A small card over the text, beside the words that opened it: placed in the viewport (under the words, or
 *  over them when there is no room), closed by Escape, a click elsewhere, or scrolling away. Rendered at the end
 *  of the page (a portal), since the words that open it sit inside a paragraph. */
export function Floating({ anchor, onClose, children, label, hover = false }: {
  anchor: HTMLElement | null;
  onClose: () => void;
  children: React.ReactNode;
  label: string;
  /** Shown while the pointer rests: no history entry for the phone's back (U5) to take. */
  hover?: boolean;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState<{ top: number; left: number; width: number } | null>(null);
  useDismiss(onClose, !hover);

  useLayoutEffect(() => {
    if (!anchor) return;
    const place = () => {
      const r = anchor.getBoundingClientRect();
      const width = Math.min(380, window.innerWidth - 32);
      const left = Math.min(Math.max(16, r.left + r.width / 2 - width / 2), window.innerWidth - width - 16);
      const height = ref.current?.offsetHeight ?? 160;
      const below = r.bottom + 8 + height < window.innerHeight;
      setPos({ top: below ? r.bottom + 8 : Math.max(8, r.top - 8 - height), left, width });
    };
    place();
    window.addEventListener('resize', place);
    return () => window.removeEventListener('resize', place);
  }, [anchor]);

  // Opened by a tap or a key, it takes the focus (PX25 of the where-it-trips review): portaled to the end of the page, it
  // was out of reach by Tab, and tabbing toward it scrolled its words away and closed it. Escape gives the focus back.
  useEffect(() => { if (!hover && pos) ref.current?.focus({ preventScroll: true }); }, [hover, pos === null]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const click = (e: MouseEvent) => {
      if (!ref.current?.contains(e.target as Node) && !anchor?.contains(e.target as Node)) onClose();
    };
    const scroll = () => {
      const r = anchor?.getBoundingClientRect();
      if (!r || r.bottom < 0 || r.top > window.innerHeight) onClose();
    };
    document.addEventListener('mousedown', click);
    window.addEventListener('scroll', scroll, { passive: true });
    return () => {
      document.removeEventListener('mousedown', click);
      window.removeEventListener('scroll', scroll);
    };
  }, [anchor, onClose]);

  return createPortal(
    <div ref={ref} role="dialog" aria-label={label} tabIndex={-1}
         style={pos ? { top: pos.top, left: pos.left, width: pos.width } : { visibility: 'hidden', top: 0, left: 0 }}
         className="fixed z-[60] rounded-control border border-rule bg-sheet p-4 font-ui text-body leading-relaxed text-ink shadow-[0_16px_40px_-16px_rgba(30,27,58,0.45)]">
      {children}
    </div>,
    document.body,
  );
}
