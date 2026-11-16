import { colours, layout, paint } from './paint';
import { fileName } from '@/shared/services/fileName';

/** The picture to share: the century of the clock as one image, 1080 × 1350 (a post's shape), drawn on the phone and
 *  handed to its share sheet (or saved where there is none). Never sent to the server. */
export type SharePicture = { dir: 'rtl' | 'ltr'; over: string; title: string; sub: string; legend: [string, string]; source: string; site: string; first: number; last: number };

const W = 1080, H = 1350, PAD = 72;

export async function drawShare(rows: Uint8Array[], p: SharePicture, from: Element): Promise<Blob> {
  await document.fonts?.ready;
  const cv = Object.assign(document.createElement('canvas'), { width: W, height: H });
  const ctx = cv.getContext('2d')!;
  const col = colours(from);
  const css = getComputedStyle(from);
  const v = (n: string, f: string) => css.getPropertyValue(n).trim() || f;
  const paper = v('--color-paper', '#F4F2EE'), ink = v('--color-ink', '#1E1B2C'), soft = v('--color-ink-soft', '#5D586E');
  ctx.fillStyle = paper; ctx.fillRect(0, 0, W, H);
  ctx.direction = p.dir;
  ctx.textAlign = p.dir === 'rtl' ? 'right' : 'left';
  const x = p.dir === 'rtl' ? W - PAD : PAD;
  ctx.fillStyle = soft; ctx.font = '500 30px "Readex Pro", system-ui, sans-serif';
  ctx.fillText(p.over, x, PAD + 20);
  ctx.fillStyle = ink; ctx.fillRect(PAD, PAD + 40, W - 2 * PAD, 3); ctx.fillRect(PAD, PAD + 47, W - 2 * PAD, 3);
  ctx.font = p.dir === 'rtl' ? '700 78px "Markazi Text", serif' : '600 62px "Source Serif 4", Georgia, serif';
  ctx.fillText(p.title, x, PAD + 140);
  ctx.fillStyle = soft; ctx.font = '400 30px "Readex Pro", system-ui, sans-serif';
  ctx.fillText(p.sub, x, PAD + 196);
  // The grid, left to right on every page: 114 rows of 7 px.
  const gy = PAD + 236;
  ctx.save();
  ctx.translate(PAD - 4, gy);
  ctx.direction = 'ltr';
  const l = { ...layout(W - 2 * PAD + 8, rows.length), rowH: 7, gap: 1.2, top: 0 };
  l.height = rows.length * l.rowH;
  paint(ctx, rows, l, col, null, p.first);
  ctx.fillStyle = soft; ctx.font = '400 22px "Readex Pro", system-ui, sans-serif'; ctx.textAlign = 'right';
  for (const y of [p.first, 1940, 1960, 1980, 2000, p.last]) ctx.fillText(String(y), l.left - 8, (y - p.first) * l.rowH + 8);
  ctx.restore();
  // The legend, and where it comes from.
  let ly = gy + rows.length * 7 + 54;
  ctx.direction = p.dir; ctx.textAlign = p.dir === 'rtl' ? 'right' : 'left';
  const side = p.dir === 'rtl' ? -1 : 1;
  ctx.font = '500 28px "Readex Pro", system-ui, sans-serif';
  let lx = x;
  for (const [i, words] of p.legend.entries()) {
    ctx.fillStyle = i === 0 ? col.ahead : col.gmt;
    ctx.fillRect(p.dir === 'rtl' ? lx - 28 : lx, ly - 22, 28, 28);
    ctx.fillStyle = ink;
    ctx.fillText(words, lx + side * 40, ly);
    lx += side * (ctx.measureText(words).width + 90);
  }
  ly += 56;
  ctx.fillStyle = soft; ctx.font = '400 24px "Readex Pro", system-ui, sans-serif';
  ctx.fillText(p.source, x, ly);
  ctx.fillStyle = v('--color-stamp', '#5B3A9E'); ctx.font = '700 32px "Readex Pro", system-ui, sans-serif';
  ctx.fillText(p.site, x, H - PAD + 6);
  return new Promise((done, fail) => cv.toBlob((b) => (b ? done(b) : fail(new Error('canvas'))), 'image/png'));
}

/** Hands the picture to the phone's share sheet; where there is none, saves it. False when the reader cancelled. */
export async function share(rows: Uint8Array[], p: SharePicture, from: Element): Promise<boolean> {
  const blob = await drawShare(rows, p, from);
  const file = new File([blob], fileName('clock.png'), { type: 'image/png' });
  try {
    if (navigator.canShare?.({ files: [file] })) { await navigator.share({ files: [file] }); return true; }
  } catch (err) {
    if ((err as DOMException).name === 'AbortError') return false;
  }
  const url = URL.createObjectURL(blob);
  Object.assign(document.createElement('a'), { href: url, download: file.name }).click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  return true;
}
