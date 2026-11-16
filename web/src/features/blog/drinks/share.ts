import { pageImageUrl } from '@/features/corpus/corpus.api';
import type { DrCrop } from '../blog.api';
import { fileName } from '@/shared/services/fileName';

/** Article 28 as a picture to share, 1080 × 1350: the article cut from its printed page, what it says in one line, and
 *  where it was printed. Drawn on the phone and handed to its share sheet (or saved where there is none). */
export type ArticlePicture = { dir: 'rtl' | 'ltr'; over: string; title: string; viewer: string; crop: DrCrop; line: string; source: string; site: string };

const W = 1080, H = 1350, PAD = 72;

function wrap(ctx: CanvasRenderingContext2D, words: string, max: number): string[] {
  const lines: string[] = [];
  let line = '';
  for (const w of words.split(' ')) {
    const next = line ? `${line} ${w}` : w;
    if (line && ctx.measureText(next).width > max) { lines.push(line); line = w; } else line = next;
  }
  if (line) lines.push(line);
  return lines;
}

export async function shareArticle(from: Element, p: ArticlePicture): Promise<boolean> {
  await document.fonts?.ready;
  const [, doc, index] = p.viewer.match(/\/pages\/(\d+)\/(\d+)/) ?? [];
  const img = new Image();
  img.src = `${pageImageUrl(doc, index)}?w=1600`;
  await img.decode();
  const cv = Object.assign(document.createElement('canvas'), { width: W, height: H });
  const ctx = cv.getContext('2d')!;
  const css = getComputedStyle(from);
  const v = (n: string, f: string) => css.getPropertyValue(n).trim() || f;
  const paper = v('--color-paper', '#F4F2EE'), ink = v('--color-ink', '#1E1B2C'), soft = v('--color-ink-soft', '#5D586E'), stamp = v('--color-stamp', '#5B3A9E');
  const rtl = p.dir === 'rtl';
  const ui = (w: number, s: number) => `${w} ${s}px "Readex Pro", system-ui, sans-serif`;
  ctx.fillStyle = paper; ctx.fillRect(0, 0, W, H);
  ctx.direction = p.dir; ctx.textAlign = rtl ? 'right' : 'left';
  const x0 = rtl ? W - PAD : PAD;
  ctx.fillStyle = soft; ctx.font = ui(500, 30); ctx.fillText(p.over, x0, PAD + 20);
  ctx.fillStyle = ink; ctx.fillRect(PAD, PAD + 40, W - 2 * PAD, 3); ctx.fillRect(PAD, PAD + 47, W - 2 * PAD, 3);
  ctx.font = rtl ? '700 72px "Markazi Text", serif' : '600 56px "Source Serif 4", Georgia, serif';
  ctx.fillText(p.title, x0, PAD + 140);
  // The clipping: white paper, the print as the Bulletin printed it.
  const sx = p.crop.left * img.naturalWidth, sy = p.crop.top * img.naturalHeight;
  const sw = (p.crop.right - p.crop.left) * img.naturalWidth, sh = (p.crop.bottom - p.crop.top) * img.naturalHeight;
  const dw = W - 2 * PAD, dh = (sh / sw) * dw, dy = PAD + 200;
  ctx.fillStyle = '#ffffff'; ctx.shadowColor = 'rgba(30, 27, 44, 0.18)'; ctx.shadowBlur = 24; ctx.shadowOffsetY = 6;
  ctx.fillRect(PAD - 18, dy - 18, dw + 36, dh + 36);
  ctx.shadowColor = 'transparent';
  ctx.drawImage(img, sx, sy, sw, sh, PAD, dy, dw, dh);
  let y = dy + dh + 90;
  ctx.fillStyle = ink; ctx.font = ui(500, 32);
  for (const l of wrap(ctx, p.line, W - 2 * PAD).slice(0, 4)) { ctx.fillText(l, x0, y); y += 48; }
  // Where it was printed, under what it says.
  ctx.fillStyle = soft; ctx.font = ui(400, 26);
  y += 18;
  for (const l of wrap(ctx, p.source, W - 2 * PAD).slice(0, 2)) { ctx.fillText(l, x0, y); y += 36; }
  ctx.fillStyle = stamp; ctx.font = ui(700, 32); ctx.fillText(p.site, x0, H - PAD + 6);
  const blob = await new Promise<Blob>((done, fail) => cv.toBlob((b) => (b ? done(b) : fail(new Error('canvas'))), 'image/png'));
  const file = new File([blob], fileName('article-28-1967.png'), { type: 'image/png' });
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
