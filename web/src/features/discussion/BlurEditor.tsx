import { useEffect, useRef, useState } from 'react';
import { Sheet } from '@/shared/components/Sheet';
import { useT } from './strings';

type Box = { x: number; y: number; w: number; h: number };
const LONGEST = 2400;

/** Blocks of `size` pixels, each one colour: unlike a blur, nothing to sharpen back. */
function pixelate(ctx: CanvasRenderingContext2D, source: CanvasImageSource, b: Box, scale: number) {
  const x = Math.round(b.x * scale), y = Math.round(b.y * scale);
  const w = Math.max(1, Math.round(b.w * scale)), h = Math.max(1, Math.round(b.h * scale));
  const size = Math.max(10, Math.round(Math.min(w, h) / 5), Math.round(Math.max(w, h) / 24));
  const small = document.createElement('canvas');
  small.width = Math.max(1, Math.ceil(w / size));
  small.height = Math.max(1, Math.ceil(h / size));
  const s = small.getContext('2d')!;
  s.drawImage(source, x, y, w, h, 0, 0, small.width, small.height);
  ctx.save();
  ctx.imageSmoothingEnabled = false;
  ctx.drawImage(small, 0, 0, small.width, small.height, x, y, w, h);
  ctx.restore();
}

/** Covering names and numbers on a picture before it leaves the device (D5): drag over each, undo, done. The
 *  picture is drawn again at most 2400 px on its longest side; the server then strips whatever metadata is left. */
export function BlurEditor({ file, onDone, onCancel }: {
  file: File;
  onDone: (blob: Blob) => void;
  onCancel: () => void;
}) {
  const { t } = useT();
  const canvas = useRef<HTMLCanvasElement>(null);
  const [image, setImage] = useState<ImageBitmap | null>(null);
  const [boxes, setBoxes] = useState<Box[]>([]);
  const [drag, setDrag] = useState<Box | null>(null);
  const start = useRef<{ x: number; y: number } | null>(null);

  // A bitmap needs no address to revoke, and turns a phone's photo the way its EXIF says.
  useEffect(() => {
    let live = true;
    void createImageBitmap(file, { imageOrientation: 'from-image' }).then((bitmap) => {
      if (live) setImage(bitmap);
      else bitmap.close();
    });
    return () => { live = false; };
  }, [file]);

  // The canvas shows the picture at its own scale (CSS fits it); boxes are in the image's pixels.
  const scale = image ? Math.min(1, LONGEST / Math.max(image.width, image.height)) : 1;
  useEffect(() => {
    const c = canvas.current;
    if (!c || !image) return;
    c.width = Math.round(image.width * scale);
    c.height = Math.round(image.height * scale);
    const ctx = c.getContext('2d')!;
    ctx.drawImage(image, 0, 0, c.width, c.height);
    const base = document.createElement('canvas');
    base.width = c.width;
    base.height = c.height;
    base.getContext('2d')!.drawImage(c, 0, 0);
    for (const b of boxes) pixelate(ctx, base, b, scale);
    if (drag) {
      const stamp = getComputedStyle(document.documentElement).getPropertyValue('--color-stamp').trim();
      ctx.save();
      ctx.strokeStyle = stamp;
      ctx.lineWidth = Math.max(2, 3 * scale);
      ctx.setLineDash([10, 6]);
      ctx.fillStyle = stamp;
      ctx.globalAlpha = 0.15;
      ctx.fillRect(drag.x * scale, drag.y * scale, drag.w * scale, drag.h * scale);
      ctx.globalAlpha = 1;
      ctx.strokeRect(drag.x * scale, drag.y * scale, drag.w * scale, drag.h * scale);
      ctx.restore();
    }
  }, [image, boxes, drag, scale]);

  const point = (e: React.PointerEvent<HTMLCanvasElement>) => {
    const r = e.currentTarget.getBoundingClientRect();
    return { x: ((e.clientX - r.left) / r.width) * (image?.width ?? 1),
             y: ((e.clientY - r.top) / r.height) * (image?.height ?? 1) };
  };
  const span = (a: { x: number; y: number }, b: { x: number; y: number }): Box =>
    ({ x: Math.min(a.x, b.x), y: Math.min(a.y, b.y), w: Math.abs(a.x - b.x), h: Math.abs(a.y - b.y) });

  const finish = () => {
    canvas.current?.toBlob((blob) => blob && onDone(blob), 'image/jpeg', 0.9);
  };

  return (
    <Sheet centered label={t('pictures.blurTitle')} onClose={onCancel} wide>
      <div className="flex flex-col gap-3">
        <h2 className="m-0 text-lead font-semibold">{t('pictures.blurTitle')}</h2>
        <p className="m-0 text-body text-ink-soft">{t('pictures.blurHint')}</p>
        <div className="flex justify-center rounded-control bg-paper p-2">
          <canvas ref={canvas} className="max-h-[60vh] max-w-full touch-none cursor-crosshair rounded-[3px]"
                  onPointerDown={(e) => {
                    e.currentTarget.setPointerCapture(e.pointerId);
                    start.current = point(e);
                    setDrag({ ...start.current, w: 0, h: 0 });
                  }}
                  onPointerMove={(e) => start.current && setDrag(span(start.current, point(e)))}
                  onPointerUp={(e) => {
                    if (start.current) {
                      const b = span(start.current, point(e));
                      if (b.w > 6 && b.h > 6) setBoxes((all) => [...all, b]);
                    }
                    start.current = null;
                    setDrag(null);
                  }} />
        </div>
        <p className="m-0 text-meta text-ink-soft">{t('pictures.stripped')}</p>
        <div className="flex flex-wrap items-center gap-2">
          <button type="button" onClick={() => setBoxes((all) => all.slice(0, -1))} disabled={!boxes.length}
                  className="h-11 rounded-control border border-rule px-4 text-body hover:bg-paper disabled:opacity-50">{t('pictures.undo')}</button>
          <button type="button" onClick={onCancel} className="h-11 rounded-control border border-rule px-4 text-body hover:bg-paper">{t('pictures.cancel')}</button>
          <button type="button" onClick={finish} disabled={!image}
                  className="ms-auto h-11 rounded-control bg-stamp px-6 text-body font-semibold text-on-stamp hover:bg-stamp-deep">{t('pictures.done')}</button>
        </div>
      </div>
    </Sheet>
  );
}
